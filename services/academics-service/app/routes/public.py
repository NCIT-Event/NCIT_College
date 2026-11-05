"""Read-only endpoints for the public website (cached by the gateway).

Mounted at /api/v1/academics/public/.
"""

from flask import Blueprint, jsonify
from ncit_common import ApiError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .. import serialize
from ..db import db
from ..models import Department, Faculty, Programme

bp = Blueprint("public", __name__, url_prefix="/public")


@bp.get("/departments")
def departments():
    rows = db().scalars(
        select(Department).where(Department.published.is_(True))
        .options(selectinload(Department.programmes))
        .order_by(Department.sort_order, Department.name)
    ).all()
    return jsonify(items=[serialize.summary(d) for d in rows])


@bp.get("/departments/<slug>")
def department(slug):
    d = db().scalar(
        select(Department).where(Department.slug == slug, Department.published.is_(True))
        .options(selectinload(Department.programmes).selectinload(Programme.courses),
                 selectinload(Department.faculty), selectinload(Department.labs),
                 selectinload(Department.testimonials))
    )
    if d is None:
        raise ApiError(404, "department_not_found", "This department page isn't available.")
    return jsonify(department=serialize.department(d, public=True))


@bp.get("/faculty")
def faculty():
    """Faculty directory: everyone listed on a published department page, A to Z."""
    rows = db().execute(
        select(Faculty, Department).join(Department, Faculty.department_id == Department.id)
        .where(Department.published.is_(True)).order_by(Faculty.name)
    ).all()
    return jsonify(items=[serialize.faculty(f) | {"department": {"slug": d.slug, "name": d.name}} for f, d in rows])
