"""Editing department pages.

A Head of Department edits only their own department (role scope
dept:<slug>); a Super Admin edits every department and adds new ones.
Mounted at /api/v1/academics/.
"""

import re

from flask import Blueprint, current_app, jsonify, request
from ncit_common import ApiError, current_principal, require_auth, require_role
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from .. import serialize
from ..db import db
from ..fields import CHILDREN, COURSE_FIELDS, DEPARTMENT_FIELDS, SUPER_ONLY, apply
from ..media import save_photo
from ..models import Course, Department, Programme

bp = Blueprint("editor", __name__)

SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,38}$")
MAX_COURSES_PER_SEMESTER = 20


def _is_super() -> bool:
    return current_principal().has_role("super_admin")


def _can_edit(slug: str) -> bool:
    return current_principal().has_role("hod", f"dept:{slug}")  # super_admin passes too


def _department(slug: str, *, load_all: bool = False) -> Department:
    stmt = select(Department).where(Department.slug == slug)
    if load_all:
        stmt = stmt.options(selectinload(Department.programmes).selectinload(Programme.courses),
                            selectinload(Department.faculty), selectinload(Department.labs),
                            selectinload(Department.testimonials))
    d = db().scalar(stmt)
    if d is None:
        raise ApiError(404, "department_not_found", "That department doesn't exist.")
    if not _can_edit(slug):
        raise ApiError(403, "forbidden", "You can only edit your own department.")
    return d


def _touch(d: Department) -> None:
    d.updated_by = current_principal().email
    d.updated_at = func.now()


def _emit(event_type: str, d: Department, data: dict | None = None) -> None:
    p = current_principal()
    try:
        current_app.config["EVENTS"].publish(
            event_type, actor={"id": p.user_id, "email": p.email}, entity="department", entity_id=d.slug,
            data={"department": d.name, **(data or {})},
            ip=(request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or ""),
        )
    except Exception:  # an audit outage must not block editing
        current_app.logger.exception("could not publish %s", event_type)


def _editor_view(slug: str):
    db().expire_all()
    return jsonify(department=serialize.department(_department(slug, load_all=True), public=False))


@bp.get("/departments")
@require_auth
def list_departments():
    rows = db().scalars(select(Department).options(selectinload(Department.programmes))
                        .order_by(Department.sort_order, Department.name)).all()
    return jsonify(items=[serialize.summary(d) | {"can_edit": _can_edit(d.slug)} for d in rows if _can_edit(d.slug)])


@bp.post("/departments")
@require_role("super_admin")
def create_department():
    body = request.get_json(silent=True) or {}
    slug = (body.get("slug") or "").strip().lower()
    if not SLUG_RE.match(slug):
        raise ApiError(422, "invalid_slug", "Use a short web address of lowercase letters, numbers and dashes, e.g. mechanical.")
    if db().scalar(select(Department.id).where(Department.slug == slug)):
        raise ApiError(409, "slug_taken", "A department with that web address already exists.")
    d = Department(slug=slug, name="", sort_order=(db().scalar(select(func.max(Department.sort_order))) or 0) + 1)
    apply(d, {"name": DEPARTMENT_FIELDS["name"]}, {"name": body.get("name")}, partial=False)
    _touch(d)
    db().add(d)
    db().commit()
    _emit("department.created", d)
    return _editor_view(slug), 201


@bp.get("/departments/<slug>")
@require_auth
def get_department(slug):
    return _editor_view(slug)


@bp.patch("/departments/<slug>")
@require_auth
def update_department(slug):
    d = _department(slug)
    body = request.get_json(silent=True) or {}
    allowed = None if _is_super() else set(DEPARTMENT_FIELDS) - SUPER_ONLY
    changed = apply(d, DEPARTMENT_FIELDS, body, partial=True, allowed=allowed)
    if changed:
        _touch(d)
        db().commit()
        if "published" in changed:
            _emit("department.published" if d.published else "department.unpublished", d)
        if set(changed) - {"published"}:
            _emit("department.updated", d, {"fields": sorted(set(changed) - {"published"})})
    return _editor_view(slug)


@bp.post("/departments/<slug>/media")
@require_auth
def upload_media(slug):
    _department(slug)
    upload = request.files.get("file")
    if upload is None:
        raise ApiError(422, "no_file", "Choose a photo to upload.")
    url = save_photo(upload, slug)
    return jsonify(url=url), 201


# ---- programmes, faculty, labs, testimonials share one pattern ----

def _child(kind: str):
    if kind not in CHILDREN:
        raise ApiError(404, "not_found", "Not found.")
    return CHILDREN[kind]


@bp.post("/departments/<slug>/<kind>")
@require_auth
def create_child(slug, kind):
    model, spec = _child(kind)
    d = _department(slug)
    item = model(department_id=d.id)
    apply(item, spec, request.get_json(silent=True) or {}, partial=False)
    item.sort_order = (db().scalar(select(func.max(model.sort_order)).where(model.department_id == d.id)) or 0) + 1
    db().add(item)
    _touch(d)
    db().commit()
    _emit(f"{kind}.created", d, {"name": getattr(item, "name", None) or getattr(item, "student_name", "")})
    return jsonify(item=serialize.CHILD_SERIALIZERS[kind](item)), 201


def _owned_child(slug: str, kind: str, item_id: str):
    model, spec = _child(kind)
    d = _department(slug)
    item = db().get(model, item_id)
    if item is None or item.department_id != d.id:
        raise ApiError(404, "item_not_found", "That item was already removed.")
    return d, model, spec, item


@bp.patch("/departments/<slug>/<kind>/<item_id>")
@require_auth
def update_child(slug, kind, item_id):
    d, _model, spec, item = _owned_child(slug, kind, item_id)
    changed = apply(item, spec, request.get_json(silent=True) or {}, partial=True)
    if changed:
        _touch(d)
        db().commit()
        _emit(f"{kind}.updated", d, {"fields": changed})
    return jsonify(item=serialize.CHILD_SERIALIZERS[kind](item))


@bp.delete("/departments/<slug>/<kind>/<item_id>")
@require_auth
def delete_child(slug, kind, item_id):
    d, _model, _spec, item = _owned_child(slug, kind, item_id)
    label = getattr(item, "name", None) or getattr(item, "student_name", "")
    db().delete(item)
    _touch(d)
    db().commit()
    _emit(f"{kind}.deleted", d, {"name": label})
    return jsonify(ok=True)


@bp.post("/departments/<slug>/<kind>/order")
@require_auth
def reorder_children(slug, kind):
    model, _spec = _child(kind)
    d = _department(slug)
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    items = {i.id: i for i in db().scalars(select(model).where(model.department_id == d.id))}
    if sorted(ids) != sorted(items):
        raise ApiError(422, "bad_order", "The list changed while you were editing. Reload and try again.")
    for position, item_id in enumerate(ids, start=1):
        items[item_id].sort_order = position
    _touch(d)
    db().commit()
    return jsonify(ok=True)


@bp.put("/departments/<slug>/programmes/<programme_id>/semesters/<int:semester>")
@require_auth
def replace_semester(slug, programme_id, semester):
    """Replace the whole course list of one semester (the editor saves a table at once)."""
    d, _m, _s, programme = _owned_child(slug, "programmes", programme_id)
    if not 1 <= semester <= programme.duration_years * 2:
        raise ApiError(422, "invalid_semester", f"This programme has {programme.duration_years * 2} semesters.")
    rows = (request.get_json(silent=True) or {}).get("courses") or []
    if len(rows) > MAX_COURSES_PER_SEMESTER:
        raise ApiError(422, "too_many", f"A semester can list at most {MAX_COURSES_PER_SEMESTER} courses.")
    new_courses = []
    for position, row in enumerate(rows, start=1):
        c = Course(programme_id=programme.id, semester=semester, sort_order=position)
        try:
            apply(c, COURSE_FIELDS, {k: row.get(k) for k in COURSE_FIELDS if k in row}, partial=False)
        except ApiError as exc:
            raise ApiError(exc.status, exc.code, f"Row {position}: {exc.message}") from exc
        new_courses.append(c)
    for old in [c for c in programme.courses if c.semester == semester]:
        db().delete(old)
    db().flush()
    db().add_all(new_courses)
    _touch(d)
    db().commit()
    _emit("courses.updated", d, {"programme": programme.name, "semester": semester, "count": len(new_courses)})
    db().refresh(programme)
    return jsonify(item=serialize.programme(programme))
