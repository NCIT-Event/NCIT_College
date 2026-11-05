"""ECA Admins (and Super Admins): manage clubs, their activities and members.

Mounted at /api/v1/eca/. Club and activity CRUD comes from ncit_common.editor;
this file adds the club rules and membership decisions.
"""

import re
import unicodedata

from flask import jsonify, request
from ncit_common import ApiError, current_principal, require_role
from ncit_common.editor import editor_blueprint
from sqlalchemy import select

from .. import memberships
from ..collections import COLLECTIONS
from ..db import db
from ..models import Club, Membership

EDITOR_ROLE = "eca_admin"  # super_admin passes every role check too
STATUS_ORDER = {"pending": 0, "approved": 1, "rejected": 2, "left": 3}


def _slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "club"
    candidate, n = slug, 2
    while db().scalar(select(Club.id).where(Club.slug == candidate)):
        candidate, n = f"{slug}-{n}", n + 1
    return candidate


def _before_create(collection: str, item) -> None:
    if collection == "clubs":
        item.slug = _slugify(item.name)


def _check_rules(collection: str, item) -> None:
    if collection == "activities" and db().get(Club, item.club_id) is None:
        raise ApiError(422, "invalid_field", "Choose the club this activity belongs to.")


bp = editor_blueprint(COLLECTIONS, role=EDITOR_ROLE, db=db, service="eca",
                      check_rules=_check_rules, before_create=_before_create)


def _club(club_id: str) -> Club:
    x = db().get(Club, club_id)
    if x is None:
        raise ApiError(404, "item_not_found", "That club was already removed.")
    return x


@bp.get("/clubs/<club_id>/members")
@require_role(EDITOR_ROLE)
def members(club_id):
    x = _club(club_id)
    rows = db().scalars(select(Membership).where(Membership.club_id == x.id).order_by(Membership.created_at)).all()
    rows = sorted(rows, key=lambda m: STATUS_ORDER.get(m.status, 9))
    return jsonify(club={"id": x.id, "name": x.name}, items=[memberships.view(m) for m in rows])


@bp.patch("/clubs/<club_id>/members/<member_id>")
@require_role(EDITOR_ROLE)
def decide(club_id, member_id):
    x = _club(club_id)
    m = db().get(Membership, member_id)
    if m is None or m.club_id != x.id:
        raise ApiError(404, "item_not_found", "That membership was already removed.")
    m = memberships.decide(x, m, request.get_json(silent=True) or {}, current_principal().email)
    return jsonify(item=memberships.view(m))


@bp.get("/requests/pending")
@require_role(EDITOR_ROLE)
def pending():
    """Every request still waiting, across all clubs (oldest first)."""
    rows = db().execute(select(Membership, Club).join(Club).where(Membership.status == "pending")
                        .order_by(Membership.created_at)).all()
    return jsonify(items=[memberships.view(m) | {"club": {"id": c.id, "name": c.name, "slug": c.slug}}
                          for m, c in rows])
