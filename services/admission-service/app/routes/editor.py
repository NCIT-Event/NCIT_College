"""Admission Officers (and Super Admins): intakes, programmes on offer, and reviewing applications.

Mounted at /api/v1/admissions/. Intake and programme editing comes from
ncit_common.editor; the review routes live under /review/.
"""

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
from ..models import Application, Intake

OFFICER = "admission_officer"  # super_admin passes every role check too
PER_PAGE = 25


def _slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:70] or "intake"
    candidate, n = slug, 2
    while db().scalar(select(Intake.id).where(Intake.slug == candidate)):
        candidate, n = f"{slug}-{n}", n + 1
    return candidate


def _before_create(collection, item):
    if collection == "intakes":
        item.slug = _slugify(item.name)


def _check_rules(collection, item):
    if collection == "intakes" and item.closes_at <= item.opens_at:
        raise ApiError(422, "invalid_window", "“Applications close” must be later than “Applications open”.")
    if collection == "offerings" and db().get(Intake, item.intake_id) is None:
        raise ApiError(422, "invalid_field", "Choose the intake this programme belongs to.")


def _before_delete(collection, item):
    in_use = Application.intake_id if collection == "intakes" else Application.offering_id
    if db().scalar(select(func.count(Application.id)).where(in_use == item.id, Application.status != "draft")):
        raise ApiError(409, "in_use", "People have applied to this. Unpublish it instead of deleting it.")
    if collection == "intakes":
        for a in db().scalars(select(Application).where(Application.intake_id == item.id)):
            db().delete(a)
    else:
        for a in db().scalars(select(Application).where(Application.offering_id == item.id)):
            db().delete(a)


bp = editor_blueprint(COLLECTIONS, role=OFFICER, db=db, service="admissions", check_rules=_check_rules,
                      before_create=_before_create, before_delete=_before_delete)


def _filtered():
    stmt = select(Application).where(Application.status != "draft")
    args = request.args
    if args.get("status"):
        stmt = stmt.where(Application.status == args["status"])
    if args.get("intake_id"):
        stmt = stmt.where(Application.intake_id == args["intake_id"])
    if args.get("offering_id"):
        stmt = stmt.where(or_(Application.offering_id == args["offering_id"],
                              Application.second_choice_id == args["offering_id"]))
    q = (args.get("q") or "").strip().lower()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(func.lower(Application.full_name).like(like), func.lower(Application.email).like(like),
                              func.lower(Application.reference).like(like)))
    return stmt


def _app(app_id: str) -> Application:
    app = db().get(Application, app_id)
    if app is None or app.status == "draft":
        raise ApiError(404, "not_found", "That application isn't available.")
    return app


def _row(a: Application) -> dict:
    return {"id": a.id, "reference": a.reference, "full_name": a.full_name, "email": a.email, "status": a.status,
            "status_label": A.label(a.status), "programme": a.offering.programme, "intake": a.intake.name,
            "grade": a.grade, "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None}


@bp.get("/review/applications")
@require_role(OFFICER)
def review_list():
    stmt = _filtered()
    page = max(int(request.args.get("page", 1) or 1), 1)
    total = db().scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db().scalars(stmt.order_by(Application.submitted_at.desc()).offset((page - 1) * PER_PAGE).limit(PER_PAGE))
    counts = dict(db().execute(select(Application.status, func.count(Application.id))
                               .where(Application.status != "draft").group_by(Application.status)).all())
    return jsonify(items=[_row(a) for a in rows], total=total, page=page, per_page=PER_PAGE, counts=counts,
                   labels=A.LABELS)


@bp.get("/review/applications.csv")
@require_role(OFFICER)
def review_csv():
    out = io.StringIO()
    w = csv.writer(out)
    cols = ["reference", "status", "full_name", "email", "phone", "date_of_birth", "gender", "address", "guardian_name",
            "guardian_phone", "school", "board", "passed_year", "grade", "entrance_score"]
    w.writerow(["Reference", "Status", "Name", "Email", "Phone", "Date of birth", "Gender", "Address", "Guardian",
                "Guardian phone", "School", "Board", "Year passed", "Grade", "Entrance score", "Programme",
                "Second choice", "Submitted (Nepal time)"])
    for a in db().scalars(_filtered().order_by(Application.submitted_at)):
        cells = [A.label(a.status) if c == "status" else str(getattr(a, c) or "") for c in cols]
        cells += [a.offering.programme, a.second_choice.programme if a.second_choice else "",
                  a.submitted_at.astimezone(NEPAL).strftime("%Y-%m-%d %H:%M") if a.submitted_at else ""]
        w.writerow(["'" + c if c[:1] in ("=", "+", "-", "@") else c for c in cells])
    return Response("﻿" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="applications.csv"'})


@bp.get("/review/applications/<app_id>")
@require_role(OFFICER)
def review_detail(app_id):
    return jsonify(item=A.view(_app(app_id), for_office=True))


@bp.post("/review/applications/<app_id>/status")
@require_role(OFFICER)
def review_move(app_id):
    body = request.get_json(silent=True) or {}
    app = A.move(_app(app_id), str(body.get("status") or ""), str(body.get("message") or ""), current_principal(),
                 notify=body.get("notify", True) is not False)
    return jsonify(item=A.view(app, for_office=True))


@bp.patch("/review/applications/<app_id>/note")
@require_role(OFFICER)
def review_note(app_id):
    app = _app(app_id)
    app.officer_note = str((request.get_json(silent=True) or {}).get("officer_note") or "")[:4000]
    db().commit()
    return jsonify(item=A.view(app, for_office=True))


@bp.get("/review/applications/<app_id>/documents/<doc>")
@require_role(OFFICER)
def review_document(app_id, doc):
    app = _app(app_id)
    if doc not in A.DOCUMENTS or not getattr(app, doc):
        raise ApiError(404, "file_not_found", "That file isn't available.")
    ext = "jpg" if A.DOCUMENTS[doc][1] == "image" else "pdf"
    return send_private(current_app.config["PRIVATE_MEDIA_ROOT"], getattr(app, doc), f"{app.reference}-{doc}.{ext}")
