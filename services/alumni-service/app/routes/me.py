"""The alumnus's own profile. Mounted at /api/v1/alumni/me/."""

from flask import Blueprint, current_app, jsonify, request
from ncit_common import ApiError, current_principal, require_auth
from ncit_common.fields import apply
from ncit_common.media import remove_file, save_image
from sqlalchemy import select

from .. import profiles as P
from ..db import db
from ..models import AlumniProfile

bp = Blueprint("me", __name__, url_prefix="/me")


def _get(create=False):
    p = current_principal()
    profile = db().scalar(select(AlumniProfile).where(AlumniProfile.email == p.email))
    if profile is None and create:
        profile = AlumniProfile(email=p.email, user_id=p.user_id, full_name=p.name if "@" not in (p.name or "@") else "")
        db().add(profile)
    return profile


@bp.get("/profile")
@require_auth
def get_profile():
    p = _get()
    return jsonify(profile=P.view(p) if p else None)


@bp.put("/profile")
@require_auth
def save_profile():
    p = _get(create=True)
    changed = apply(p, P.FIELDS, request.get_json(silent=True) or {}, partial=True)
    P.check(p)
    P.after_edit(p, changed)
    db().commit()
    return jsonify(profile=P.view(p))


@bp.post("/profile/photo")
@require_auth
def photo():
    p = _get(create=True)
    if request.files.get("file") is None:
        raise ApiError(422, "no_file", "Choose a photo to upload.")
    old = p.photo
    p.photo = save_image(request.files["file"], media_root=current_app.config["MEDIA_ROOT"], service="alumni",
                         group="photos", max_side=800)
    db().commit()
    remove_file(current_app.config["MEDIA_ROOT"], old)  # the old photo stops being reachable at its address
    return jsonify(profile=P.view(p))


@bp.post("/profile/submit")
@require_auth
def submit():
    p = _get()
    if p is None:
        raise ApiError(422, "incomplete", "Fill in your details first.")
    P.submit(p)
    return jsonify(profile=P.view(p))
