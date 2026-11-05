"""Signed-in college accounts: register for events and see your registrations.

Mounted at /api/v1/events/me/. Any signed-in @ncit.edu.np account may use these.
"""

from flask import Blueprint, jsonify
from ncit_common import ApiError, current_principal, require_auth, require_college
from sqlalchemy import select

from .. import registrations as regs
from ..collections import event, now, public
from ..db import db
from ..models import Event, Registration

bp = Blueprint("me", __name__, url_prefix="/me")


def _event_by_slug(slug: str) -> Event:
    x = db().scalar(select(Event).where(Event.slug == slug, Event.published.is_(True)))
    if x is None:
        raise ApiError(404, "not_found", "This event isn't available.")
    return x


def _mine(x: Event) -> dict | None:
    reg = db().scalar(select(Registration).where(Registration.event_id == x.id,
                                                 Registration.email == current_principal().email,
                                                 Registration.status != "cancelled"))
    if reg is None:
        return None
    return regs.view(reg) | {"waitlist_position": regs.waitlist_position(reg)}


@bp.get("/registrations")
@require_auth
def my_registrations():
    t = now()
    rows = db().execute(select(Registration, Event).join(Event).where(
        Registration.email == current_principal().email, Registration.status != "cancelled",
        Event.published.is_(True)).order_by(Event.start_at.desc())).all()
    return jsonify(items=[regs.view(r) | {"waitlist_position": regs.waitlist_position(r),
                                          "event": public(event(e, t))} for r, e in rows])


@bp.get("/events/<slug>")
@require_auth
def my_event(slug):
    x = _event_by_slug(slug)
    return jsonify(registration=_mine(x), event=public(event(x, now())))


@bp.post("/events/<slug>/register")
@require_college
def register(slug):
    x = _event_by_slug(slug)
    regs.register(x.id, current_principal())
    x = db().get(Event, x.id, populate_existing=True)
    return jsonify(registration=_mine(x), event=public(event(x, now()))), 201


@bp.delete("/events/<slug>/register")
@require_college
def cancel(slug):
    x = _event_by_slug(slug)
    regs.cancel(x.id, current_principal())
    x = db().get(Event, x.id, populate_existing=True)
    return jsonify(registration=None, event=public(event(x, now())))
