"""The bell: a signed-in person's own notifications. Mounted at /api/v1/notify/me/.

Anyone signed in (staff, students, applicants, alumni) can use these; each
person only ever sees and changes their own (see app/inbox.py for the rules).
"""

from flask import Blueprint, jsonify, request
from ncit_common import ApiError, current_principal, require_auth

from .. import inbox
from ..db import db

bp = Blueprint("me", __name__, url_prefix="/me")


@bp.get("/notifications")
@require_auth
def notifications():
    p = current_principal()
    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = min(max(int(request.args.get("per_page", 10)), 1), 50)
    except ValueError as exc:
        raise ApiError(422, "invalid_field", "page and per_page must be numbers.") from exc
    rows, more = inbox.listing(db(), p, page, per_page, unread_only=request.args.get("unread") == "1")
    resp = jsonify(items=[inbox.view(n, read) for n, read in rows], more=more, page=page,
                   unread=inbox.unread_count(db(), p))
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


@bp.get("/notifications/unread")
@require_auth
def unread():
    resp = jsonify(unread=inbox.unread_count(db(), current_principal()))
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


@bp.post("/notifications/read")
@require_auth
def read():
    """{"ids": [...]} marks those; {"all": true} marks everything."""
    body = request.get_json(silent=True) or {}
    p = current_principal()
    if body.get("all") is True:
        marked = inbox.mark_read(db(), p, None)
    elif isinstance(body.get("ids"), list):
        marked = inbox.mark_read(db(), p, body["ids"])
    else:
        raise ApiError(422, "invalid_field", 'Send {"ids": [...]} or {"all": true}.')
    db().commit()
    return jsonify(marked=marked, unread=inbox.unread_count(db(), p))
