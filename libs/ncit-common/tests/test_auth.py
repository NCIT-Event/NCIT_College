import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask, jsonify
from ncit_common import (
    MemoryEventPublisher,
    MemoryRevocationStore,
    register_error_handlers,
    require_auth,
    require_college,
    require_role,
)

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE = _key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
PUBLIC = _key.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
)


def make_token(roles, exp_in=900, jti="t1", key=PRIVATE, iat=None):
    now = time.time() if iat is None else iat
    return jwt.encode(
        {
            "sub": "u1",
            "email": "hod@ncit.edu.np",
            "name": "Test HOD",
            "roles": roles,
            "jti": jti,
            "iat": now,
            "exp": int(now + exp_in),
            "iss": "ncit-auth",
            "aud": "ncit-web",
        },
        key,
        algorithm="RS256",
    )


@pytest.fixture
def store():
    s = MemoryRevocationStore()
    s.revoke_token("revoked")
    return s


@pytest.fixture
def client(store):
    app = Flask(__name__)
    app.config["JWT_PUBLIC_KEY"] = PUBLIC
    app.config["JWT_REVOCATION"] = store
    register_error_handlers(app)

    @app.get("/me")
    @require_auth
    def me():
        return jsonify(ok=True)

    @app.post("/write")
    @require_auth
    def write():
        return jsonify(ok=True)

    @app.post("/college-only")
    @require_college
    def college_only():
        return jsonify(ok=True)

    @app.put("/departments/<dept>")
    @require_role("hod", scope_from="dept", scope_prefix="dept:")
    def edit_department(dept):
        return jsonify(dept=dept)

    return app.test_client()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_missing_token_is_401(client):
    res = client.get("/me")
    assert res.status_code == 401
    assert res.json["error"]["code"] == "not_signed_in"


def test_valid_token_passes(client):
    assert client.get("/me", headers=bearer(make_token([]))).status_code == 200


def test_cookie_token_passes(client):
    client.set_cookie("ncit_access", make_token([]))
    assert client.get("/me").status_code == 200


def test_expired_token(client):
    res = client.get("/me", headers=bearer(make_token([], exp_in=-10)))
    assert res.json["error"]["code"] == "token_expired"


def test_wrong_signing_key(client):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = other.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    res = client.get("/me", headers=bearer(make_token([], key=pem)))
    assert res.json["error"]["code"] == "invalid_token"


def test_revoked_token(client):
    res = client.get("/me", headers=bearer(make_token([], jti="revoked")))
    assert res.json["error"]["code"] == "token_revoked"


def test_hod_edits_own_department_only(client):
    token = make_token([{"role": "hod", "scope": "dept:computer"}])
    assert client.put("/departments/computer", headers=bearer(token)).status_code == 200
    assert client.put("/departments/civil", headers=bearer(token)).status_code == 403


def test_super_admin_passes_everything(client):
    token = make_token([{"role": "super_admin", "scope": "*"}])
    assert client.put("/departments/civil", headers=bearer(token)).status_code == 200


def test_global_role_scope(client):
    token = make_token([{"role": "hod", "scope": "*"}])
    assert client.put("/departments/civil", headers=bearer(token)).status_code == 200


def test_user_revocation_rejects_older_tokens(client, store):
    old = make_token([], jti="old", iat=time.time() - 5)
    store.revoke_user("u1")
    assert client.get("/me", headers=bearer(old)).json["error"]["code"] == "token_revoked"
    fresh = make_token([], jti="fresh", iat=time.time() + 0.01)
    assert client.get("/me", headers=bearer(fresh)).status_code == 200


def test_cookie_write_requires_csrf(client):
    client.set_cookie("ncit_access", make_token([]))
    assert client.post("/write").json["error"]["code"] == "csrf_failed"
    client.set_cookie("ncit_csrf", "abc")
    assert client.post("/write", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert client.post("/write", headers={"X-CSRF-Token": "abc"}).status_code == 200


def test_bearer_write_needs_no_csrf(client):
    assert client.post("/write", headers=bearer(make_token([]))).status_code == 200


def test_event_publisher_shape():
    pub = MemoryEventPublisher("auth-service")
    ev = pub.publish("role.granted", actor={"id": "u1"}, entity="user", entity_id="u2", data={"role": "hod"})
    assert pub.events == [ev]
    assert ev["type"] == "role.granted" and ev["service"] == "auth-service" and ev["data"]["role"] == "hod"


def _token(claims):
    return jwt.encode({"iss": "ncit-auth", "aud": "ncit-web", **claims}, PRIVATE, algorithm="RS256")


def test_tokens_must_carry_expiry_issue_time_and_subject(client):
    """Security review: a correctly signed token without exp (it would never expire), iat or sub is refused."""
    now = time.time()
    full = {"sub": "u1", "email": "a@ncit.edu.np", "roles": [], "iat": now, "exp": int(now + 60)}
    assert client.get("/me", headers=bearer(_token(full))).status_code == 200
    for missing in ("exp", "iat", "sub"):
        claims = {k: v for k, v in full.items() if k != missing}
        res = client.get("/me", headers=bearer(_token(claims)))
        assert res.status_code == 401, missing


def test_require_college_refuses_outside_addresses(client):
    now = time.time()
    def tok(email):
        return bearer(_token({"sub": "u", "email": email, "roles": [], "iat": now, "exp": int(now + 60)}))
    assert client.post("/college-only", headers=tok("ram@ncit.edu.np")).status_code == 200
    assert client.post("/college-only", headers=tok("RAM@NCIT.EDU.NP")).status_code == 200
    for email in ("ram@gmail.com", "ram@ncit.edu.np.evil.com", "ram@fakencit.edu.np", ""):
        res = client.post("/college-only", headers=tok(email))
        assert res.status_code == 403 and res.json["error"]["code"] == "college_account_only", email
