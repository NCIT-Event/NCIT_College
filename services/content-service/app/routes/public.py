"""Read-only endpoints for the website (cached briefly by the gateway).

Mounted at /api/v1/content/public/.
"""

import re

from flask import Blueprint, current_app, jsonify, request
from ncit_common import ApiError
from sqlalchemy import func, or_, select

from ..collections import (
    NOTICE_CATEGORIES,
    banner,
    facility,
    leadership,
    news,
    notice,
    now,
    public,
)
from ..db import db
from ..models import Banner, Facility, LeadershipMessage, NewsArticle, Notice

bp = Blueprint("public", __name__, url_prefix="/public")

PER_PAGE = 12


def _live_banners(t):
    return (select(Banner).where(Banner.published.is_(True),
                                 or_(Banner.start_at.is_(None), Banner.start_at <= t),
                                 or_(Banner.end_at.is_(None), Banner.end_at > t))
            .order_by(Banner.sort_order))


def _live_news(t):
    return select(NewsArticle).where(NewsArticle.published.is_(True), NewsArticle.publish_at <= t)


def _live_notices(t):
    return select(Notice).where(Notice.published.is_(True), Notice.publish_at <= t,
                                or_(Notice.expires_at.is_(None), Notice.expires_at > t))


def _page(stmt, order, serializer, t):
    page = max(int(request.args.get("page", 1) or 1), 1)
    total = db().scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db().scalars(stmt.order_by(*order).offset((page - 1) * PER_PAGE).limit(PER_PAGE)).all()
    return {"items": [public(serializer(x, t)) for x in rows], "total": total, "page": page, "per_page": PER_PAGE}


@bp.get("/home")
def home():
    """Everything the home page needs, in one request."""
    t = now()
    return jsonify(
        banners=[public(banner(x, t)) for x in db().scalars(_live_banners(t))],
        leadership=[public(leadership(x, t)) for x in db().scalars(
            select(LeadershipMessage).where(LeadershipMessage.published.is_(True)).order_by(LeadershipMessage.sort_order))],
        news=[public(news(x, t)) for x in db().scalars(_live_news(t).order_by(NewsArticle.publish_at.desc()).limit(4))],
        notices=[public(notice(x, t)) for x in db().scalars(
            _live_notices(t).order_by(Notice.pinned.desc(), Notice.publish_at.desc()).limit(5))],
        facilities=[public(facility(x, t)) for x in db().scalars(
            select(Facility).where(Facility.published.is_(True)).order_by(Facility.sort_order))],
    )


@bp.get("/news")
def news_list():
    t = now()
    stmt = _live_news(t)
    if request.args.get("category"):
        stmt = stmt.where(NewsArticle.category == request.args["category"])
    return jsonify(_page(stmt, [NewsArticle.publish_at.desc()], news, t))


@bp.get("/news/<slug>")
def news_article(slug):
    t = now()
    x = db().scalar(_live_news(t).where(NewsArticle.slug == slug))
    if x is None:
        raise ApiError(404, "not_found", "This article isn't available.")
    return jsonify(article=public(news(x, t)))


@bp.get("/notices")
def notices_list():
    t = now()
    stmt = _live_notices(t)
    category = request.args.get("category")
    if category in NOTICE_CATEGORIES:
        stmt = stmt.where(Notice.category == category)
    return jsonify(_page(stmt, [Notice.pinned.desc(), Notice.publish_at.desc()], notice, t))


@bp.get("/leadership")
def leadership_list():
    t = now()
    rows = db().scalars(select(LeadershipMessage).where(LeadershipMessage.published.is_(True))
                        .order_by(LeadershipMessage.sort_order))
    return jsonify(items=[public(leadership(x, t)) for x in rows])


CONTACT_TOPICS = {"admissions": "Admissions", "academics": "Academics", "fees": "Fees and payments",
                  "careers": "Jobs at NCIT", "media": "Media and partnerships", "other": "Something else"}
EMAIL_RE = re.compile(r"^[^\s@]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$")


@bp.post("/contact")
def contact():
    """The Contact page form: emailed to the college (CONTACT_EMAIL). Rate limited at the gateway.

    Nothing is ever emailed back to the address given, so the form can't be
    used to send mail to strangers. A hidden "website" field catches bots.
    """
    body = request.get_json(silent=True) or {}
    if body.get("website"):  # honeypot: people never see this field
        return jsonify(ok=True)
    name = str(body.get("name") or "").strip()[:120]
    email = str(body.get("email") or "").strip()[:254]
    phone = str(body.get("phone") or "").strip()[:30]
    topic = body.get("topic") if body.get("topic") in CONTACT_TOPICS else "other"
    message = str(body.get("message") or "").strip()
    if not name:
        raise ApiError(422, "invalid_field", "Tell us your name.")
    if not EMAIL_RE.match(email):
        raise ApiError(422, "invalid_field", "Enter an email address we can reply to.")
    if len(message) < 10:
        raise ApiError(422, "invalid_field", "Write a little more so we can help.")
    if len(message) > 4000:
        raise ApiError(422, "invalid_field", "Keep the message under 4000 characters.")
    current_app.config["MAIL"].send(current_app.config["CONTACT_EMAIL"], "contact_message",
                                    {"name": name, "email": email, "phone": phone, "topic": CONTACT_TOPICS[topic],
                                     "message": message})
    return jsonify(ok=True)
