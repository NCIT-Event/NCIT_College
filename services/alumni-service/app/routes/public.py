"""The public alumni directory (verified alumni who agreed to be listed). Mounted at /api/v1/alumni/public/."""

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, select

from ..db import db
from ..models import AlumniProfile
from ..profiles import public_card

bp = Blueprint("public", __name__, url_prefix="/public")
PER_PAGE = 24


def _listed():
    return select(AlumniProfile).where(AlumniProfile.status == "verified", AlumniProfile.show_in_directory.is_(True))


@bp.get("/directory")
def directory():
    stmt = _listed()
    q = (request.args.get("q") or "").strip().lower()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(func.lower(AlumniProfile.full_name).like(like), func.lower(AlumniProfile.employer).like(like),
                              func.lower(AlumniProfile.current_role).like(like), func.lower(AlumniProfile.city).like(like)))
    if request.args.get("programme"):
        stmt = stmt.where(AlumniProfile.programme == request.args["programme"])
    if request.args.get("year"):
        stmt = stmt.where(AlumniProfile.graduation_year == request.args["year"])
    page = max(int(request.args.get("page", 1) or 1), 1)
    total = db().scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db().scalars(stmt.order_by(AlumniProfile.graduation_year.desc(), AlumniProfile.full_name)
                        .offset((page - 1) * PER_PAGE).limit(PER_PAGE))
    programmes = [p for (p,) in db().execute(select(AlumniProfile.programme).where(
        AlumniProfile.status == "verified", AlumniProfile.show_in_directory.is_(True)).distinct().order_by(AlumniProfile.programme))]
    verified = db().scalar(select(func.count(AlumniProfile.id)).where(AlumniProfile.status == "verified"))
    return jsonify(items=[public_card(p) for p in rows], total=total, page=page, per_page=PER_PAGE,
                   programmes=programmes, verified_total=verified)


@bp.get("/featured")
def featured():
    rows = db().scalars(_listed().where(AlumniProfile.featured.is_(True)).order_by(AlumniProfile.verified_at.desc()).limit(4))
    return jsonify(items=[public_card(p) for p in rows])
