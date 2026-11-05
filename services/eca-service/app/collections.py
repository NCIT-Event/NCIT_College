"""What ECA Admins may change, and how clubs and activities are shown."""

from datetime import datetime
from functools import partial

from ncit_common.fields import Field as _Field
from ncit_common.models import utcnow

from .models import Activity, Club

Field = partial(_Field, media_root="eca")

CATEGORIES = ("technical", "cultural", "sports", "arts", "social", "academic")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _base(x) -> dict:
    return {"id": x.id, "published": x.published, "updated_at": _iso(x.updated_at), "updated_by": x.updated_by,
            "status": "live" if x.published else "draft"}


def club(x, now) -> dict:
    return _base(x) | {
        "slug": x.slug, "name": x.name, "category": x.category, "tagline": x.tagline, "about": x.about,
        "logo": x.logo, "photo": x.photo, "photo_alt": x.photo_alt,
        "coordinator_name": x.coordinator_name, "coordinator_email": x.coordinator_email,
        "meeting_info": x.meeting_info, "join_open": x.join_open,
        "member_count": x.member_count or 0, "pending_count": x.pending_count or 0,
    }


def activity(x, now) -> dict:
    return _base(x) | {
        "club_id": x.club_id, "club": {"name": x.club.name, "slug": x.club.slug} if x.club else None,
        "title": x.title, "happened_on": _iso(x.happened_on), "body": x.body,
        "photo": x.photo, "photo_alt": x.photo_alt,
    }


def public(item: dict) -> dict:
    """Drop editor-only keys before sending to the website."""
    return {k: v for k, v in item.items() if k not in ("published", "updated_by", "status", "pending_count")}


COLLECTIONS = {
    "clubs": {
        "model": Club, "serialize": club, "label": "club", "ordered": True, "name_field": "name",
        "fields": {
            "name": Field("Club name", max_len=120, required=True),
            "category": Field("Category", max_len=20, choices=CATEGORIES),
            "tagline": Field("One-line description", max_len=300),
            "about": Field("About the club", "text", max_len=6000),
            "logo": Field("Logo", "media"),
            "photo": Field("Cover photo", "media"),
            "photo_alt": Field("Photo description", max_len=200),
            "coordinator_name": Field("Staff coordinator", max_len=120),
            "coordinator_email": Field("Coordinator email", "email", max_len=254),
            "meeting_info": Field("When and where the club meets", max_len=200),
            "join_open": Field("Accepting new members", "bool"),
            "published": Field("Published", "bool"),
        },
    },
    "activities": {
        "model": Activity, "serialize": activity, "label": "club activity", "ordered": False, "name_field": "title",
        "order_by": lambda m: [m.happened_on.desc().nulls_first(), m.updated_at.desc()],
        "filters": ("club_id",),
        "fields": {
            "club_id": Field("Club", max_len=36, required=True),
            "title": Field("Title", max_len=200, required=True),
            "happened_on": Field("Date", "datetime"),
            "body": Field("What happened", "text", max_len=8000),
            "photo": Field("Photo", "media"),
            "photo_alt": Field("Photo description", max_len=200),
            "published": Field("Published", "bool"),
        },
    },
}


def now() -> datetime:
    return utcnow()
