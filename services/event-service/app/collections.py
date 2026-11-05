"""What Event Admins may change, and how events are shown.

Status shown in the dashboard:
- draft     not published
- upcoming  published, starts in the future
- ongoing   published, started and not yet ended
- past      published, already over

Registration state shown on the website:
- off       no registration (just come along)
- open      places available
- full      no places left; new sign-ups join the waiting list
- closed    registration deadline has passed
"""

from datetime import datetime, timedelta
from functools import partial

from ncit_common.fields import Field as _Field
from ncit_common.models import utcnow

from .models import Event

Field = partial(_Field, media_root="events")

CATEGORIES = ("academic", "technical", "workshop", "seminar", "cultural", "sports", "career", "general")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def ends(x) -> datetime:
    """When an event is over: its end time, or 3 hours after it starts."""
    return x.end_at or (x.start_at + timedelta(hours=3))


def status(x, now: datetime) -> str:
    if not x.published:
        return "draft"
    if x.start_at > now:
        return "upcoming"
    return "ongoing" if ends(x) > now else "past"


def registration_closes(x) -> datetime:
    return x.registration_closes_at or x.start_at


def registration_state(x, now: datetime) -> str:
    if not x.registration_open:
        return "off"
    if now >= registration_closes(x):
        return "closed"
    if x.capacity and (x.registered_count or 0) >= x.capacity:
        return "full"
    return "open"


def event(x, now) -> dict:
    taken = x.registered_count or 0
    return {
        "id": x.id, "published": x.published, "updated_at": _iso(x.updated_at), "updated_by": x.updated_by,
        "slug": x.slug, "title": x.title, "summary": x.summary, "body": x.body, "category": x.category,
        "organizer": x.organizer, "venue": x.venue, "start_at": _iso(x.start_at), "end_at": _iso(x.end_at),
        "cover": x.cover, "cover_alt": x.cover_alt, "attachment": x.attachment, "external_url": x.external_url,
        "registration_open": x.registration_open, "capacity": x.capacity,
        "registration_closes_at": _iso(x.registration_closes_at),
        "registration": {
            "state": registration_state(x, now), "closes_at": _iso(registration_closes(x)),
            "capacity": x.capacity, "taken": taken,
            "spots_left": max(x.capacity - taken, 0) if x.capacity else None,
        },
        "registered_count": taken, "waitlist_count": x.waitlist_count or 0,
        "status": status(x, now),
    }


def public(item: dict) -> dict:
    """Drop editor-only keys before sending to the website."""
    hidden = ("published", "updated_by", "status", "registered_count", "waitlist_count",
              "registration_open", "capacity", "registration_closes_at")
    return {k: v for k, v in item.items() if k not in hidden}


COLLECTIONS = {
    "events": {
        "model": Event, "serialize": event, "label": "event", "ordered": False, "name_field": "title",
        "order_by": lambda m: [m.start_at.desc()],
        "fields": {
            "title": Field("Event name", max_len=200, required=True),
            "summary": Field("One-line summary", max_len=400),
            "body": Field("Details", "text", max_len=12000),
            "category": Field("Category", max_len=20, choices=CATEGORIES),
            "organizer": Field("Organised by", max_len=120),
            "venue": Field("Venue", max_len=160),
            "start_at": Field("Starts", "datetime", required=True),
            "end_at": Field("Ends", "datetime"),
            "cover": Field("Cover photo", "media"),
            "cover_alt": Field("Photo description", max_len=200),
            "attachment": Field("Programme PDF", "file"),
            "external_url": Field("External link", "url", max_len=300),
            "registration_open": Field("Take registrations", "bool"),
            "capacity": Field("Places", "int", lo=0, hi=100000),
            "registration_closes_at": Field("Registration closes", "datetime"),
            "published": Field("Published", "bool"),
        },
    },
}


def now() -> datetime:
    return utcnow()
