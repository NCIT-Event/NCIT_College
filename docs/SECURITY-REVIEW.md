# Security review and full test run

**Date:** 2026-11-04 · **Scope:** the whole website as handed over in Phase 6 (11 services, 3 workers, nginx gateway, Caddy HTTPS, front end, Docker deployment) · **Result:** 7 problems found and fixed, each with a regression test; nothing open.

## How it was tested

1. **Code review** of everything that decides who can do what:
   - sign-in (Google, email codes, tokens, cookies, CSRF, revocation);
   - every route in every service, checked by a script for a role or ownership check (all of them have one);
   - department scoping for HODs;
   - uploads and private files;
   - the gateway configuration;
   - every place the front end turns data into HTML.
2. **Attacks on the running site** (local stack and Docker with HTTPS):
   - an outsider account trying staff and student actions;
   - one applicant reading or changing another's application and documents;
   - forged and altered tokens;
   - requests without the CSRF token, or from another site;
   - path traversal on `/media/`;
   - injection-shaped search queries;
   - faked visitor addresses;
   - open redirects after sign-in, in a real browser;
   - repeated uploads.
3. **Stored-script test (XSS):**
   - a script payload (`<i class=xssprobe>`, plus a variant that breaks out of attributes) was written into **78 text fields** in 7 databases, plus a hostile applicant name and application;
   - **73 page views** were then loaded in Chromium: every public page on desktop and phone, every dashboard view, the editor and the application review sheet;
   - the page was searched for the injected element.
4. **Scanners:**
   - `pip-audit` and `npm audit`: 0 known vulnerabilities;
   - `ruff`: clean;
   - secret scan of the repository: no secrets committed.
5. **Everything re-run after the fixes:**
   - all automated tests;
   - `tools/security_check.py`, locally with `--dev` and over HTTPS on Docker;
   - the browser end-to-end scripts for Phases 4–6.

## What was found and fixed

| # | Severity | Problem | Fix | Proven by |
|---|---|---|---|---|
| 1 | **High** | **Open redirect after sign-in.** `/login.html?next=/%5Cevil.com` or `?next=/%09/evil.com` sent a signed-in user to another website. Browsers read `\` as `/` and drop tabs, so both become `//evil.com`. This is a classic phishing trick: a genuine ncit.edu.np link that ends on a fake page. The server-side guard had the same gap for tab and newline variants. | The login page and auth-service now accept only a plain path on this site: no backslash, whitespace or control characters, no second leading slash. The login page also confirms the parsed URL is on the same origin. The Google callback re-checks the stored value. | Browser test: both payloads now land on `/dashboard/`. Unit test with 15 bad values. |
| 2 | **Medium** | **Anyone on the internet could book event places and ask to join clubs.** Applicant and alumni accounts are created by an emailed code, for *any* address, but event registration and club joining only checked "signed in". A script could fill every place at an event with fake Gmail accounts. | A new shared check `require_college` (`ncit-common`) allows only `@ncit.edu.np` accounts. It is used on register, cancel, join and leave. Look-alike domains (`ncit.edu.np.evil.com`) are refused. | Live attack refused (403); tests in events, ECA and `ncit-common`; new `security_check` check. |
| 3 | **Medium** | **Faked visitor address and a shared rate limit.** (a) Any visitor could send `X-Forwarded-For: 6.6.6.6` and that address was written into the audit log. (b) Behind Caddy, nginx saw every visitor as Caddy's address, so all visitors shared one sign-in rate limit: one person could lock everyone out of sign-in for a minute at a time. | Caddy gets a fixed address (`172.30.0.250`) on a fixed Docker subnet. The gateway trusts `X-Forwarded-For` only from that address (nginx `real_ip`) and passes on exactly one address, the visitor's. `X-Forwarded-Proto` is also trusted only from Caddy. | Live: a faked address is never recorded. Behind Caddy on Docker the real visitor address is recorded. One visitor at the limit no longer blocks another. New `security_check` check. |
| 4 | Low | **Replaced uploads stayed on disk.** Uploading a transcript again, re-applying for a job, or changing an alumni photo left the old file behind. For applicants, a superseded passport or transcript copy was kept with no way to remove it. For alumni, the old photo stayed public at its old address. Repeated uploads also filled the disk. | A new `remove_file()` in the shared library deletes the replaced file. It only touches files the site itself named (a random 32-character name), so it can't be pointed at anything else. | 5 uploads to one slot now leave 1 file; tests in `ncit-common` and admissions. |
| 5 | Low | **Tokens weren't required to expire.** Tokens were checked for signature, issuer and audience, but a correctly signed token with no expiry would have been accepted forever. Only auth-service can sign tokens, so this was defence in depth. | Tokens must carry `exp`, `iat`, `sub`, `aud` and `iss`. | Test: a signed token missing any of them is refused. |
| 6 | Low | **A line break in a Contact-form name made the email fail.** Python's mail library refuses header injection, so no extra headers could be added. But the message was lost and showed as *Failed* in the Email log. | Email subjects are folded onto one line. | Test with `\r\nBcc:` in the name. |
| 7 | Low (deployment) | **The very first start of a new server could fail.** On first start PostgreSQL runs a temporary local-only server while it sets up. The health check accepted that, so database setup ran too early and stopped with "connection refused". Found while re-testing the Docker deployment from empty. | The health check now asks over TCP, which only answers once setup is finished. | Docker: `down -v`, then `up` from empty succeeds; all services healthy. |

## What was checked and found sound

- **Sign-in:**
  - Google accounts must be verified and in the NCIT Workspace domain;
  - the OAuth flow uses state, nonce and PKCE;
  - email codes are hashed, single-use, expire in 10 minutes, allow 5 tries and are rate limited;
  - college addresses can't use email codes.
- **Tokens and sessions:**
  - RS256 only (`alg: none` and wrong-key tokens refused);
  - 15-minute access tokens;
  - rotating refresh tokens with reuse detection;
  - revocation takes effect on the next request;
  - cookies are HttpOnly and SameSite=Lax, and Secure in production.
- **CSRF:** every cookie-authenticated change needs the matching token, compared in constant time. Requests from another site are refused.
- **Access control:**
  - all 124 routes were checked: every editor route needs its role;
  - HOD edits are scoped to their own department, including child items addressed by ID;
  - applicants and job applicants see only their own records and files (other people's give 404, not 403, so their IDs can't be confirmed);
  - the 8 roles are separated from each other.
- **XSS:** none. All 73 page views showed the payloads as text. Every HTML template escapes data, and the Content-Security-Policy forbids inline scripts as a second barrier. Link fields accept only `https://` or `/` addresses, so `javascript:` links can't be stored.
- **Injection:**
  - all database access goes through SQLAlchemy with bound parameters;
  - search reduces a query to plain words (at most 8) before building the full-text query, so search operators can't be injected;
  - quotes, `--`, `%`, tsquery operators and 5,000-character queries are handled (over-long queries get a clean 400).
- **Files:**
  - images are decoded and re-encoded, which strips EXIF and GPS;
  - PDFs are checked;
  - decompression bombs and size limits are enforced;
  - private files live outside the gateway's reach;
  - private keys are matched against a strict pattern before use;
  - `/media/` path traversal is refused.
- **Gateway:**
  - one set of security headers on every response;
  - server version hidden;
  - `.env`, `.git` and source files not served;
  - request size and slow-request limits;
  - rate limits on sign-in, codes, forms and the Contact form.
- **Errors:** plain JSON with no stack traces or internals.
- **Dependencies:** no known vulnerabilities; a weekly scan runs in CI.

## Accepted risks (low, documented)

| Risk | Why it is accepted |
|---|---|
| Asking for a sign-in code for a **suspended** applicant or alumni address says "suspended", which confirms that the address has an account. | This affects only outside accounts. The clear message helps a genuine person contact the college. It reveals nothing about staff. |
| Photos uploaded in the dashboard editors and then not saved stay in `/media/`. | Only signed-in staff can upload. The files are re-encoded images under random names. Clean-up can be done by hand if it ever matters. |
| The fixed Docker subnet `172.30.0.0/24` could clash with a network already on the server. | If it does, change it in three marked places (`infra/docker-compose.yml`, `infra/docker-compose.tls.yml`, `gateway/nginx.conf`). See [OPERATIONS.md](OPERATIONS.md). |

## Results after the fixes

| | |
|---|---|
| Automated tests | **146 pass** (8 new regression tests); the 2 Redis tests also pass against a real Redis |
| `tools/security_check.py --dev` (local) | **49 of 49** (2 new checks: outsider accounts, faked addresses) |
| `tools/security_check.py https://localhost` (Docker + Caddy) | **32 of 32** read-only checks |
| Attack scripts (outsider account, faked address, upload orphaning, open redirect) | all refused |
| Stored-script test | 0 injected elements across 73 page views |
| Browser end-to-end scripts (Phases 4–6) | pass; students still register for events and join clubs |
| `pip-audit`, `npm audit`, `ruff` | clean |

## Files changed

- `frontend/public/assets/js/login.js`: `safeNext()`
- `services/auth-service/app/routes/auth.py`: `_safe_next()`, re-checked in the callback
- `libs/ncit-common/ncit_common/auth.py`: `require_college`, required token claims
- `libs/ncit-common/ncit_common/media.py`: `remove_file()`
- `services/event-service/app/routes/me.py`, `services/eca-service/app/routes/me.py`: college accounts only
- `services/admission-service/app/routes/me.py`, `services/career-service/app/routes/me.py`, `services/alumni-service/app/routes/me.py`: delete replaced files
- `services/notification-service/app/templates.py`: one-line subjects
- `gateway/nginx.conf`: trusted proxy, single forwarded address
- `infra/docker-compose.yml`, `infra/docker-compose.tls.yml`: fixed subnet and Caddy address, `ALLOWED_DOMAIN` for every service, TCP health check for PostgreSQL
- `tools/security_check.py`: 2 new checks; waits out rate limits instead of failing
- Tests in `ncit-common`, auth, events, ECA, admissions and notifications
