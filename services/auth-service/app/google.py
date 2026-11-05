"""Google OpenID Connect: authorization-code flow with PKCE, state and nonce.

The ID token is verified against Google's published keys. A sign-in is
accepted only when Google says the email is verified, the Workspace domain
claim (`hd`) is the college domain, and the address itself ends with it.
"""

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import jwt
import requests

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ("https://accounts.google.com", "accounts.google.com")


class SignInRefused(Exception):
    """Raised with a short code the login page turns into a message."""

    def __init__(self, code: str, email: str = ""):
        super().__init__(code)
        self.code = code
        self.email = email


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class GoogleClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, domain: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.domain = domain.lower()
        self._jwks = jwt.PyJWKClient(JWKS_URL, cache_keys=True, lifespan=3600)

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)

    def authorization_url(self, state: str, nonce: str, code_challenge: str) -> str:
        return AUTH_URL + "?" + urlencode({
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            # Hint only: shows NCIT accounts first. The real check is in verify().
            "hd": self.domain,
            "prompt": "select_account",
        })

    def exchange_code(self, code: str, code_verifier: str) -> str:
        res = requests.post(TOKEN_URL, data={
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        }, timeout=10)
        if res.status_code != 200:
            raise SignInRefused("google_exchange_failed")
        id_token = res.json().get("id_token")
        if not id_token:
            raise SignInRefused("google_exchange_failed")
        return id_token

    def verify(self, id_token: str, nonce: str) -> dict:
        try:
            key = self._jwks.get_signing_key_from_jwt(id_token)
            claims = jwt.decode(id_token, key.key, algorithms=["RS256"], audience=self.client_id,
                                issuer=ISSUERS, leeway=30)
        except jwt.PyJWTError as exc:
            raise SignInRefused("invalid_google_token") from exc
        return self.check_claims(claims, nonce)

    def check_claims(self, claims: dict, nonce: str) -> dict:
        email = (claims.get("email") or "").strip().lower()
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise SignInRefused("invalid_google_token", email)
        if not claims.get("email_verified"):
            raise SignInRefused("email_not_verified", email)
        if (claims.get("hd") or "").lower() != self.domain or not email.endswith("@" + self.domain):
            raise SignInRefused("wrong_domain", email)
        return {"sub": claims["sub"], "email": email, "name": claims.get("name", ""),
                "picture": claims.get("picture", "")}
