"""Site search and the sitemap. Mounted at /api/v1/search/public/ (cached briefly) and /sitemap.xml."""

from xml.sax.saxutils import escape

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import select

from ..db import db
from ..models import Document
from ..search import kinds, search

bp = Blueprint("public", __name__)
PER_PAGE = 20
KIND_LABELS = {"page": "Pages", "department": "Departments", "programme": "Programmes", "faculty": "Faculty", "news": "News",
               "notice": "Notices", "event": "Events", "club": "Clubs", "job": "Vacancies"}


@bp.get("/public/search")
def site_search():
    q = (request.args.get("q") or "").strip()[:200]
    kind = request.args.get("kind") if request.args.get("kind") in KIND_LABELS else None
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    rows, total = search(db(), q, kind, PER_PAGE, (page - 1) * PER_PAGE)
    return jsonify(q=q, kind=kind, page=page, per_page=PER_PAGE, total=total, kinds=kinds(db(), q), labels=KIND_LABELS,
                   items=[{"kind": d.kind, "title": d.title, "summary": d.summary, "snippet": s or d.summary, "url": d.url,
                           "updated_at": d.updated_at.isoformat() if d.updated_at else None} for d, s in rows])


@bp.get("/sitemap.xml")
def sitemap():
    site = current_app.config["SITE_URL"].rstrip("/")
    rows = db().scalars(select(Document).where(Document.in_sitemap.is_(True)).order_by(Document.url)).all()
    seen, out = set(), ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for d in rows:
        if d.url in seen or "#" in d.url or "?" in d.url:
            continue
        seen.add(d.url)
        lastmod = f"<lastmod>{d.updated_at.date().isoformat()}</lastmod>" if d.updated_at else ""
        out.append(f"  <url><loc>{escape(site + d.url)}</loc>{lastmod}</url>")
    out.append("</urlset>")
    return Response("\n".join(out) + "\n", mimetype="application/xml")
