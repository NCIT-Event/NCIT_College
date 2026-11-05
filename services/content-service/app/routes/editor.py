"""Editing website content: Super Admins and Content Admins.

Mounted at /api/v1/content/. The routes come from ncit_common.editor
(GET/POST /<collection>, PATCH/DELETE /<collection>/<id>, POST /<collection>/order,
POST /uploads); this file adds the rules specific to website content.
"""

import re
import unicodedata

from ncit_common import ApiError
from ncit_common.editor import editor_blueprint
from sqlalchemy import select

from ..collections import COLLECTIONS, now
from ..db import db
from ..models import LeadershipMessage, NewsArticle

EDITOR_ROLE = "content_admin"  # super_admin passes every role check too


def _slugify(title: str) -> str:
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "article"
    candidate, n = slug, 2
    while db().scalar(select(NewsArticle.id).where(NewsArticle.slug == candidate)):
        candidate, n = f"{slug}-{n}", n + 1
    return candidate


def _before_create(collection: str, item) -> None:
    if collection == "news":
        item.slug = _slugify(item.title)


def _check_rules(collection: str, item) -> None:
    """Rules that involve more than one field."""
    if collection == "banners" and item.start_at and item.end_at and item.end_at <= item.start_at:
        raise ApiError(422, "invalid_window", "“Show until” must be later than “Show from”.")
    if collection == "notices" and item.publish_at and item.expires_at and item.expires_at <= item.publish_at:
        raise ApiError(422, "invalid_window", "“Remove after” must be later than “Publish at”.")
    if collection in ("news", "notices") and item.published and item.publish_at is None:
        item.publish_at = now()  # publishing without a time means "now"
    if collection == "leadership":
        clash = db().scalar(select(LeadershipMessage.id).where(LeadershipMessage.position == item.position,
                                                               LeadershipMessage.id != item.id))
        if clash:
            raise ApiError(409, "position_taken", "There is already a message for this position. Edit that one instead.")


bp = editor_blueprint(COLLECTIONS, role=EDITOR_ROLE, db=db, service="content",
                      check_rules=_check_rules, before_create=_before_create)
