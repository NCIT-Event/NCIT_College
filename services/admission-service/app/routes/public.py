"""Read-only endpoints for the website. Mounted at /api/v1/admissions/public/."""

from flask import Blueprint, jsonify
from sqlalchemy import select

from ..collections import intake, intake_status, now, offering, public
from ..db import db
from ..models import Intake

bp = Blueprint("public", __name__, url_prefix="/public")


@bp.get("/intakes")
def intakes():
    """Published intakes that are open or opening soon, with their programmes."""
    t = now()
    rows = db().scalars(select(Intake).where(Intake.published.is_(True), Intake.closes_at > t).order_by(Intake.opens_at))
    return jsonify(items=[public(intake(x, t)) | {"offerings": [public(offering(o, t)) for o in x.offerings if o.published]}
                          for x in rows if intake_status(x, t) in ("open", "upcoming")])
