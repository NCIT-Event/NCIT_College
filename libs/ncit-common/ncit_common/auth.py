"""JWT verification and role checks shared by every service.

auth-service signs access tokens with RS256; other services only hold the
public key (JWT_PUBLIC_KEY) and verify locally, with no call to auth-service.
The token travels in the `ncit_access` cookie or an `Authorization: Bearer`
header. Cookie-authenticated writes must also send the `X-CSRF-Token` header
matching the `ncit_csrf` cookie (double-submit CSRF protection).

Revocation: set `JWT_REVOCATION` to a store from `ncit_common.revocation`;
every request checks it, so a revoked role or session stops working at once.

Roles look like {"role": "hod", "scope": "dept:computer"}; a global role has
scope "*". `super_admin` passes every check.
"""

import hmac
import os
from dataclasses import dataclass, field
from functools import wraps

import jwt
from flask import current_app, g, request

from .errors import ApiError

ACCESS_COOKIE = "ncit_access"
CSRF_COOKIE = "ncit_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
SUPER_ADMIN = "super_admin"


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str
    name: str
    roles: tuple[dict, ...] = field(default_factory=tuple)

    def has_role(self, role: str, scope: str | None = None) -> bool:
        for grant in self.roles:
            if grant.get("role") == SUPER_ADMIN:
                return True
            if grant.get("role") != role:
                continue
            granted_scope = grant.get("scope", "*")
            if scope is None or granted_scope in ("*", scope):
                return True
        return False


def _raw_token() -> tuple[str | None, bool]:
    """Return (token, from_cookie)."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):], False
    return request.cookies.get(ACCESS_COOKIE), True


def check_csrf() -> None:
    if request.method in SAFE_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise ApiError(403, "csrf_failed", "Your session check failed. Reload the page and try again.")


def decode_token(token: str) -> Principal:
    cfg = current_app.config
    try:
        claims = jwt.decode(
            token,
            cfg["JWT_PUBLIC_KEY"],
            algorithms=["RS256"],
            audience=cfg.get("JWT_AUDIENCE", "ncit-web"),
            issuer=cfg.get("JWT_ISSUER", "ncit-auth"),
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ApiError(401, "token_expired", "Your session has expired. Sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise ApiError(401, "invalid_token", "Sign in to continue.") from exc

    store = cfg.get("JWT_REVOCATION")
    if store is not None and store.is_revoked(claims):
        raise ApiError(401, "token_revoked", "Your access has changed. Sign in again.")

    return Principal(
        user_id=claims["sub"],
        email=claims.get("email", ""),
        name=claims.get("name", ""),
        roles=tuple(claims.get("roles", [])),
    )


def current_principal() -> Principal | None:
    return g.get("principal")


def require_auth(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        token, from_cookie = _raw_token()
        if not token:
            raise ApiError(401, "not_signed_in", "Sign in to continue.")
        g.principal = decode_token(token)
        if from_cookie:
            check_csrf()
        return view(*args, **kwargs)

    return wrapper


def require_role(role: str, scope_from: str | None = None, scope_prefix: str = ""):
    """Allow the request only if the user holds `role`.

    `scope_from` names a URL parameter whose value is the scope, so
    `@require_role("hod", scope_from="dept", scope_prefix="dept:")` on
    `/departments/<dept>` lets an HOD edit only their own department.
    """

    def decorator(view):
        @require_auth
        @wraps(view)
        def wrapper(*args, **kwargs):
            scope = None
            if scope_from:
                scope = f"{scope_prefix}{kwargs.get(scope_from)}"
            if not g.principal.has_role(role, scope):
                raise ApiError(403, "forbidden", "You don't have access to this.")
            return view(*args, **kwargs)

        return wrapper

    return decorator


def college_domain() -> str:
    return (current_app.config.get("ALLOWED_DOMAIN") or os.environ.get("ALLOWED_DOMAIN") or "ncit.edu.np").lower()


def require_college(view):
    """Allow only college (@ncit.edu.np) accounts.

    Applicants and alumni sign in with an emailed code from any address, so a
    signed-in user isn't necessarily a member of the college. Use this on
    student and staff actions such as event registration and club membership.
    """

    @require_auth
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.principal.email.lower().endswith("@" + college_domain()):
            raise ApiError(403, "college_account_only",
                           f"Sign in with your @{college_domain()} college account to do this.")
        return view(*args, **kwargs)

    return wrapper
