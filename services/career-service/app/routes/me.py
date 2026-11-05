"""Applying for jobs. Mounted at /api/v1/careers/me/. Anyone signed in may apply
(outside applicants sign in with an emailed code)."""

from flask import Blueprint, current_app, jsonify, request
from ncit_common import ApiError, current_principal, require_auth
from ncit_common.editor import emit
from ncit_common.media import remove_file, save_pdf, send_private
from ncit_common.notify import notify
from sqlalchemy import select

from .. import applications as A
from ..collections import job_status, now
from ..db import db
from ..models import Job, JobApplication

bp = Blueprint("me", __name__, url_prefix="/me")


def _job(slug):
    x = db().scalar(select(Job).where(Job.slug == slug, Job.published.is_(True)))
    if x is None:
        raise ApiError(404, "not_found", "This vacancy isn't available.")
    return x


def _mine(job_id):
    return db().scalar(select(JobApplication).where(JobApplication.job_id == job_id,
                                                    JobApplication.email == current_principal().email))


@bp.get("/applications")
@require_auth
def my_applications():
    rows = db().scalars(select(JobApplication).where(JobApplication.email == current_principal().email)
                        .order_by(JobApplication.created_at.desc()))
    return jsonify(items=[A.view(a) for a in rows])


@bp.get("/jobs/<slug>")
@require_auth
def my_application_for(slug):
    a = _mine(_job(slug).id)
    return jsonify(application=A.view(a) if a else None)


@bp.post("/jobs/<slug>/apply")
@require_auth
def apply_for(slug):
    """multipart form: full_name, phone, qualification, experience_years, cover_letter, cv (PDF)."""
    job = _job(slug)
    if job_status(job, now()) != "open":
        raise ApiError(409, "closed", "Applications for this vacancy have closed.")
    p, form = current_principal(), request.form
    existing = _mine(job.id)
    if existing is not None and existing.status != "withdrawn":
        raise ApiError(409, "already_applied", "You've already applied for this vacancy.")
    full_name = (form.get("full_name") or "").strip()[:160]
    phone = (form.get("phone") or "").strip()[:30]
    if not full_name:
        raise ApiError(422, "invalid_field", "Full name can't be empty.")
    if not A.PHONE_RE.match(phone):
        raise ApiError(422, "invalid_field", "Enter a phone number we can call you on.")
    if request.files.get("cv") is None:
        raise ApiError(422, "invalid_field", "Attach your CV as a PDF.")
    cv = save_pdf(request.files["cv"], media_root=current_app.config["PRIVATE_MEDIA_ROOT"], service="careers",
                  group="cvs", private=True)
    app = existing or JobApplication(job_id=job.id, email=p.email)
    old_cv = app.cv if existing is not None else None
    app.user_id, app.full_name, app.phone, app.cv = p.user_id, full_name, phone, cv
    app.qualification = (form.get("qualification") or "").strip()[:200]
    app.experience_years = (form.get("experience_years") or "").strip()[:10]
    app.cover_letter = (form.get("cover_letter") or "").strip()[:6000]
    app.message, app.status = "", "submitted"
    app.history = [*(app.history or []), {"at": now().isoformat(), "status": "submitted", "by": p.email, "message": ""}]
    if existing is None:
        db().add(app)
    db().commit()
    if old_cv and old_cv != cv:
        remove_file(current_app.config["PRIVATE_MEDIA_ROOT"], old_cv)  # the CV from the withdrawn application
    A.mail(app, "job_application_received")
    notify(role="hr_officer", kind="action", title=f"New job application: {app.full_name}",
           body=f"{job.title} · {app.qualification or 'no qualification given'}", link="/dashboard/#job-applications")
    emit("job_applications.submitted", entity="job_applications", entity_id=app.id,
         data={"label": "job application", "name": job.title})
    return jsonify(application=A.view(app)), 201


@bp.post("/jobs/<slug>/withdraw")
@require_auth
def withdraw(slug):
    a = _mine(_job(slug).id)
    if a is None or a.status in ("withdrawn", "offered", "rejected"):
        raise ApiError(409, "not_withdrawable", "There's no open application to withdraw.")
    a.status = "withdrawn"
    a.history = [*(a.history or []), {"at": now().isoformat(), "status": "withdrawn", "by": a.email, "message": ""}]
    db().commit()
    return jsonify(application=A.view(a))


@bp.get("/jobs/<slug>/cv")
@require_auth
def my_cv(slug):
    a = _mine(_job(slug).id)
    if a is None or not a.cv:
        raise ApiError(404, "file_not_found", "That file isn't available.")
    return send_private(current_app.config["PRIVATE_MEDIA_ROOT"], a.cv, "cv.pdf")
