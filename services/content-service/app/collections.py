"""The five kinds of content, what editors may change, and how each is shown.

Status shown in the dashboard:
- draft     not published
- scheduled published, but its start / publish time is in the future
- live      on the website now
- expired   published, but its end / expiry time has passed
"""

from datetime import datetime
from functools import partial

from ncit_common.fields import Field as _Field

from .models import Banner, Facility, LeadershipMessage, NewsArticle, Notice, utcnow

Field = partial(_Field, media_root="content")

POSITIONS = ("executive_director", "director", "principal")
NOTICE_CATEGORIES = ("exam", "admission", "holiday", "result", "general")
FACILITY_ICONS = ("library", "monitor", "cpu", "flask-conical", "utensils", "bus", "trophy", "building-2",
                  "graduation-cap", "users", "book-open", "globe")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def window_status(published: bool, start: datetime | None, end: datetime | None, now: datetime) -> str:
    if not published:
        return "draft"
    if start and start > now:
        return "scheduled"
    if end and end <= now:
        return "expired"
    return "live"


def _base(x) -> dict:
    return {"id": x.id, "published": x.published, "updated_at": _iso(x.updated_at), "updated_by": x.updated_by}


def banner(x, now) -> dict:
    return _base(x) | {
        "title": x.title, "subtitle": x.subtitle, "image": x.image, "image_alt": x.image_alt,
        "cta_label": x.cta_label, "cta_url": x.cta_url, "cta2_label": x.cta2_label, "cta2_url": x.cta2_url,
        "start_at": _iso(x.start_at), "end_at": _iso(x.end_at),
        "status": window_status(x.published, x.start_at, x.end_at, now),
    }


def leadership(x, now) -> dict:
    return _base(x) | {
        "position": x.position, "person_name": x.person_name, "role_title": x.role_title,
        "excerpt": x.excerpt, "message": x.message, "photo": x.photo,
        "status": "live" if x.published else "draft",
    }


def news(x, now) -> dict:
    return _base(x) | {
        "slug": x.slug, "title": x.title, "summary": x.summary, "body": x.body, "cover": x.cover,
        "cover_alt": x.cover_alt, "category": x.category, "publish_at": _iso(x.publish_at),
        "status": window_status(x.published, x.publish_at, None, now),
    }


def notice(x, now) -> dict:
    return _base(x) | {
        "title": x.title, "category": x.category, "body": x.body, "attachment": x.attachment,
        "link_url": x.link_url, "pinned": x.pinned, "publish_at": _iso(x.publish_at), "expires_at": _iso(x.expires_at),
        "status": window_status(x.published, x.publish_at, x.expires_at, now),
    }


def facility(x, now) -> dict:
    return _base(x) | {"name": x.name, "description": x.description, "icon": x.icon, "photo": x.photo,
                       "status": "live" if x.published else "draft"}


def public(item: dict) -> dict:
    """Drop editor-only keys before sending to the website."""
    return {k: v for k, v in item.items() if k not in ("published", "updated_by", "status")}


COLLECTIONS = {
    "banners": {
        "model": Banner, "serialize": banner, "label": "banner", "ordered": True, "name_field": "title",
        "fields": {
            "title": Field("Headline", max_len=160, required=True),
            "subtitle": Field("Text under the headline", max_len=300),
            "image": Field("Banner photo", "media"),
            "image_alt": Field("Photo description", max_len=200),
            "cta_label": Field("Main button text", max_len=40),
            "cta_url": Field("Main button link", "url", max_len=300),
            "cta2_label": Field("Second button text", max_len=40),
            "cta2_url": Field("Second button link", "url", max_len=300),
            "start_at": Field("Show from", "datetime"),
            "end_at": Field("Show until", "datetime"),
            "published": Field("Published", "bool"),
        },
    },
    "leadership": {
        "model": LeadershipMessage, "serialize": leadership, "label": "leadership message", "ordered": True,
        "name_field": "person_name",
        "fields": {
            "position": Field("Position", max_len=40, required=True, choices=POSITIONS),
            "person_name": Field("Name", max_len=120, required=True),
            "role_title": Field("Title shown under the name", max_len=120),
            "excerpt": Field("Short quote for the home page", max_len=400),
            "message": Field("Full message", "text", max_len=8000),
            "photo": Field("Portrait", "media"),
            "published": Field("Published", "bool"),
        },
    },
    "news": {
        "model": NewsArticle, "serialize": news, "label": "news article", "ordered": False, "name_field": "title",
        "order_by": lambda m: [m.publish_at.desc().nulls_first(), m.updated_at.desc()],
        "fields": {
            "title": Field("Headline", max_len=200, required=True),
            "summary": Field("Summary", max_len=400),
            "body": Field("Article", "text", max_len=20000),
            "cover": Field("Cover photo", "media"),
            "cover_alt": Field("Photo description", max_len=200),
            "category": Field("Category", max_len=40),
            "publish_at": Field("Publish at", "datetime"),
            "published": Field("Published", "bool"),
        },
    },
    "notices": {
        "model": Notice, "serialize": notice, "label": "notice", "ordered": False, "name_field": "title",
        "order_by": lambda m: [m.publish_at.desc().nulls_first(), m.updated_at.desc()],
        "fields": {
            "title": Field("Title", max_len=200, required=True),
            "category": Field("Category", max_len=20, choices=NOTICE_CATEGORIES),
            "body": Field("Details", "text", max_len=4000),
            "attachment": Field("PDF", "file"),
            "link_url": Field("Link", "url", max_len=300),
            "pinned": Field("Pin to the top", "bool"),
            "publish_at": Field("Publish at", "datetime"),
            "expires_at": Field("Remove after", "datetime"),
            "published": Field("Published", "bool"),
        },
    },
    "facilities": {
        "model": Facility, "serialize": facility, "label": "facility", "ordered": True, "name_field": "name",
        "fields": {
            "name": Field("Name", max_len=120, required=True),
            "description": Field("Description", "text", max_len=1000),
            "icon": Field("Icon", max_len=40, choices=FACILITY_ICONS),
            "photo": Field("Photo", "media"),
            "published": Field("Published", "bool"),
        },
    },
}


def now() -> datetime:
    return utcnow()
