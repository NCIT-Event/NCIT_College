"""Access tokens (JWT, RS256, 15 min) and refresh tokens (opaque, rotated)."""

import base64
import hashlib
import secrets
import time
import uuid
from datetime import timedelta

import jwt
from cryptography.hazmat.primitives import serialization
from flask import current_app
from sqlalchemy import select, update

from .models import RefreshToken, User, utcnow

ACCESS_TTL = 15 * 60
REFRESH_TTL = timedelta(days=7)
# Two tabs refreshing at the same moment both present the same token; the
# second one inside this window is treated as a race, not as theft.
REUSE_GRACE = timedelta(seconds=30)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_access_token(user: User) -> tuple[str, dict]:
    cfg = current_app.config
    now = time.time()
    grants = user.active_grants()
    # A role with an expiry date must stop working when it expires, not up to 15 minutes later:
    # the token ends at the earliest expiry among its roles, and the next refresh leaves that role out.
    exp = now + ACCESS_TTL
    for grant in grants:
        if grant.expires_at is not None:
            exp = min(exp, grant.expires_at.timestamp())
    claims = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "roles": [g.as_claim() for g in grants],
        "jti": uuid.uuid4().hex,
        # fractional iat so a token issued just after a revocation is not caught by it
        "iat": now,
        "exp": max(int(exp), int(now) + 1),
        "iss": cfg["JWT_ISSUER"],
        "aud": cfg["JWT_AUDIENCE"],
    }
    token = jwt.encode(claims, cfg["JWT_PRIVATE_KEY"], algorithm="RS256", headers={"kid": cfg["JWT_KID"]})
    return token, claims


def new_refresh_token(session, user: User, family_id: str | None = None, *, user_agent="", ip="") -> tuple[str, RefreshToken]:
    raw = secrets.token_urlsafe(48)
    record = RefreshToken(
        user_id=user.id,
        token_hash=_hash(raw),
        family_id=family_id or str(uuid.uuid4()),
        expires_at=utcnow() + REFRESH_TTL,
        user_agent=user_agent[:300],
        ip=ip[:64],
    )
    session.add(record)
    session.flush()
    return raw, record


class RefreshError(Exception):
    def __init__(self, code: str, reuse_user_id: str | None = None):
        super().__init__(code)
        self.code = code
        self.reuse_user_id = reuse_user_id


def rotate_refresh_token(session, raw: str, *, user_agent="", ip="") -> tuple[User, str]:
    """Spend `raw` and return (user, new raw token). Raises RefreshError."""
    record = session.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)))
    now = utcnow()
    if record is None:
        raise RefreshError("invalid_refresh")
    if record.revoked_at is not None:
        if record.replaced_by and now - record.revoked_at <= REUSE_GRACE:
            pass  # concurrent refresh from another tab; issue a sibling token below
        else:
            revoke_family(session, record.family_id)
            raise RefreshError("refresh_reused", reuse_user_id=record.user_id)
    if record.expires_at <= now:
        raise RefreshError("refresh_expired")

    user = session.get(User, record.user_id)
    if user is None or user.status != "active":
        raise RefreshError("account_inactive")

    new_raw, new_record = new_refresh_token(session, user, record.family_id, user_agent=user_agent, ip=ip)
    if record.revoked_at is None:
        record.revoked_at = now
        record.replaced_by = new_record.id
    return user, new_raw


def revoke_refresh(session, raw: str | None) -> None:
    if not raw:
        return
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == _hash(raw), RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def revoke_family(session, family_id: str) -> None:
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def revoke_all_for_user(session, user_id: str) -> None:
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def _b64url_uint(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def jwks() -> dict:
    """Public key set other services (or tools) can use to verify access tokens."""
    cfg = current_app.config
    public = serialization.load_pem_public_key(cfg["JWT_PUBLIC_KEY"].encode())
    numbers = public.public_numbers()
    return {"keys": [{
        "kty": "RSA", "use": "sig", "alg": "RS256", "kid": cfg["JWT_KID"],
        "n": _b64url_uint(numbers.n), "e": _b64url_uint(numbers.e),
    }]}
