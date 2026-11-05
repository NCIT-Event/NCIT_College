"""Account rules shared by the HTTP routes and the CLI."""

from datetime import datetime

from flask import current_app, g, request
from ncit_common import ApiError
from sqlalchemy import func, select

from .models import RoleGrant, User, utcnow
from .roles import ROLES, normalise_scope
from .tokens import revoke_all_for_user


def db():
    if "db" not in g:
        g.db = current_app.extensions["db"]()
    return g.db


def client_ip() -> str:
    # The gateway sets X-Forwarded-For; the first address is the visitor.
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or "")[:64]


def emit(event_type: str, *, actor, entity_id: str, data: dict | None = None, entity: str = "user") -> None:
    actor_info = {"id": actor.id, "email": actor.email} if actor is not None else {}
    try:
        current_app.config["EVENTS"].publish(
            event_type, actor=actor_info, entity=entity, entity_id=entity_id, data=data or {}, ip=client_ip()
        )
    except Exception:  # an audit outage must not block sign-in or access changes
        current_app.logger.exception("could not publish %s", event_type)


def force_token_refresh(user_id: str) -> None:
    """Make the user's current access tokens fail so the next request picks up new roles."""
    current_app.config["JWT_REVOCATION"].revoke_user(user_id)


def domain() -> str:
    return current_app.config["ALLOWED_DOMAIN"]


def validate_internal_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ApiError(422, "invalid_email", "Enter the person's email address.")
    if not email.endswith("@" + domain()):
        raise ApiError(422, "wrong_domain", f"Use an @{domain()} address. Other accounts can't sign in to the dashboard.")
    return email


def grant_role(session, *, email: str, role: str, scope: str | None, expires_at: datetime | None,
               actor: User | None) -> tuple[User, RoleGrant]:
    email = validate_internal_email(email)
    try:
        stored_scope = normalise_scope(role, scope)
    except ValueError as exc:
        raise ApiError(422, "invalid_role", str(exc)) from exc
    if expires_at is not None and expires_at <= utcnow():
        raise ApiError(422, "invalid_expiry", "Choose an expiry date in the future, or leave it empty.")

    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, status="invited")
        session.add(user)
        session.flush()

    grant = next((x for x in user.grants if x.role == role and x.scope == stored_scope), None)
    if grant is None:
        grant = RoleGrant(user_id=user.id, role=role, scope=stored_scope,
                          granted_by=actor.id if actor else None, expires_at=expires_at)
        user.grants.append(grant)
    else:
        grant.expires_at = expires_at
    session.flush()
    return user, grant


def super_admin_count(session, exclude_grant_id: str | None = None) -> int:
    now = utcnow()
    q = (select(func.count()).select_from(RoleGrant).join(User, User.id == RoleGrant.user_id)
         .where(RoleGrant.role == "super_admin", User.status != "suspended",
                (RoleGrant.expires_at.is_(None)) | (RoleGrant.expires_at > now)))
    if exclude_grant_id:
        q = q.where(RoleGrant.id != exclude_grant_id)
    return session.scalar(q) or 0


def revoke_grant(session, user: User, grant: RoleGrant, actor: User) -> None:
    if grant.role == "super_admin" and super_admin_count(session, exclude_grant_id=grant.id) == 0:
        raise ApiError(409, "last_super_admin", "Keep at least one Super Admin. Grant the role to someone else first.")
    if grant.role == "super_admin" and user.id == actor.id:
        raise ApiError(409, "self_revoke", "Ask another Super Admin to remove your own Super Admin role.")
    session.delete(grant)
    session.flush()
    force_token_refresh(user.id)


def suspend(session, user: User, actor: User) -> None:
    if user.id == actor.id:
        raise ApiError(409, "self_suspend", "You can't suspend your own account.")
    if any(x.role == "super_admin" for x in user.active_grants()) and super_admin_count(session) <= 1:
        raise ApiError(409, "last_super_admin", "Keep at least one active Super Admin.")
    user.status = "suspended"
    revoke_all_for_user(session, user.id)
    force_token_refresh(user.id)


def complete_sign_in(session, profile: dict) -> User:
    """Create or update the user for a verified Google profile and return it (active)."""
    cfg = current_app.config
    user = session.scalar(select(User).where(User.google_sub == profile["sub"]))
    if user is None:
        user = session.scalar(select(User).where(User.email == profile["email"]))
    if user is None:
        user = User(email=profile["email"], status="active")
        session.add(user)
        session.flush()
    if user.status == "suspended":
        raise ApiError(403, "account_suspended", "This account is suspended.")

    first_login = user.last_login_at is None
    user.google_sub = profile["sub"]
    user.email = profile["email"]
    user.name = profile.get("name") or user.name
    user.avatar_url = profile.get("picture") or user.avatar_url
    user.status = "active"
    user.last_login_at = utcnow()

    if user.email in cfg["SUPER_ADMIN_EMAILS"] and not any(x.role == "super_admin" for x in user.grants):
        user.grants.append(RoleGrant(user_id=user.id, role="super_admin", scope="*"))
    default_role = cfg["DEFAULT_ROLE"]
    if first_login and not user.grants and default_role in ROLES:
        user.grants.append(RoleGrant(user_id=user.id, role=default_role, scope="*"))
    session.flush()
    return user
