"""Read-only endpoints for the website (cached briefly by the gateway).

Mounted at /api/v1/eca/public/.
"""

from flask import Blueprint, jsonify, request
from ncit_common import ApiError
from sqlalchemy import select

from .. import memberships
from ..collections import CATEGORIES, activity, club, now, public
from ..db import db
from ..models import Activity, Club

bp = Blueprint("public", __name__, url_prefix="/public")


def _live_activities():
    return (select(Activity).join(Club)
            .where(Activity.published.is_(True), Club.published.is_(True))
            .order_by(Activity.happened_on.desc().nulls_last(), Activity.updated_at.desc()))


@bp.get("/clubs")
def clubs():
    t = now()
    stmt = select(Club).where(Club.published.is_(True)).order_by(Club.sort_order)
    category = request.args.get("category")
    if category in CATEGORIES:
        stmt = stmt.where(Club.category == category)
    return jsonify(items=[{k: v for k, v in public(club(x, t)).items() if k != "about"} for x in db().scalars(stmt)])


@bp.get("/clubs/<slug>")
def club_detail(slug):
    t = now()
    x = db().scalar(select(Club).where(Club.slug == slug, Club.published.is_(True)))
    if x is None:
        raise ApiError(404, "not_found", "This club isn't available.")
    acts = db().scalars(_live_activities().where(Activity.club_id == x.id).limit(20))
    return jsonify(club=public(club(x, t)), committee=memberships.committee(x),
                   activities=[public(activity(a, t)) for a in acts])


@bp.get("/activities")
def recent_activities():
    t = now()
    try:
        limit = min(max(int(request.args.get("limit", 6)), 1), 30)
    except ValueError as exc:
        raise ApiError(422, "bad_limit", "Limit must be a number.") from exc
    return jsonify(items=[public(activity(a, t)) for a in db().scalars(_live_activities().limit(limit))])
