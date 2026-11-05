"""Registering for events, the waiting list, and who gets a freed place.

Rules:
- Any signed-in college account can register while registration is open.
- When an event is full, new sign-ups go on the waiting list in order.
- When someone cancels (or the Event Admin adds places), the earliest person
  on the waiting list moves up automatically.
- The event row is locked while places are counted (SELECT ... FOR UPDATE on
  PostgreSQL), so two people can't take the last place at the same time.
"""

from flask import g
from ncit_common import ApiError
from ncit_common.editor import emit
from ncit_common.notify import notify
from sqlalchemy import func, select

from .collections import now, registration_closes
from .db import db
from .models import Event, Registration


def locked_event(event_id: str) -> Event:
    event = db().get(Event, event_id, with_for_update=True, populate_existing=True)
    if event is None:
        raise ApiError(404, "not_found", "This event isn't available.")
    return event


def taken(event_id: str) -> int:
    return db().scalar(select(func.count(Registration.id)).where(
        Registration.event_id == event_id, Registration.status == "registered")) or 0


def promote_waitlist(event: Event) -> list[Registration]:
    """Move people up from the waiting list while there is room. Caller commits."""
    db().flush()
    moved = []
    count = taken(event.id)
    waiting = db().scalars(select(Registration).where(Registration.event_id == event.id,
                                                      Registration.status == "waitlisted")
                           .order_by(Registration.created_at)).all()
    for reg in waiting:
        if event.capacity and count >= event.capacity:
            break
        reg.status = "registered"
        count += 1
        moved.append(reg)
    if moved:  # told once the change is saved (see announce_after_request)
        g.setdefault("promoted", []).extend((r.email, event.title, event.slug) for r in moved)
    return moved


def announce_after_request(resp):
    """After a successful request, tell everyone who moved up from a waiting list (app.after_request)."""
    if resp.status_code < 400:
        for email, title, slug in g.pop("promoted", []):
            notify(to=email, kind="success", title=f"A place opened up: you're registered for {title}",
                   body="You were on the waiting list and are now registered. If you can't come, cancel so someone else can.",
                   link=f"/events/{slug}")
    return resp


def register(event_id: str, principal) -> Registration:
    event = locked_event(event_id)
    t = now()
    if not event.published or not event.registration_open:
        raise ApiError(409, "registration_off", "This event doesn't take registrations.")
    if t >= registration_closes(event):
        raise ApiError(409, "registration_closed", "Registration for this event has closed.")
    reg = db().scalar(select(Registration).where(Registration.event_id == event.id,
                                                 Registration.email == principal.email))
    if reg is not None and reg.status != "cancelled":
        raise ApiError(409, "already_registered", "You're already registered for this event.")
    full = bool(event.capacity) and taken(event.id) >= event.capacity
    if reg is None:
        reg = Registration(event_id=event.id, email=principal.email)
        db().add(reg)
    reg.user_id, reg.name = principal.user_id, principal.name or ""
    reg.status = "waitlisted" if full else "registered"
    reg.created_at = t  # re-registering after cancelling goes to the back of the queue
    db().commit()
    emit(f"registrations.{reg.status}", entity="registrations", entity_id=reg.id,
         data={"label": "registration", "name": event.title, "event_id": event.id, "email": reg.email})
    return reg


def cancel(event_id: str, principal) -> list[Registration]:
    event = locked_event(event_id)
    reg = db().scalar(select(Registration).where(Registration.event_id == event.id,
                                                 Registration.email == principal.email,
                                                 Registration.status != "cancelled"))
    if reg is None:
        raise ApiError(404, "not_registered", "You aren't registered for this event.")
    reg.status = "cancelled"
    moved = promote_waitlist(event)
    db().commit()
    emit("registrations.cancelled", entity="registrations", entity_id=reg.id,
         data={"label": "registration", "name": event.title, "event_id": event.id, "email": reg.email,
               "moved_up": [m.email for m in moved]})
    return moved


def view(reg: Registration) -> dict:
    return {"id": reg.id, "email": reg.email, "name": reg.name, "status": reg.status, "attended": reg.attended,
            "created_at": reg.created_at.isoformat() if reg.created_at else None}


def waitlist_position(reg: Registration) -> int | None:
    if reg.status != "waitlisted":
        return None
    ahead = db().scalar(select(func.count(Registration.id)).where(
        Registration.event_id == reg.event_id, Registration.status == "waitlisted",
        Registration.created_at < reg.created_at)) or 0
    return ahead + 1
