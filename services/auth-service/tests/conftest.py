import pytest
from app import create_app
from app.google import GoogleClient, SignInRefused
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from ncit_common import MemoryEventPublisher, MemoryRevocationStore

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE = _key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
).decode()


class FakeGoogle(GoogleClient):
    """Real claim checks, no network: the test decides what Google 'returns'."""

    def __init__(self):
        super().__init__("client-id", "secret", "http://localhost/api/v1/auth/google/callback", "ncit.edu.np")
        self.next_claims = None

    def exchange_code(self, code, code_verifier):
        if code == "bad":
            raise SignInRefused("google_exchange_failed")
        return "fake-id-token"

    def verify(self, id_token, nonce):
        claims = dict(self.next_claims)
        claims.setdefault("nonce", nonce)
        return self.check_claims(claims, nonce)


@pytest.fixture
def google():
    return FakeGoogle()


@pytest.fixture
def events():
    return MemoryEventPublisher("auth-service")


@pytest.fixture
def revocation():
    return MemoryRevocationStore()


@pytest.fixture
def app(tmp_path, google, events, revocation):
    return create_app({
        "SECRET_KEY": "test",
        "DATABASE_URL": f"sqlite:///{tmp_path}/auth.db",
        "JWT_PRIVATE_KEY": PRIVATE,
        "COOKIE_SECURE": False,
        # the test client calls routes without the gateway's /api/v1/auth prefix
        "AUTH_COOKIE_PATH": "/",
        "SUPER_ADMIN_EMAILS": {"admin@ncit.edu.np"},
        "GOOGLE_CLIENT": google,
        "EVENTS": events,
        "JWT_REVOCATION": revocation,
    })


@pytest.fixture
def client(app):
    return app.test_client()


def google_sign_in(client, google, email, name="Test User", hd="ncit.edu.np", verified=True, sub=None):
    """Run the full redirect flow and return the callback response."""
    google.next_claims = {"sub": sub or f"g-{email}", "email": email, "name": name,
                          "email_verified": verified, "hd": hd}
    start = client.get("/google/login?next=/dashboard/")
    assert start.status_code == 302
    state = start.headers["Location"].split("state=")[1].split("&")[0]
    return client.get(f"/google/callback?code=ok&state={state}")


def csrf(client) -> dict:
    cookie = client.get_cookie("ncit_csrf")
    return {"X-CSRF-Token": cookie.value if cookie else ""}
