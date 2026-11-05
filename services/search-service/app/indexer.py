"""Build the search index from the services' public endpoints.

Each source turns one service's public data into documents. A source is
re-indexed as a whole: its old documents are replaced only if every request
for it succeeded, so a service that is briefly down never empties results.
"""

import json
import logging
import re
import urllib.request
from datetime import datetime

from sqlalchemy import delete

from .models import Document, utcnow

log = logging.getLogger("search-indexer")
TAG_RE = re.compile(r"\s+")


def clean(text, limit=None) -> str:
    text = TAG_RE.sub(" ", str(text or "")).strip()
    return text[:limit] if limit else text


def doc(**fields) -> dict:
    """One search document (key, kind, title, summary, body, url and optionally updated_at, in_sitemap)."""
    return fields


def when(value) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def http_fetcher(urls: dict):
    """fetch(source, path) using each service's internal base URL."""

    def fetch(source: str, path: str):
        req = urllib.request.Request(urls[source].rstrip("/") + path, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read())

    return fetch


def _paged(fetch, source, path):
    page, items = 1, []
    while True:
        data = fetch(source, f"{path}{'&' if '?' in path else '?'}page={page}")
        items += data["items"]
        if page * data.get("per_page", 50) >= data.get("total", 0) or not data["items"] or page >= 40:
            return items
        page += 1


def academics(fetch):
    docs = []
    for d in fetch("academics", "/public/departments")["items"]:
        full = fetch("academics", f"/public/departments/{d['slug']}")["department"]
        body = [full.get("overview"), (full.get("hod") or {}).get("name"), (full.get("hod") or {}).get("message"),
                " ".join(p.get("name", "") for p in full.get("programmes", [])),
                " ".join(f"{lab.get('name', '')} {lab.get('description', '')}" for lab in full.get("labs", []))]
        docs.append(doc(key=f"department:{d['slug']}", kind="department", title=full["name"], summary=clean(full.get("tagline"), 600),
                         body=clean(" ".join(filter(None, body))), url=f"/departments/{d['slug']}", updated_at=when(full.get("updated_at"))))
    for f in fetch("academics", "/public/faculty")["items"]:
        docs.append(doc(key=f"faculty:{f['id']}", kind="faculty", title=f["name"],
                         summary=clean(f"{f.get('designation', '')}, {f['department']['name']}", 600),
                         body=clean(f.get("specialization")), url=f"/faculty?q={urllib.request.quote(f['name'])}", in_sitemap=False))
    return docs


def content(fetch):
    docs = []
    for a in _paged(fetch, "content", "/public/news"):
        docs.append(doc(key=f"news:{a['slug']}", kind="news", title=a["title"], summary=clean(a.get("summary"), 600),
                         body=clean(f"{a.get('category', '')} {a.get('body', '')}"), url=f"/news/{a['slug']}", updated_at=when(a.get("publish_at"))))
    for n in _paged(fetch, "content", "/public/notices"):
        docs.append(doc(key=f"notice:{n['id']}", kind="notice", title=n["title"], summary=clean(n.get("body"), 300),
                         body=clean(f"{n.get('category', '')} {n.get('body', '')}"), url=f"/notices#notice-{n['id']}",
                         updated_at=when(n.get("publish_at")), in_sitemap=False))
    for m in fetch("content", "/public/leadership")["items"]:
        docs.append(doc(key=f"leadership:{m['position']}", kind="page", title=f"Message from the {m.get('role_title') or m['position']}",
                         summary=clean(f"{m['person_name']}: {m.get('excerpt', '')}", 600), body=clean(m.get("message")),
                         url=f"/leadership#{m['position']}", in_sitemap=False))
    return docs


def events(fetch):
    docs = []
    seen = set()
    for when_ in ("", "&when=past"):
        for e in fetch("events", f"/public/events?limit=50{when_}")["items"]:
            if e["slug"] in seen:
                continue
            seen.add(e["slug"])
            docs.append(doc(key=f"event:{e['slug']}", kind="event", title=e["title"], summary=clean(e.get("summary"), 600),
                             body=clean(" ".join(filter(None, [e.get("venue"), e.get("organizer"), e.get("category"), e.get("body")]))),
                             url=f"/events/{e['slug']}", updated_at=when(e.get("start_at"))))
    return docs


def eca(fetch):
    docs = []
    for c in fetch("eca", "/public/clubs")["items"]:
        full = fetch("eca", f"/public/clubs/{c['slug']}")
        club = full["club"]
        body = [club.get("about"), club.get("meeting_info"), club.get("coordinator_name"),
                " ".join(a.get("title", "") for a in full.get("activities", []))]
        docs.append(doc(key=f"club:{c['slug']}", kind="club", title=club["name"], summary=clean(club.get("tagline"), 600),
                         body=clean(" ".join(filter(None, body))), url=f"/clubs/{c['slug']}"))
    return docs


def careers(fetch):
    docs = []
    for j in fetch("careers", "/public/jobs")["items"]:
        full = fetch("careers", f"/public/jobs/{j['slug']}")["job"]
        docs.append(doc(key=f"job:{j['slug']}", kind="job", title=full["title"], summary=clean(full.get("summary"), 600),
                         body=clean(" ".join(filter(None, [full.get("department"), full.get("description"), full.get("requirements")]))),
                         url=f"/careers/{j['slug']}"))
    return docs


def admissions(fetch):
    docs = []
    for x in fetch("admissions", "/public/intakes")["items"]:
        for o in x.get("offerings", []):
            docs.append(doc(key=f"programme:{o['id']}", kind="programme", title=o["programme"],
                             summary=clean(f"{x['name']} admissions · {o.get('seats') or ''} seats".replace(" ·  seats", ""), 600),
                             body=clean(f"{o.get('eligibility', '')} {o.get('fee_note', '')}"), url="/admissions#programmes", in_sitemap=False))
    return docs


PAGES = [
    ("/", "Nepal College of Information Technology", "Engineering, IT and management programmes in Balkumari, Lalitpur, affiliated to Pokhara University."),
    ("/about", "About NCIT", "History, leadership and facilities of the college."),
    ("/admissions", "Admissions", "Programmes open for applications, seats, eligibility, fees and dates."),
    ("/apply", "Apply online", "Apply for admission and track your application."),
    ("/faculty", "Faculty directory", "Teachers in every department."),
    ("/events", "Events", "Upcoming and past events, and the events calendar."),
    ("/clubs", "ECA and clubs", "Student clubs and extra-curricular activities."),
    ("/news", "News", "News from the college."),
    ("/notices", "Notices", "Exam routines, admission notices, holidays and results."),
    ("/leadership", "Leadership messages", "Messages from the Executive Director, Director and Principal."),
    ("/careers", "Careers at NCIT", "Faculty and staff vacancies."),
    ("/alumni", "Alumni", "The alumni directory and how to register as alumni."),
    ("/alumni/join", "Register as alumni", "Join the NCIT alumni network."),
    ("/contact", "Contact and directions", "Phone, email, address and a message form."),
    ("/privacy", "Privacy notice", "How the website uses personal information."),
    ("/accessibility", "Accessibility", "Accessibility statement and how to report a problem."),
]


def pages(fetch):
    return [doc(key=f"page:{url}", kind="page", title=t, summary=s, body="", url=url) for url, t, s in PAGES]


SOURCES = {"pages": pages, "academics": academics, "content": content, "events": events, "eca": eca,
           "careers": careers, "admissions": admissions}

# which source to refresh when a service announces a change
SERVICE_SOURCE = {"academics-service": "academics", "content-service": "content", "event-service": "events",
                  "eca-service": "eca", "career-service": "careers", "admission-service": "admissions"}


def reindex(session, fetch, sources=None) -> dict:
    """Rebuild the given sources (default: all). Returns {source: count or 'failed: …'}."""
    result = {}
    for name in sources or SOURCES:
        try:
            docs = SOURCES[name](fetch)
        except Exception as exc:  # noqa: BLE001 (keep the previous documents when a service is unreachable)
            log.warning("could not index %s: %s", name, exc)
            result[name] = f"failed: {type(exc).__name__}"
            continue
        session.execute(delete(Document).where(Document.source == name))
        now = utcnow()
        session.add_all(Document(source=name, indexed_at=now, **{"in_sitemap": True, "updated_at": None} | d) for d in docs)
        session.commit()
        result[name] = len(docs)
    return result
