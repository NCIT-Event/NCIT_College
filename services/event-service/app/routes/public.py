"""Read-only endpoints for the website (cached briefly by the gateway).

Mounted at /api/v1/events/public/.
"""

import re
from datetime import UTC, datetime, timedelta

from flask import Blueprint, jsonify, request
from ncit_common import ApiError
from sqlalchemy import func, or_, select

from ..collections import CATEGORIES, event, now, public
from ..db import db
from ..models import Event

bp = Blueprint("public", __name__, url_prefix="/public")

PER_PAGE = 12
NEPAL = timedelta(hours=5, minutes=45)


def _published():
    return select(Event).where(Event.published.is_(True))


def _not_over(t):
    # still on: ends in the future (no end time = treat as 3 hours long)
    return or_(Event.end_at > t, (Event.end_at.is_(None) & (Event.start_at > t - timedelta(hours=3))))


@bp.get("/events")
def events_list():
    """?when=upcoming (default) | past, &category=, &page=, &limit= (home page)."""
    t = now()
    stmt = _published()
    when = request.args.get("when", "upcoming")
    if when == "past":
        stmt, order = stmt.where(~_not_over(t)), [Event.start_at.desc()]
    else:
        stmt, order = stmt.where(_not_over(t)), [Event.start_at]
    category = request.args.get("category")
    if category in CATEGORIES:
        stmt = stmt.where(Event.category == category)
    try:
        page = max(int(request.args.get("page", 1) or 1), 1)
        per_page = min(max(int(request.args.get("limit", PER_PAGE) or PER_PAGE), 1), 50)
    except ValueError as exc:
        raise ApiError(422, "bad_page", "Page must be a number.") from exc
    total = db().scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db().scalars(stmt.order_by(*order).offset((page - 1) * per_page).limit(per_page)).all()
    return jsonify(items=[public(event(x, t)) for x in rows], total=total, page=page, per_page=per_page)


@bp.get("/events/<slug>")
def event_detail(slug):
    t = now()
    x = db().scalar(_published().where(Event.slug == slug))
    if x is None:
        raise ApiError(404, "not_found", "This event isn't available.")
    return jsonify(event=public(event(x, t)))


@bp.get("/calendar")
def calendar():
    """Events in a month (Nepal time): ?month=2026-12. Defaults to this month."""
    month = request.args.get("month") or (now() + NEPAL).strftime("%Y-%m")
    if not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", month):
        raise ApiError(422, "bad_month", "Month must look like 2026-12.")
    year, mon = map(int, month.split("-"))
    start = datetime(year, mon, 1, tzinfo=UTC) - NEPAL
    end = datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=UTC) - NEPAL
    stmt = _published().where(Event.start_at < end,
                              or_(Event.end_at >= start, Event.end_at.is_(None) & (Event.start_at >= start)))
    t = now()
    items = [{k: v for k, v in public(event(x, t)).items() if k not in ("body", "summary")}
             for x in db().scalars(stmt.order_by(Event.start_at))]
    return jsonify(month=month, items=items)
