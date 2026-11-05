"""HR Officers (and Super Admins): vacancies and job applications. Mounted at /api/v1/careers/."""

import csv
import io
import re
import unicodedata

from flask import Response, current_app, jsonify, request
from ncit_common import ApiError, current_principal, require_role
from ncit_common.editor import editor_blueprint
from ncit_common.fields import NEPAL
from ncit_common.media import send_private
from sqlalchemy import func, or_, select

from .. import applications as A
from ..collections import COLLECTIONS
from ..db import db
from ..models import Job, JobApplication

HR = "hr_officer"  # super_admin passes every role check too


def _slugify(title):
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "job"
    candidate, n = slug, 2
    while db().scalar(select(Job.id).where(Job.slug == candidate)):
        candidate, n = f"{slug}-{n}", n + 1
    return candidate


def _before_create(collection, item):
    item.slug = _slugify(item.title)


def _before_delete(collection, item):
    if db().scalar(select(func.count(JobApplication.id)).where(JobApplication.job_id == item.id)):
        raise ApiError(409, "in_use", "People have applied for this vacancy. Unpublish it instead of deleting it.")


bp = editor_blueprint(COLLECTIONS, role=HR, db=db, service="careers", before_create=_before_create,
                      before_delete=_before_delete)


def _app(app_id):
    a = db().get(JobApplication, app_id)
    if a is None:
        raise ApiError(404, "not_found", "That application isn't available.")
    return a


def _filtered():
    stmt = select(JobApplication)
    if request.args.get("job_id"):
        stmt = stmt.where(JobApplication.job_id == request.args["job_id"])
    if request.args.get("status"):
        stmt = stmt.where(JobApplication.status == request.args["status"])
    q = (request.args.get("q") or "").strip().lower()
    if q:
        stmt = stmt.where(or_(func.lower(JobApplication.full_name).like(f"%{q}%"), func.lower(JobApplication.email).like(f"%{q}%")))
    return stmt


@bp.get("/review/applications")
@require_role(HR)
def review_list():
    rows = db().scalars(_filtered().order_by(JobApplication.created_at.desc()).limit(500))
    return jsonify(items=[{"id": a.id, "full_name": a.full_name, "email": a.email, "status": a.status,
                           "status_label": A.LABELS.get(a.status), "job": a.job.title, "job_id": a.job_id,
                           "qualification": a.qualification, "created_at": a.created_at.isoformat()} for a in rows],
                   labels=A.LABELS)


@bp.get("/review/applications.csv")
@require_role(HR)
def review_csv():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Vacancy", "Name", "Email", "Phone", "Qualification", "Experience (years)", "Status", "Applied (Nepal time)"])
    for a in db().scalars(_filtered().order_by(JobApplication.created_at)):
        cells = [a.job.title, a.full_name, a.email, a.phone, a.qualification, a.experience_years,
                 A.LABELS.get(a.status, a.status), a.created_at.astimezone(NEPAL).strftime("%Y-%m-%d %H:%M")]
        w.writerow(["'" + c if c[:1] in ("=", "+", "-", "@") else c for c in cells])
    return Response("﻿" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="job-applications.csv"'})


@bp.get("/review/applications/<app_id>")
@require_role(HR)
def review_detail(app_id):
    return jsonify(item=A.view(_app(app_id), for_hr=True))


@bp.post("/review/applications/<app_id>/status")
@require_role(HR)
def review_move(app_id):
    body = request.get_json(silent=True) or {}
    a = A.move(_app(app_id), str(body.get("status") or ""), str(body.get("message") or ""), current_principal(),
               notify=body.get("notify", True) is not False)
    return jsonify(item=A.view(a, for_hr=True))


@bp.patch("/review/applications/<app_id>/note")
@require_role(HR)
def review_note(app_id):
    a = _app(app_id)
    a.hr_note = str((request.get_json(silent=True) or {}).get("hr_note") or "")[:4000]
    db().commit()
    return jsonify(item=A.view(a, for_hr=True))


@bp.get("/review/applications/<app_id>/cv")
@require_role(HR)
def review_cv(app_id):
    a = _app(app_id)
    if not a.cv:
        raise ApiError(404, "file_not_found", "That file isn't available.")
    safe = re.sub(r"[^A-Za-z0-9]+", "-", a.full_name).strip("-") or "applicant"
    return send_private(current_app.config["PRIVATE_MEDIA_ROOT"], a.cv, f"CV-{safe}.pdf")
