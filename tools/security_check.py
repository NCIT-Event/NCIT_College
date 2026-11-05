#!/usr/bin/env python3
"""Security checks against a running NCIT site (standard library only).

    python3 tools/security_check.py https://ncit.edu.np            # production: read-only checks
    python3 tools/security_check.py http://localhost:8080 --dev     # local stack with DEV_LOGIN=true: everything

Read-only checks: security headers, no server version, sensitive files hidden,
sign-in required on every dashboard API, forged tokens refused, private
documents not reachable, injection-shaped input handled, errors don't leak
internals, sign-in codes rate limited.
With --dev (needs DEV_LOGIN, never available in production) it also signs in as
each role to check that roles can't reach each other's APIs, that CSRF
protection works, that cookie flags are right and that disguised uploads are
refused.

Exit code 0 when every check passes. Prints a table you can paste into a report.
"""

import base64
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
import uuid

BASE = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "http://localhost:8080").rstrip("/")
DEV = "--dev" in sys.argv
results: list[tuple[str, bool, str]] = []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def request(path, method="GET", body=None, headers=None, opener=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    h = {"Accept": "application/json", "User-Agent": "ncit-security-check"}
    if body is not None:
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        res = (opener or urllib.request.build_opener(NoRedirect)).open(req, timeout=15)
        return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def jload(body):
    try:
        return json.loads(body or b"{}")
    except ValueError:  # e.g. the gateway's own HTML 429 page
        return {}


def request_patiently(*args, **kwargs):
    """request(), waiting out the gateway's sign-in rate limit (429) instead of reporting it."""
    import time

    for _ in range(15):
        res = request(*args, **kwargs)
        if res[0] != 429:
            return res
        time.sleep(4)
    return res


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


# ---------- headers ----------
REQUIRED = {"content-security-policy": "default-src 'self'", "x-frame-options": "DENY", "x-content-type-options": "nosniff",
            "referrer-policy": "strict-origin", "permissions-policy": "camera=()"}
for label, path in (("HTML page", "/"), ("public API", "/api/v1/content/public/home"), ("static file", "/assets/css/site.css"),
                    ("error page", "/no-such-page"), ("dashboard API", "/api/v1/auth/users")):
    _, h, _ = request(path)
    h = {k.lower(): v for k, v in h.items()}
    missing = [k for k, v in REQUIRED.items() if v not in h.get(k, "")]
    check(f"Security headers on {label}", not missing, "missing: " + ", ".join(missing) if missing else "all present")
_, h, _ = request("/")
server = {k.lower(): v for k, v in h.items()}.get("server", "")
check("Server version hidden", not any(c.isdigit() for c in server), f"Server: {server or '(none)'}")
if BASE.startswith("https://"):
    check("HSTS over HTTPS", "max-age" in {k.lower(): v for k, v in h.items()}.get("strict-transport-security", ""))

# ---------- files that must never be served ----------
for path in ("/.env", "/.git/config", "/../../etc/passwd", "/media/", "/media/../.env", "/private/", "/infra/docker-compose.yml",
             "/services/auth-service/app/__init__.py"):
    status, _, body = request(path)
    check(f"Not served: {path}", status in (400, 403, 404) and b"SECRET" not in body and b"root:" not in body, f"HTTP {status}")

# ---------- sign-in required ----------
PROTECTED = ["/api/v1/auth/users", "/api/v1/audit/", "/api/v1/content/news", "/api/v1/academics/departments",
             "/api/v1/events/events", "/api/v1/eca/clubs", "/api/v1/admissions/review/applications",
             "/api/v1/careers/review/applications", "/api/v1/alumni/review/profiles", "/api/v1/notify/messages", "/api/v1/notify/me/notifications",
             "/api/v1/search/status", "/api/v1/admissions/me/applications", "/api/v1/events/me/registrations"]
bad = [p for p in PROTECTED if request(p)[0] != 401]
check(f"Sign-in required on {len(PROTECTED)} protected APIs", not bad, "open: " + ", ".join(bad) if bad else "all 401 without a session")


def b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


claims = {"sub": "x", "email": "attacker@ncit.edu.np", "roles": [{"role": "super_admin", "scope": "*"}], "exp": 4102444800,
          "iss": "ncit-auth", "aud": "ncit-web", "jti": uuid.uuid4().hex}
forged = {"alg none": f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}.",
          "wrong key": f"{b64({'alg': 'HS256', 'typ': 'JWT'})}.{b64(claims)}.{base64.urlsafe_b64encode(b'x' * 32).rstrip(b'=').decode()}"}
for name, tok in forged.items():
    status = request("/api/v1/auth/users", headers={"Authorization": f"Bearer {tok}"})[0]
    check(f"Forged token refused ({name})", status == 401, f"HTTP {status}")

# ---------- private documents ----------
fake = "private:admissions/documents/" + "a" * 32 + ".pdf"
for path in ("/media/admissions/documents/" + "a" * 32 + ".pdf", "/api/v1/admissions/me/applications/x/documents/transcript",
             "/api/v1/careers/review/applications/x/cv", f"/media/{fake}"):
    status = request(path)[0]
    check(f"Private file not reachable: {path[:60]}", status in (401, 403, 404), f"HTTP {status}")

# ---------- injection-shaped input ----------
for q in ("' OR 1=1 --", "\"; DROP TABLE documents; --", "<script>alert(1)</script>", "%", "\\x00", "a" * 3000):
    status, _, body = request("/api/v1/search/public/search?q=" + urllib.request.quote(q))
    check(f"Search handles {q[:24]!r}", status == 200 and b"Traceback" not in body, f"HTTP {status}")
status, _, body = request("/api/v1/events/public/calendar?month=2026-12%27%20OR%201=1")
check("Bad parameters refused cleanly", status == 422 and b"Traceback" not in body, f"HTTP {status}")

# ---------- errors don't leak ----------
status, h, body = request("/api/v1/content/public/news/does-not-exist")
check("API errors are plain JSON", status == 404 and body.startswith(b"{") and b"Traceback" not in body, f"HTTP {status}")
status, _, body = request("/api/v1/content/public/home", method="DELETE")
check("Unsupported methods refused", status in (401, 403, 405), f"HTTP {status}")

# ---------- signed-in checks (local stack with DEV_LOGIN only) ----------
if DEV:
    import time

    def session(email, headers=None):
        jar = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect)
        for _ in range(10):  # the gateway rate limits sign-ins; wait and retry instead of testing signed out
            status, h, _ = request("/api/v1/auth/dev/login", "POST", {"email": email}, opener=op, headers=headers)
            if status != 429:
                break
            time.sleep(4)
        if status != 200:
            raise SystemExit(f"could not sign in as {email} (HTTP {status}); is DEV_LOGIN on?")
        csrf = next((c.value for c in jar if c.name == "ncit_csrf"), "")
        return op, jar, csrf, status, h

    op, jar, csrf, status, h = session("admin@ncit.edu.np")
    cookies = h.get("Set-Cookie", "") + "".join(v for k, v in h.items() if k.lower() == "set-cookie")
    raw_cookies = [c for c in jar]
    access = next((c for c in raw_cookies if c.name == "ncit_access"), None)
    check("Session cookie is HttpOnly", access is not None and access.has_nonstandard_attr("HttpOnly"), "ncit_access")
    check("Session cookie is SameSite=Lax", access is not None and (access.get_nonstandard_attr("SameSite") or "").lower() == "lax")
    status = request("/api/v1/content/news", "POST", {"title": "csrf test"}, opener=op)[0]
    check("CSRF: change without the token refused", status == 403, f"HTTP {status}")
    status = request("/api/v1/content/news", "POST", {"title": "csrf test"}, opener=op, headers={"X-CSRF-Token": "wrong"})[0]
    check("CSRF: wrong token refused", status == 403, f"HTTP {status}")

    MATRIX = {
        "content.admin@ncit.edu.np": ["/api/v1/events/events", "/api/v1/eca/clubs", "/api/v1/admissions/review/applications", "/api/v1/auth/users"],
        "event.admin@ncit.edu.np": ["/api/v1/eca/clubs", "/api/v1/content/news", "/api/v1/careers/jobs"],
        "eca.admin@ncit.edu.np": ["/api/v1/events/events", "/api/v1/alumni/review/profiles"],
        "admissions.officer@ncit.edu.np": ["/api/v1/careers/review/applications", "/api/v1/alumni/review/profiles", "/api/v1/notify/messages"],
        "hr.officer@ncit.edu.np": ["/api/v1/admissions/review/applications", "/api/v1/audit/"],
        "alumni.coordinator@ncit.edu.np": ["/api/v1/admissions/review/applications", "/api/v1/careers/review/applications"],
        "hod.civil@ncit.edu.np": ["/api/v1/academics/departments/computer", "/api/v1/content/news"],
        "student.check@ncit.edu.np": ["/api/v1/auth/users", "/api/v1/events/events", "/api/v1/admissions/review/applications"],
    }
    for email, paths in MATRIX.items():
        op2, _, _, _, _ = session(email)
        assert request("/api/v1/auth/me", opener=op2)[0] == 200, f"{email} is not signed in"
        leaks = [p for p in paths if request(p, opener=op2)[0] not in (403, 404)]
        check(f"Role separation: {email.split('@')[0]}", not leaks, "reached: " + ", ".join(leaks) if leaks else f"refused on {len(paths)} other areas")

    for name, data in (("HTML disguised as JPEG", b"<html><script>alert(1)</script></html>"), ("PDF disguised as JPEG", b"%PDF-1.4\n%%EOF")):
        boundary = uuid.uuid4().hex
        payload = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"kind\"\r\n\r\nimage\r\n--{boundary}\r\n"
                   f"Content-Disposition: form-data; name=\"file\"; filename=\"photo.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
        status = request("/api/v1/content/uploads", "POST", raw=payload, opener=op,
                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "X-CSRF-Token": csrf})[0]
        check(f"Upload refused: {name}", status == 422, f"HTTP {status}")
    status, h, _ = request_patiently("/api/v1/auth/google/login?next=//evil.example/x", opener=op)
    loc = {k.lower(): v for k, v in h.items()}.get("location", "")
    check("No open redirect after sign-in", "evil.example" not in loc, loc[:60] or f"HTTP {status}")
    # an applicant account (any email address) can't take event places or ask to join clubs
    ext_jar = http.cookiejar.CookieJar()
    ext = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(ext_jar), NoRedirect)
    ext_email = f"check.{uuid.uuid4().hex[:8]}@example.com"
    for _ in range(10):  # rate limited like every sign-in: wait and retry
        status, _, body = request("/api/v1/auth/code/request", "POST", {"email": ext_email, "purpose": "applicant"}, opener=ext)
        if status != 429:
            break
        time.sleep(4)
    code = jload(body).get("dev_code", "")
    status = request_patiently("/api/v1/auth/code/verify", "POST", {"email": ext_email, "code": code}, opener=ext)[0]
    if status == 200:
        ext_csrf = {"X-CSRF-Token": next((c.value for c in ext_jar if c.name == "ncit_csrf"), "")}
        events = jload(request("/api/v1/events/public/events")[2]).get("items", [])
        clubs = jload(request("/api/v1/eca/public/clubs")[2]).get("items", [])
        reached = []
        if events:
            st = request(f"/api/v1/events/me/events/{events[0]['slug']}/register", "POST", {}, opener=ext, headers=ext_csrf)[0]
            reached += [f"event registration (HTTP {st})"] if st != 403 else []
        if clubs:
            st = request(f"/api/v1/eca/me/clubs/{clubs[0]['slug']}/join", "POST", {}, opener=ext, headers=ext_csrf)[0]
            reached += [f"club join (HTTP {st})"] if st != 403 else []
        check("Applicant accounts can't register for events or join clubs", not reached and (events or clubs),
              ", ".join(reached) or "refused")
    else:
        check("Applicant accounts can't register for events or join clubs", False, f"could not sign in by code (HTTP {status})")

    # the notification bell: your own only, and never from a shared cache
    st, h, body = request("/api/v1/notify/me/notifications", opener=op)
    cache_hdr = {k.lower(): v for k, v in h.items()}
    check("Notifications are private and never cached",
          st == 200 and "private" in cache_hdr.get("cache-control", "") and "x-app-cache" not in cache_hdr,
          f"HTTP {st}, Cache-Control: {cache_hdr.get('cache-control', '-')}")
    st = request("/api/v1/notify/me/notifications/read", "POST", {"all": True}, opener=op)[0]
    check("Notifications: marking read needs the CSRF token", st == 403, f"HTTP {st}")
    st, h, _ = request("/api/v1/events/me/registrations", opener=op)
    check("Signed-in answers never come from the page cache",
          "x-app-cache" not in {k.lower() for k in h}, f"HTTP {st}")

    # a visitor can't put a made-up address into the audit log
    xff_email = f"xff.{uuid.uuid4().hex[:8]}@ncit.edu.np"
    session(xff_email, {"X-Forwarded-For": "6.6.6.6"})
    ips = []
    for _ in range(10):  # the audit worker stores events a moment later
        _, _, body = request(f"/api/v1/audit/?q={xff_email}", opener=op)
        ips = [i.get("ip", "") for i in jload(body).get("items", [])]
        if ips:
            break
        time.sleep(1)
    check("Visitor can't fake their address (X-Forwarded-For)", bool(ips) and not any("6.6.6.6" in i for i in ips),
          f"recorded: {', '.join(sorted(set(ips))) or 'nothing'}")

    status = request("/api/v1/auth/code/request", "POST", {"email": "someone@ncit.edu.np", "purpose": "applicant"})[0]
    check("College addresses can't use email codes", status in (422, 429), f"HTTP {status}")

# ---------- rate limiting ----------
codes = [request("/api/v1/auth/code/request", "POST", {"email": f"rl{n}@example.com", "purpose": "nope"})[0] for n in range(15)]
check("Sign-in code requests rate limited", 429 in codes, f"{codes.count(429)} of 15 refused with 429")

# ---------- report ----------
width = max(len(n) for n, _, _ in results)
print(f"\nSecurity checks against {BASE}{' (with signed-in checks)' if DEV else ''}\n")
for name, ok, detail in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
failed = [n for n, ok, _ in results if not ok]
print(f"\n{len(results) - len(failed)} of {len(results)} passed" + (f"; FAILED: {', '.join(failed)}" if failed else ""))
sys.exit(1 if failed else 0)
