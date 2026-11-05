"""Sign-in, session refresh, sign-out and the current user.

Mounted by the gateway at /api/v1/auth/.
"""

import re
import secrets

import jwt
from flask import Blueprint, current_app, jsonify, redirect, request, session
from ncit_common import ApiError, check_csrf, current_principal, require_auth
from ncit_common.auth import ACCESS_COOKIE, CSRF_COOKIE

from ..google import SignInRefused, pkce_pair
from ..models import User
from ..roles import EXTERNAL_ROLES, ROLES, scope_label
from ..services import client_ip, complete_sign_in, db, emit
from ..tokens import (
    ACCESS_TTL,
    REFRESH_TTL,
    RefreshError,
    issue_access_token,
    jwks,
    new_refresh_token,
    revoke_refresh,
    rotate_refresh_token,
)

bp = Blueprint("auth", __name__)

REFRESH_COOKIE = "ncit_refresh"
LOGIN_PAGE = "/login.html"
DEFAULT_NEXT = "/dashboard/"


_SAFE_NEXT_RE = re.compile(r"^/(?![/\\])[^\x00-\x20\x7f\\]*$")


def _safe_next(value: str | None) -> str:
    """Only same-site paths, never //host or scheme URLs (open-redirect guard).

    Browsers read "\\" as "/" and silently drop tabs and line breaks, so "/\\evil.com" and
    "/<tab>/evil.com" both become "//evil.com". Any whitespace, control character or backslash
    is refused, and the path must not start with a second slash.
    """
    if value and len(value) <= 500 and _SAFE_NEXT_RE.match(value):
        return value
    return DEFAULT_NEXT


def _set_session_cookies(resp, access: str, refresh: str | None):
    cfg = current_app.config
    secure = cfg["COOKIE_SECURE"]
    resp.set_cookie(ACCESS_COOKIE, access, max_age=ACCESS_TTL, path="/", secure=secure, httponly=True, samesite="Lax")
    if refresh:
        resp.set_cookie(REFRESH_COOKIE, refresh, max_age=int(REFRESH_TTL.total_seconds()),
                        path=cfg["AUTH_COOKIE_PATH"], secure=secure, httponly=True, samesite="Lax")
    csrf = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
    # readable by the page's JS, which echoes it in the X-CSRF-Token header
    resp.set_cookie(CSRF_COOKIE, csrf, max_age=int(REFRESH_TTL.total_seconds()), path="/",
                    secure=secure, httponly=False, samesite="Lax")
    return resp


def _clear_session_cookies(resp):
    cfg = current_app.config
    resp.delete_cookie(ACCESS_COOKIE, path="/")
    resp.delete_cookie(REFRESH_COOKIE, path=cfg["AUTH_COOKIE_PATH"])
    resp.delete_cookie(CSRF_COOKIE, path="/")
    return resp


def _start_session(user: User):
    access, _ = issue_access_token(user)
    refresh, _ = new_refresh_token(db(), user, user_agent=request.headers.get("User-Agent", ""), ip=client_ip())
    db().commit()
    return access, refresh


def _refuse(code: str, email: str = ""):
    emit("user.sign_in_refused", actor=None, entity_id=email or "unknown", data={"reason": code, "email": email})
    return redirect(f"{LOGIN_PAGE}?error={code}")


@bp.get("/config")
def config():
    cfg = current_app.config
    return jsonify(
        google=current_app.extensions["google"].configured,
        dev_login=cfg["DEV_LOGIN"],
        domain=cfg["ALLOWED_DOMAIN"],
    )


@bp.get("/google/login")
def google_login():
    google = current_app.extensions["google"]
    if not google.configured:
        return redirect(f"{LOGIN_PAGE}?error=google_not_configured")
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    verifier, challenge = pkce_pair()
    session.clear()
    session.permanent = True
    session.update(oauth_state=state, oauth_nonce=nonce, oauth_verifier=verifier,
                   oauth_next=_safe_next(request.args.get("next")))
    return redirect(google.authorization_url(state, nonce, challenge))


@bp.get("/google/callback")
def google_callback():
    google = current_app.extensions["google"]
    state = session.pop("oauth_state", None)
    nonce = session.pop("oauth_nonce", None)
    verifier = session.pop("oauth_verifier", None)
    next_url = _safe_next(session.pop("oauth_next", DEFAULT_NEXT))

    if request.args.get("error"):
        return redirect(f"{LOGIN_PAGE}?error=cancelled")
    if not state or not secrets.compare_digest(state, request.args.get("state", "")):
        return _refuse("state_mismatch")
    try:
        id_token = google.exchange_code(request.args.get("code", ""), verifier)
        profile = google.verify(id_token, nonce)
    except SignInRefused as exc:
        return _refuse(exc.code, exc.email)

    try:
        user = complete_sign_in(db(), profile)
    except ApiError as exc:
        db().rollback()
        return _refuse(exc.code, profile["email"])

    access, refresh = _start_session(user)
    emit("user.signed_in", actor=user, entity_id=user.id, data={"method": "google"})
    return _set_session_cookies(redirect(next_url), access, refresh)


@bp.post("/dev/login")
def dev_login():
    """Local development only: sign in as any college address without Google."""
    if not current_app.config["DEV_LOGIN"]:
        raise ApiError(404, "not_found", "Not found.")
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    domain = current_app.config["ALLOWED_DOMAIN"]
    if not email.endswith("@" + domain):
        emit("user.sign_in_refused", actor=None, entity_id=email or "unknown",
             data={"reason": "wrong_domain", "email": email, "method": "dev"})
        raise ApiError(403, "wrong_domain", f"Only @{domain} accounts can sign in.")
    name = body.get("name") or email.split("@")[0].replace(".", " ").title()
    profile = {"sub": f"dev-{email}", "email": email, "name": name, "picture": ""}
    try:
        user = complete_sign_in(db(), profile)
    except ApiError:
        db().rollback()
        raise
    access, refresh = _start_session(user)
    emit("user.signed_in", actor=user, entity_id=user.id, data={"method": "dev"})
    return _set_session_cookies(jsonify(ok=True), access, refresh)


@bp.post("/refresh")
def refresh():
    check_csrf()
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise ApiError(401, "not_signed_in", "Sign in to continue.")
    try:
        user, new_raw = rotate_refresh_token(db(), raw, user_agent=request.headers.get("User-Agent", ""), ip=client_ip())
    except RefreshError as exc:
        db().commit()  # keep the family revocation on reuse
        if exc.reuse_user_id:
            current_app.config["JWT_REVOCATION"].revoke_user(exc.reuse_user_id)
            emit("session.refresh_reused", actor=None, entity_id=exc.reuse_user_id)
        resp = jsonify(error={"code": exc.code, "message": "Your session has ended. Sign in again."})
        return _clear_session_cookies(resp), 401
    access, _ = issue_access_token(user)
    db().commit()
    return _set_session_cookies(jsonify(ok=True), access, new_raw)


@bp.post("/logout")
def logout():
    check_csrf()
    revoke_refresh(db(), request.cookies.get(REFRESH_COOKIE))
    db().commit()
    token = request.cookies.get(ACCESS_COOKIE)
    if token:
        cfg = current_app.config
        try:
            claims = jwt.decode(token, cfg["JWT_PUBLIC_KEY"], algorithms=["RS256"], audience=cfg["JWT_AUDIENCE"],
                                issuer=cfg["JWT_ISSUER"], options={"verify_exp": False})
        except jwt.PyJWTError:
            claims = None
        if claims:
            cfg["JWT_REVOCATION"].revoke_token(claims.get("jti", ""))
            emit("session.signed_out", actor=None, entity_id=claims.get("sub", ""))
    return _clear_session_cookies(jsonify(ok=True))


@bp.get("/me")
@require_auth
def me():
    user = db().get(User, current_principal().user_id)
    if user is None or user.status != "active":
        raise ApiError(401, "account_inactive", "Sign in to continue.")
    return jsonify(user=serialize_user(user))


@bp.get("/.well-known/jwks.json")
def well_known_jwks():
    return jsonify(jwks())


def serialize_grant(grant) -> dict:
    return {
        "id": grant.id,
        "role": grant.role,
        "role_name": ROLES.get(grant.role, {}).get("name") or EXTERNAL_ROLES.get(grant.role, grant.role),
        "scope": grant.scope,
        "scope_label": scope_label(grant.scope),
        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
    }


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name or user.email.split("@")[0],
        "avatar_url": user.avatar_url,
        "status": user.status,
        "kind": user.kind,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "roles": [serialize_grant(x) for x in sorted(user.active_grants(), key=lambda x: x.created_at)],
    }

