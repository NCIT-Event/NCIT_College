"""Event Admins (and Super Admins): manage events and see who registered.

Mounted at /api/v1/events/. Event CRUD comes from ncit_common.editor; this
file adds the event rules and the registration list.
"""

import csv
import io
import re
import unicodedata

from flask import Response, jsonify, request
from ncit_common import ApiError, require_role
from ncit_common.editor import editor_blueprint, emit
from ncit_common.fields import NEPAL
from ncit_common.notify import notify
from sqlalchemy import select

from .. import registrations as regs
from ..collections import COLLECTIONS
from ..db import db
from ..models import Event, Registration

EDITOR_ROLE = "event_admin"  # super_admin passes every role check too
NEPAL_FMT = "%Y-%m-%d %H:%M"


def _slugify(title: str) -> str:
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "event"
    candidate, n = slug, 2
    while db().scalar(select(Event.id).where(Event.slug == candidate)):
        candidate, n = f"{slug}-{n}", n + 1
    return candidate


def _before_create(collection: str, item) -> None:
    item.slug = _slugify(item.title)


def _check_rules(collection: str, item) -> None:
    if item.end_at and item.end_at <= item.start_at:
        raise ApiError(422, "invalid_window", "“Ends” must be later than “Starts”.")
    if item.registration_closes_at and item.registration_closes_at > (item.end_at or item.start_at):
        raise ApiError(422, "invalid_window", "Registration must close before the event ends.")
    if item.id:  # existing event: added places go to the waiting list first
        regs.promote_waitlist(item)


bp = editor_blueprint(COLLECTIONS, role=EDITOR_ROLE, db=db, service="events",
                      check_rules=_check_rules, before_create=_before_create)


def _event(event_id: str) -> Event:
    x = db().get(Event, event_id)
    if x is None:
        raise ApiError(404, "item_not_found", "That event was already removed.")
    return x


def _rows(event_id: str):
    order = {"registered": 0, "waitlisted": 1, "cancelled": 2}
    rows = db().scalars(select(Registration).where(Registration.event_id == event_id)
                        .order_by(Registration.created_at)).all()
    return sorted(rows, key=lambda r: order.get(r.status, 3))


@bp.get("/events/<event_id>/registrations")
@require_role(EDITOR_ROLE)
def registration_list(event_id):
    x = _event(event_id)
    items = [regs.view(r) | {"waitlist_position": regs.waitlist_position(r)} for r in _rows(x.id)]
    return jsonify(event={"id": x.id, "title": x.title, "capacity": x.capacity}, items=items)


@bp.get("/events/<event_id>/registrations.csv")
@require_role(EDITOR_ROLE)
def registration_csv(event_id):
    x = _event(event_id)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Name", "Email", "Status", "Attended", "Registered at (Nepal time)"])
    for r in _rows(x.id):
        when = r.created_at.astimezone(NEPAL).strftime(NEPAL_FMT) if r.created_at else ""
        # a leading = + - @ would run as a formula in Excel; prefix it so it shows as text
        cells = [r.name, r.email, r.status, "yes" if r.attended else "no", when]
        writer.writerow(["'" + c if c[:1] in ("=", "+", "-", "@") else c for c in cells])
    filename = f"registrations-{x.slug}.csv"
    return Response("﻿" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@bp.patch("/events/<event_id>/registrations/<reg_id>")
@require_role(EDITOR_ROLE)
def registration_update(event_id, reg_id):
    """Mark attendance, cancel a registration, or move someone off the waiting list."""
    event = regs.locked_event(event_id)
    reg = db().get(Registration, reg_id)
    if reg is None or reg.event_id != event.id:
        raise ApiError(404, "item_not_found", "That registration was already removed.")
    data = request.get_json(silent=True) or {}
    if "attended" in data:
        reg.attended = bool(data["attended"])
    status, previous = data.get("status"), reg.status
    if status is not None:
        if status not in ("registered", "cancelled"):
            raise ApiError(422, "invalid_field", "Choose registered or cancelled.")
        reg.status = status  # an admin may admit someone past the limit
    moved = regs.promote_waitlist(event) if status == "cancelled" else []
    db().commit()
    if status == "registered" and previous == "waitlisted":
        notify(to=reg.email, kind="success", title=f"You're registered for {event.title}",
               body="The organisers gave you a place from the waiting list.", link=f"/events/{event.slug}")
    elif status == "cancelled" and previous != "cancelled":
        notify(to=reg.email, kind="warning", title=f"Your registration for {event.title} was cancelled",
               body="The organisers cancelled your place. Contact them if you think this is a mistake.",
               link=f"/events/{event.slug}")
    emit("registrations.updated", entity="registrations", entity_id=reg.id,
         data={"label": "registration", "name": event.title, "event_id": event.id, "email": reg.email,
               "fields": sorted(k for k in data if k in ("attended", "status")),
               "moved_up": [m.email for m in moved]})
    return jsonify(item=regs.view(reg))
