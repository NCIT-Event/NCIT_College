"""What HR Officers manage (vacancies) and how they're shown. Status: draft · open · closed."""

from datetime import datetime
from functools import partial

from ncit_common.fields import Field as _Field
from ncit_common.models import utcnow

from .models import Job

Field = partial(_Field, media_root="careers")

KINDS = ("faculty", "staff")
EMPLOYMENT = ("full_time", "part_time", "contract")


def _iso(dt):
    return dt.isoformat() if dt else None


def job_status(x, now: datetime) -> str:
    if not x.published:
        return "draft"
    return "open" if x.closes_at > now else "closed"


def job(x, now) -> dict:
    active = [a for a in x.applications if a.status != "withdrawn"]
    return {"id": x.id, "published": x.published, "updated_at": _iso(x.updated_at), "updated_by": x.updated_by,
            "slug": x.slug, "title": x.title, "department": x.department, "kind": x.kind, "employment": x.employment,
            "positions": x.positions, "summary": x.summary, "description": x.description,
            "requirements": x.requirements, "attachment": x.attachment, "closes_at": _iso(x.closes_at),
            "status": job_status(x, now), "application_count": len(active),
            "new_count": sum(1 for a in active if a.status == "submitted")}


def public(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in ("published", "updated_by", "updated_at", "application_count", "new_count")}


COLLECTIONS = {
    "jobs": {
        "model": Job, "serialize": job, "label": "vacancy", "ordered": False, "name_field": "title",
        "order_by": lambda m: [m.closes_at.desc()],
        "fields": {
            "title": Field("Job title", max_len=200, required=True),
            "department": Field("Department or office", max_len=120),
            "kind": Field("Type", max_len=10, choices=KINDS),
            "employment": Field("Employment", max_len=12, choices=EMPLOYMENT),
            "positions": Field("Positions", "int", lo=1, hi=100),
            "summary": Field("Summary", max_len=400),
            "description": Field("About the role", "text", max_len=10000),
            "requirements": Field("Requirements", "text", max_len=6000),
            "attachment": Field("Job description (PDF)", "file"),
            "closes_at": Field("Applications close", "datetime", required=True),
            "published": Field("Published", "bool"),
        },
    },
}


def now() -> datetime:
    return utcnow()
