"""Alumni Coordinators (and Super Admins): verify alumni and choose who's featured. Mounted at /api/v1/alumni/."""

import csv
import io

from flask import Blueprint, Response, jsonify, request
from ncit_common import ApiError, current_principal, require_role
from sqlalchemy import func, or_, select

from .. import profiles as P
from ..db import db
from ..models import AlumniProfile

bp = Blueprint("editor", __name__)
COORDINATOR = "alumni_coordinator"  # super_admin passes every role check too


def _profile(pid):
    p = db().get(AlumniProfile, pid)
    if p is None:
        raise ApiError(404, "not_found", "That profile isn't available.")
    return p


def _filtered():
    stmt = select(AlumniProfile).where(AlumniProfile.status != "draft")
    if request.args.get("status"):
        stmt = stmt.where(AlumniProfile.status == request.args["status"])
    if request.args.get("year"):
        stmt = stmt.where(AlumniProfile.graduation_year == request.args["year"])
    q = (request.args.get("q") or "").strip().lower()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(func.lower(AlumniProfile.full_name).like(like), func.lower(AlumniProfile.email).like(like),
                              func.lower(AlumniProfile.registration_no).like(like)))
    return stmt


@bp.get("/review/profiles")
@require_role(COORDINATOR)
def review_list():
    rows = db().scalars(_filtered().order_by(AlumniProfile.status != "pending", AlumniProfile.submitted_at).limit(500))
    counts = dict(db().execute(select(AlumniProfile.status, func.count(AlumniProfile.id))
                               .where(AlumniProfile.status != "draft").group_by(AlumniProfile.status)).all())
    return jsonify(items=[P.view(p, for_coordinator=True) for p in rows], counts=counts, labels=P.LABELS)


@bp.post("/review/profiles/<pid>/status")
@require_role(COORDINATOR)
def review_decide(pid):
    body = request.get_json(silent=True) or {}
    p = _profile(pid)
    P.decide(p, str(body.get("status") or ""), str(body.get("message") or ""), current_principal())
    return jsonify(item=P.view(p, for_coordinator=True))


@bp.patch("/review/profiles/<pid>")
@require_role(COORDINATOR)
def review_feature(pid):
    p = _profile(pid)
    featured = bool((request.get_json(silent=True) or {}).get("featured"))
    if featured and not (p.status == "verified" and p.show_in_directory):
        raise ApiError(409, "not_listed", "Only verified alumni who agreed to be listed can be featured.")
    p.featured = featured
    db().commit()
    return jsonify(item=P.view(p, for_coordinator=True))


@bp.get("/review/profiles.csv")
@require_role(COORDINATOR)
def review_csv():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Name", "Email", "Phone", "Programme", "Year", "PU registration", "Role", "Organisation", "City", "Status"])
    for p in db().scalars(_filtered().order_by(AlumniProfile.graduation_year, AlumniProfile.full_name)):
        cells = [p.full_name, p.email, p.phone, p.programme, p.graduation_year, p.registration_no, p.current_role,
                 p.employer, p.city, P.LABELS.get(p.status, p.status)]
        w.writerow(["'" + c if c[:1] in ("=", "+", "-", "@") else c for c in cells])
    return Response("﻿" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="alumni.csv"'})
