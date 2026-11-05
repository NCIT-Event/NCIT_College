"""Signed-in college accounts: join and leave clubs, see your memberships.

Mounted at /api/v1/eca/me/. Any signed-in @ncit.edu.np account may use these.
"""

from flask import Blueprint, jsonify, request
from ncit_common import ApiError, current_principal, require_auth, require_college
from sqlalchemy import select

from .. import memberships
from ..collections import club, now, public
from ..db import db
from ..models import Club, Membership

bp = Blueprint("me", __name__, url_prefix="/me")


def _club(slug: str) -> Club:
    x = db().scalar(select(Club).where(Club.slug == slug, Club.published.is_(True)))
    if x is None:
        raise ApiError(404, "not_found", "This club isn't available.")
    return x


def _mine(x: Club) -> dict | None:
    m = memberships.find(x, current_principal().email)
    return memberships.view(m) if m is not None and m.status in memberships.ACTIVE else None


@bp.get("/memberships")
@require_auth
def my_memberships():
    t = now()
    rows = db().execute(select(Membership, Club).join(Club).where(
        Membership.email == current_principal().email, Membership.status.in_(memberships.ACTIVE + ("rejected",)),
        Club.published.is_(True)).order_by(Club.sort_order)).all()
    return jsonify(items=[memberships.view(m) | {"club": {k: v for k, v in public(club(c, t)).items() if k != "about"}}
                          for m, c in rows])


@bp.get("/clubs/<slug>")
@require_auth
def my_club(slug):
    return jsonify(membership=_mine(_club(slug)))


@bp.post("/clubs/<slug>/join")
@require_college
def join(slug):
    x = _club(slug)
    memberships.join(x, current_principal(), (request.get_json(silent=True) or {}).get("message", ""))
    return jsonify(membership=_mine(x)), 201


@bp.delete("/clubs/<slug>/join")
@require_college
def leave(slug):
    x = _club(slug)
    memberships.leave(x, current_principal())
    return jsonify(membership=None)
