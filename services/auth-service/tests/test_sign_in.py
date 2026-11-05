from datetime import timedelta

from app.models import RefreshToken, utcnow
from conftest import csrf, google_sign_in
from sqlalchemy import update


def test_outside_email_is_refused(client, google, events):
    res = google_sign_in(client, google, "someone@gmail.com", hd="")
    assert res.status_code == 302
    assert res.headers["Location"] == "/login.html?error=wrong_domain"
    assert client.get_cookie("ncit_access") is None
    assert events.events[-1]["type"] == "user.sign_in_refused"
    assert events.events[-1]["data"]["email"] == "someone@gmail.com"


def test_college_address_without_workspace_claim_is_refused(client, google):
    # e.g. a personal Google account registered with a college address
    res = google_sign_in(client, google, "student@ncit.edu.np", hd="")
    assert res.headers["Location"].endswith("error=wrong_domain")


def test_lookalike_domain_is_refused(client, google):
    res = google_sign_in(client, google, "a@evilncit.edu.np", hd="evilncit.edu.np")
    assert res.headers["Location"].endswith("error=wrong_domain")


def test_unverified_email_is_refused(client, google):
    res = google_sign_in(client, google, "a@ncit.edu.np", verified=False)
    assert res.headers["Location"].endswith("error=email_not_verified")


def test_state_mismatch_is_refused(client, google):
    google.next_claims = {"sub": "x", "email": "a@ncit.edu.np", "email_verified": True, "hd": "ncit.edu.np"}
    client.get("/google/login")
    res = client.get("/google/callback?code=ok&state=forged")
    assert res.headers["Location"].endswith("error=state_mismatch")


def test_successful_sign_in_sets_session_and_default_role(client, google, events):
    res = google_sign_in(client, google, "Ram.Sharma@NCIT.edu.np", name="Ram Sharma")
    assert res.status_code == 302 and res.headers["Location"] == "/dashboard/"
    access = client.get_cookie("ncit_access")
    assert access is not None and access.http_only
    assert client.get_cookie("ncit_refresh").http_only
    me = client.get("/me").json["user"]
    assert me["email"] == "ram.sharma@ncit.edu.np"
    assert [r["role"] for r in me["roles"]] == ["student"]
    assert events.events[-1]["type"] == "user.signed_in"


def test_configured_super_admin_is_bootstrapped(client, google):
    google_sign_in(client, google, "admin@ncit.edu.np")
    assert "super_admin" in [r["role"] for r in client.get("/me").json["user"]["roles"]]


def test_next_parameter_cannot_redirect_off_site(client, google):
    google.next_claims = {"sub": "x", "email": "a@ncit.edu.np", "email_verified": True, "hd": "ncit.edu.np"}
    start = client.get("/google/login?next=//evil.example/steal")
    state = start.headers["Location"].split("state=")[1].split("&")[0]
    assert client.get(f"/google/callback?code=ok&state={state}").headers["Location"] == "/dashboard/"


def test_refresh_rotates_and_detects_reuse(client, google, app):
    google_sign_in(client, google, "a@ncit.edu.np")
    first = client.get_cookie("ncit_refresh").value
    assert client.post("/refresh", headers=csrf(client)).status_code == 200
    second = client.get_cookie("ncit_refresh").value
    assert second != first

    # Replaying the old token after the grace window revokes the whole sign-in.
    with app.app_context():
        session = app.extensions["db"]()
        session.execute(update(RefreshToken).where(RefreshToken.revoked_at.is_not(None))
                        .values(revoked_at=utcnow() - timedelta(minutes=5)))
        session.commit()
    client.set_cookie("ncit_refresh", first, path="/")
    res = client.post("/refresh", headers=csrf(client))
    assert res.status_code == 401 and res.json["error"]["code"] == "refresh_reused"
    # the newer token from the same sign-in is dead too
    client.set_cookie("ncit_refresh", second, path="/")
    client.set_cookie("ncit_csrf", "t")
    res = client.post("/refresh", headers={"X-CSRF-Token": "t"})
    assert res.status_code == 401 and res.json["error"]["code"] == "refresh_reused"


def test_concurrent_refresh_within_grace_is_allowed(client, google):
    google_sign_in(client, google, "a@ncit.edu.np")
    first = client.get_cookie("ncit_refresh").value
    assert client.post("/refresh", headers=csrf(client)).status_code == 200
    client.set_cookie("ncit_refresh", first, path="/")
    assert client.post("/refresh", headers=csrf(client)).status_code == 200


def test_refresh_requires_csrf(client, google):
    google_sign_in(client, google, "a@ncit.edu.np")
    assert client.post("/refresh").json["error"]["code"] == "csrf_failed"


def test_logout_revokes_access_token(client, google):
    google_sign_in(client, google, "a@ncit.edu.np")
    token = client.get_cookie("ncit_access").value
    headers = csrf(client)
    assert client.post("/logout", headers=headers).status_code == 200
    res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert res.json["error"]["code"] == "token_revoked"


def test_jwks_publishes_the_signing_key(client):
    keys = client.get("/.well-known/jwks.json").json["keys"]
    assert keys[0]["kty"] == "RSA" and keys[0]["kid"] == "ncit-1"


def test_dev_login_is_off_by_default(client):
    assert client.post("/dev/login", json={"email": "a@ncit.edu.np"}).status_code == 404


def test_next_after_sign_in_stays_on_this_site():
    """Security review: browsers turn "/\\evil.com" and "/<tab>/evil.com" into "//evil.com"."""
    from app.routes.auth import DEFAULT_NEXT, _safe_next

    for good in ("/dashboard/", "/dashboard/#news", "/apply?intake=fall-2026", "/events/open-day"):
        assert _safe_next(good) == good
    for bad in ("//evil.com", "/\\evil.com", "/\\/evil.com", "/\t/evil.com", "/\n/evil.com", "/\r/evil.com",
                "/ /evil.com", "/%09x\x00", "https://evil.com", "evil.com", "javascript:alert(1)", "", None, "/" + "a" * 600):
        assert _safe_next(bad) == DEFAULT_NEXT, repr(bad)
