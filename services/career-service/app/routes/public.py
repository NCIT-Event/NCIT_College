"""Read-only endpoints for the website. Mounted at /api/v1/careers/public/."""

from flask import Blueprint, jsonify
from ncit_common import ApiError
from sqlalchemy import select

from ..collections import job, now, public
from ..db import db
from ..models import Job

bp = Blueprint("public", __name__, url_prefix="/public")


@bp.get("/jobs")
def jobs():
    t = now()
    rows = db().scalars(select(Job).where(Job.published.is_(True), Job.closes_at > t).order_by(Job.closes_at))
    return jsonify(items=[{k: v for k, v in public(job(x, t)).items() if k not in ("description", "requirements")}
                          for x in rows])


@bp.get("/jobs/<slug>")
def job_detail(slug):
    t = now()
    x = db().scalar(select(Job).where(Job.slug == slug, Job.published.is_(True)))
    if x is None:
        raise ApiError(404, "not_found", "This vacancy isn't available.")
    return jsonify(job=public(job(x, t)))
