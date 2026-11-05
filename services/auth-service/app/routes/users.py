"""Users & access: Super Admin grants and revokes roles.

Mounted by the gateway at /api/v1/auth/.
"""

import csv
import io
from datetime import UTC, datetime, time, timedelta, timezone

from flask import Blueprint, jsonify, request
from ncit_common import ApiError, current_principal, require_auth, require_role
from ncit_common.notify import notify
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from ..models import RoleGrant, User, utcnow
from ..roles import ROLES, catalogue
from ..services import db, emit, force_token_refresh, grant_role, revoke_grant, suspend
from .auth import serialize_grant, serialize_user

bp = Blueprint("users", __name__)

MAX_PER_PAGE = 100
MAX_IMPORT_ROWS = 2000


def _actor() -> User:
    actor = db().get(User, current_principal().user_id)
    if actor is None:
        raise ApiError(401, "account_inactive", "Sign in to continue.")
    return actor


def _parse_expiry(value) -> datetime | None:
    """Accept YYYY-MM-DD (end of that day, Nepal time) or empty."""
    if not value:
        return None
    try:
        day = datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise ApiError(422, "invalid_expiry", "Use a date like 2026-12-31 for the expiry.") from exc
    nepal = timezone(timedelta(hours=5, minutes=45))
    return datetime.combine(day, time(23, 59, 59), tzinfo=nepal).astimezone(UTC)


def _load_user(user_id: str) -> User:
    user = db().get(User, user_id)
    if user is None:
        raise ApiError(404, "user_not_found", "That user no longer exists.")
    return user


@bp.get("/roles")
@require_auth
def roles():
    return jsonify(catalogue())


@bp.get("/users")
@require_role("super_admin")
def list_users():
    q = (request.args.get("q") or "").strip().lower()
    role = request.args.get("role") or ""
    status = request.args.get("status") or ""
    page = max(int(request.args.get("page", 1) or 1), 1)
    per_page = min(max(int(request.args.get("per_page", 50) or 50), 1), MAX_PER_PAGE)

    # college accounts by default; ?kind=external lists applicants and alumni (email-code accounts)
    stmt = select(User).where(User.kind == ("external" if request.args.get("kind") == "external" else "internal"))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like), func.lower(User.name).like(like)))
    if role:
        stmt = stmt.where(User.grants.any(RoleGrant.role == role))
    if status:
        stmt = stmt.where(User.status == status)

    total = db().scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db().scalars(
        stmt.options(selectinload(User.grants))
        .order_by(User.status.desc(), User.email)
        .offset((page - 1) * per_page).limit(per_page)
    ).all()
    return jsonify(items=[serialize_user(u) for u in rows], total=total, page=page, per_page=per_page)


@bp.get("/users/summary")
@require_role("super_admin")
def summary():
    now = utcnow()
    invited = db().scalar(select(func.count()).select_from(User).where(User.status == "invited"))
    oldest_invite = db().scalar(select(func.min(User.created_at)).where(User.status == "invited"))
    expiring = db().scalars(
        select(RoleGrant).where(RoleGrant.expires_at.is_not(None), RoleGrant.expires_at > now,
                                RoleGrant.expires_at <= now + timedelta(days=7))
    ).all()
    suspended = db().scalar(select(func.count()).select_from(User).where(User.status == "suspended"))
    return jsonify(
        invited=invited,
        oldest_invite_days=(now - oldest_invite).days if oldest_invite else None,
        expiring=[{"role_name": ROLES.get(g.role, {}).get("name", g.role), "user_id": g.user_id,
                   "expires_at": g.expires_at.isoformat()} for g in expiring],
        suspended=suspended,
    )


@bp.post("/users/grants")
@require_role("super_admin")
def create_grant():
    body = request.get_json(silent=True) or {}
    actor = _actor()
    existed = db().scalar(select(User.id).where(User.email == (body.get("email") or "").strip().lower()))
    user, grant = grant_role(db(), email=body.get("email", ""), role=body.get("role", ""),
                             scope=body.get("scope"), expires_at=_parse_expiry(body.get("expires_at")), actor=actor)
    db().commit()
    force_token_refresh(user.id)
    info = serialize_grant(grant)
    emit("role.granted", actor=actor, entity_id=user.id,
         data={"email": user.email, **info, "invited": existed is None})
    _tell_about_role(user, info, granted=True)
    return jsonify(user=serialize_user(user), invited=existed is None), 201


def _tell_about_role(user, info: dict, *, granted: bool) -> None:
    name = info["role_name"] + (f" ({info['scope_label']})" if info.get("scope_label") else "")
    if granted:
        until = f" until {info['expires_at'][:10]}" if info.get("expires_at") else ""
        notify(to=user.email, kind="success", title=f"You've been given the {name} role{until}",
               body="The matching areas are now in your dashboard menu.", link="/dashboard/")
    else:
        notify(to=user.email, kind="info", title=f"Your {name} role was removed",
               body="Ask a Super Admin if you still need it.", link="/dashboard/")


@bp.delete("/users/<user_id>/grants/<grant_id>")
@require_role("super_admin")
def delete_grant(user_id, grant_id):
    actor = _actor()
    user = _load_user(user_id)
    grant = db().get(RoleGrant, grant_id)
    if grant is None or grant.user_id != user.id:
        raise ApiError(404, "grant_not_found", "That role was already removed.")
    info = serialize_grant(grant)
    revoke_grant(db(), user, grant, actor)
    db().commit()
    emit("role.revoked", actor=actor, entity_id=user.id, data={"email": user.email, **info})
    _tell_about_role(user, info, granted=False)
    return jsonify(user=serialize_user(user))


@bp.post("/users/<user_id>/suspend")
@require_role("super_admin")
def suspend_user(user_id):
    actor = _actor()
    user = _load_user(user_id)
    previous = user.status
    suspend(db(), user, actor)
    db().commit()
    emit("user.suspended", actor=actor, entity_id=user.id, data={"email": user.email, "previous_status": previous})
    return jsonify(user=serialize_user(user))


@bp.post("/users/<user_id>/reactivate")
@require_role("super_admin")
def reactivate_user(user_id):
    actor = _actor()
    user = _load_user(user_id)
    if user.status != "suspended":
        raise ApiError(409, "not_suspended", "This account isn't suspended.")
    user.status = "active" if user.last_login_at else "invited"
    db().commit()
    emit("user.reactivated", actor=actor, entity_id=user.id, data={"email": user.email})
    return jsonify(user=serialize_user(user))


@bp.post("/users/import")
@require_role("super_admin")
def import_users():
    """CSV with columns: email, role, department (for HODs), expires (YYYY-MM-DD)."""
    upload = request.files.get("file")
    text = upload.read().decode("utf-8-sig") if upload else request.get_data(as_text=True)
    if not text.strip():
        raise ApiError(422, "empty_file", "The file is empty. Add a header row: email,role,department,expires")
    reader = csv.DictReader(io.StringIO(text))
    fields = {(f or "").strip().lower() for f in (reader.fieldnames or [])}
    if not {"email", "role"} <= fields:
        raise ApiError(422, "bad_header", "The first row must include the columns email and role.")

    actor = _actor()
    role_by_name = {v["name"].lower(): k for k, v in ROLES.items()}
    results, granted = [], 0
    for line_no, row in enumerate(reader, start=2):
        if line_no - 1 > MAX_IMPORT_ROWS:
            results.append({"line": line_no, "ok": False, "error": f"Stopped after {MAX_IMPORT_ROWS} rows."})
            break
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        role = row.get("role", "").lower().replace(" ", "_")
        role = role if role in ROLES else role_by_name.get(row.get("role", "").lower(), role)
        try:
            with db().begin_nested():
                user, grant = grant_role(db(), email=row.get("email", ""), role=role, scope=row.get("department"),
                                         expires_at=_parse_expiry(row.get("expires")), actor=actor)
            granted += 1
            results.append({"line": line_no, "ok": True, "email": user.email, "role": grant.role})
            force_token_refresh(user.id)
        except ApiError as exc:
            results.append({"line": line_no, "ok": False, "email": row.get("email", ""), "error": exc.message})
    db().commit()
    emit("users.imported", actor=actor, entity_id=actor.id, entity="import",
         data={"granted": granted, "failed": len(results) - granted})
    return jsonify(granted=granted, failed=len(results) - granted, results=results)
