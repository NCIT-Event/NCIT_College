"""The applicant's own applications. Mounted at /api/v1/admissions/me/.

Anyone signed in may apply: applicants sign in with an emailed code (no
college account needed); a college account works too.
"""

from flask import Blueprint, current_app, jsonify, request
from ncit_common import ApiError, current_principal, require_auth
from ncit_common.fields import apply
from ncit_common.media import remove_file, save_image, save_pdf, send_private
from sqlalchemy import select

from .. import applications as A
from ..collections import intake_status, now
from ..db import db
from ..models import Application, Intake, Offering

bp = Blueprint("me", __name__, url_prefix="/me")


def _mine(app_id: str) -> Application:
    app = db().get(Application, app_id)
    if app is None or app.email != current_principal().email:
        raise ApiError(404, "not_found", "That application isn't available.")
    return app


@bp.get("/applications")
@require_auth
def my_applications():
    rows = db().scalars(select(Application).where(Application.email == current_principal().email)
                        .order_by(Application.created_at.desc()))
    return jsonify(items=[A.view(a) for a in rows])


@bp.post("/applications")
@require_auth
def start():
    body = request.get_json(silent=True) or {}
    offering = db().get(Offering, str(body.get("offering_id") or ""))
    if offering is None or not offering.published or not offering.intake.published:
        raise ApiError(422, "invalid_field", "Choose a programme to apply for.")
    if intake_status(offering.intake, now()) != "open":
        raise ApiError(409, "intake_closed", "Applications for this intake are not open.")
    p = current_principal()
    existing = db().scalar(select(Application).where(Application.email == p.email,
                                                     Application.intake_id == offering.intake_id))
    if existing is not None:
        if existing.status == "withdrawn":
            existing.status, existing.offering_id = "draft", offering.id
            db().commit()
            return jsonify(item=A.view(existing)), 200
        raise ApiError(409, "already_applied", "You already have an application for this intake. Open it below.")
    app = Application(email=p.email, user_id=p.user_id, intake_id=offering.intake_id, offering_id=offering.id,
                      full_name=p.name if "@" not in (p.name or "@") else "")
    db().add(app)
    db().commit()
    return jsonify(item=A.view(app)), 201


@bp.get("/applications/<app_id>")
@require_auth
def detail(app_id):
    return jsonify(item=A.view(_mine(app_id)))


@bp.patch("/applications/<app_id>")
@require_auth
def update(app_id):
    app = _mine(app_id)
    if app.status not in A.EDITABLE:
        raise ApiError(409, "not_editable", "This application has been sent and can't be changed now.")
    apply(app, A.APPLICANT_FIELDS, request.get_json(silent=True) or {}, partial=True)
    A.check_fields(app)
    db().commit()
    return jsonify(item=A.view(app))


@bp.post("/applications/<app_id>/documents/<doc>")
@require_auth
def upload(app_id, doc):
    app = _mine(app_id)
    if doc not in A.DOCUMENTS:
        raise ApiError(404, "not_found", "Unknown document.")
    if app.status not in A.EDITABLE:
        raise ApiError(409, "not_editable", "This application has been sent and can't be changed now.")
    file = request.files.get("file")
    if file is None:
        raise ApiError(422, "no_file", "Choose a file to upload.")
    root = current_app.config["PRIVATE_MEDIA_ROOT"]
    kind = A.DOCUMENTS[doc][1]
    save = save_image if kind == "image" else save_pdf
    old = getattr(app, doc)
    setattr(app, doc, save(file, media_root=root, service="admissions", group="documents", private=True))
    db().commit()
    remove_file(root, old)  # the replaced document doesn't stay on disk
    return jsonify(item=A.view(app))


@bp.get("/applications/<app_id>/documents/<doc>")
@require_auth
def download(app_id, doc):
    app = _mine(app_id)
    if doc not in A.DOCUMENTS or not getattr(app, doc):
        raise ApiError(404, "file_not_found", "That file isn't available.")
    return send_private(current_app.config["PRIVATE_MEDIA_ROOT"], getattr(app, doc),
                        f"{doc}.{'jpg' if A.DOCUMENTS[doc][1] == 'image' else 'pdf'}")


@bp.post("/applications/<app_id>/submit")
@require_auth
def submit(app_id):
    return jsonify(item=A.view(A.submit(_mine(app_id), current_principal())))


@bp.post("/applications/<app_id>/withdraw")
@require_auth
def withdraw(app_id):
    return jsonify(item=A.view(A.withdraw(_mine(app_id), current_principal())))


@bp.get("/intakes/<intake_id>")
@require_auth
def intake_for_form(intake_id):
    """Programmes to choose from while filling in an application."""
    x = db().get(Intake, intake_id)
    if x is None or not x.published:
        raise ApiError(404, "not_found", "That intake isn't available.")
    return jsonify(items=[{"id": o.id, "programme": o.programme} for o in x.offerings if o.published])
