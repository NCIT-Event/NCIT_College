"""Index status and a manual "rebuild now" for Super Admins. Mounted at /api/v1/search/."""

from flask import Blueprint, current_app, jsonify, request
from ncit_common import ApiError, require_role
from sqlalchemy import func, select

from ..db import db
from ..indexer import SOURCES, reindex
from ..models import Document

bp = Blueprint("admin", __name__)


@bp.get("/status")
@require_role("super_admin")
def status():
    rows = db().execute(select(Document.source, func.count(Document.key), func.max(Document.indexed_at)).group_by(Document.source)).all()
    return jsonify(sources={s: {"documents": n, "indexed_at": t.isoformat() if t else None} for s, n, t in rows})


@bp.post("/reindex")
@require_role("super_admin")
def rebuild():
    sources = (request.get_json(silent=True) or {}).get("sources") or None
    if sources and any(s not in SOURCES for s in sources):
        raise ApiError(422, "invalid_source", "Unknown source.")
    return jsonify(result=reindex(db(), current_app.config["FETCH"], sources))
