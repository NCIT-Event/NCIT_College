"""Email log for Super Admins. Mounted at /api/v1/notify/."""

from flask import Blueprint, current_app, jsonify, request
from ncit_common import ApiError, require_role
from sqlalchemy import func, or_, select

from ..db import db
from ..delivery import REDACTED, attempt, sender_from_config
from ..models import Message

bp = Blueprint("log", __name__)
PER_PAGE = 25


def view(m: Message, full: bool = False) -> dict:
    out = {"id": m.id, "to": m.to, "template": m.template, "service": m.service, "subject": m.subject,
           "status": m.status, "error": m.error, "attempts": m.attempts, "sensitive": m.sensitive,
           "created_at": m.created_at.isoformat() if m.created_at else None,
           "sent_at": m.sent_at.isoformat() if m.sent_at else None}
    if full:
        out["body"] = m.body
    return out


@bp.get("/messages")
@require_role("super_admin")
def messages():
    stmt = select(Message)
    if request.args.get("status"):
        stmt = stmt.where(Message.status == request.args["status"])
    q = (request.args.get("q") or "").strip().lower()
    if q:
        stmt = stmt.where(or_(func.lower(Message.to).like(f"%{q}%"), func.lower(Message.subject).like(f"%{q}%")))
    page = max(int(request.args.get("page", 1) or 1), 1)
    total = db().scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db().scalars(stmt.order_by(Message.created_at.desc()).offset((page - 1) * PER_PAGE).limit(PER_PAGE))
    counts = dict(db().execute(select(Message.status, func.count(Message.id)).group_by(Message.status)).all())
    return jsonify(items=[view(m) for m in rows], total=total, page=page, per_page=PER_PAGE, counts=counts,
                   smtp=bool(current_app.config["SMTP_HOST"]))


@bp.get("/messages/<message_id>")
@require_role("super_admin")
def message(message_id):
    m = db().get(Message, message_id)
    if m is None:
        raise ApiError(404, "not_found", "That email isn't in the log.")
    return jsonify(item=view(m, full=True))


@bp.post("/messages/<message_id>/retry")
@require_role("super_admin")
def retry(message_id):
    m = db().get(Message, message_id)
    if m is None:
        raise ApiError(404, "not_found", "That email isn't in the log.")
    if m.status != "failed":
        raise ApiError(409, "not_failed", "Only failed emails can be sent again.")
    if m.body == REDACTED or not m.body:
        raise ApiError(409, "cannot_retry", "Sign-in code emails aren't sent again. The person can request a new code.")
    attempt(m, sender_from_config(current_app.config), None, current_app.config["MAIL_KEEP_SENSITIVE"])
    db().commit()
    return jsonify(item=view(m, full=True))
