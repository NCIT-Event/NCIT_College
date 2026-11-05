"""What Admission Officers manage (intakes and programmes on offer) and how they're shown.

Intake status: draft · upcoming (opens later) · open · closed.
"""

from datetime import datetime
from functools import partial

from ncit_common.fields import Field as _Field
from ncit_common.models import utcnow

from .models import Intake, Offering

Field = partial(_Field, media_root="admissions")

LEVELS = ("bachelor", "master")


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def intake_status(x, now: datetime) -> str:
    if not x.published:
        return "draft"
    if x.opens_at > now:
        return "upcoming"
    return "open" if x.closes_at > now else "closed"


def intake(x, now) -> dict:
    return {"id": x.id, "published": x.published, "updated_at": _iso(x.updated_at), "updated_by": x.updated_by,
            "slug": x.slug, "name": x.name, "intro": x.intro, "opens_at": _iso(x.opens_at), "closes_at": _iso(x.closes_at),
            "status": intake_status(x, now), "offering_count": len(x.offerings)}


def offering(x, now) -> dict:
    return {"id": x.id, "published": x.published, "updated_at": _iso(x.updated_at), "updated_by": x.updated_by,
            "intake_id": x.intake_id, "intake": x.intake.name if x.intake else "", "programme": x.programme,
            "department": x.department, "level": x.level, "seats": x.seats, "eligibility": x.eligibility,
            "fee_note": x.fee_note, "status": "live" if x.published else "draft"}


def public(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in ("published", "updated_by", "updated_at")}


COLLECTIONS = {
    "intakes": {
        "model": Intake, "serialize": intake, "label": "intake", "ordered": False, "name_field": "name",
        "order_by": lambda m: [m.opens_at.desc()],
        "fields": {
            "name": Field("Intake name", max_len=120, required=True),
            "intro": Field("What applicants should know", "text", max_len=4000),
            "opens_at": Field("Applications open", "datetime", required=True),
            "closes_at": Field("Applications close", "datetime", required=True),
            "published": Field("Published", "bool"),
        },
    },
    "offerings": {
        "model": Offering, "serialize": offering, "label": "programme on offer", "ordered": True,
        "name_field": "programme", "filters": ("intake_id",),
        "fields": {
            "intake_id": Field("Intake", max_len=36, required=True),
            "programme": Field("Programme", max_len=160, required=True),
            "department": Field("Department code", max_len=40),
            "level": Field("Level", max_len=20, choices=LEVELS),
            "seats": Field("Seats", "int", lo=0, hi=10000),
            "eligibility": Field("Who can apply", "text", max_len=3000),
            "fee_note": Field("Fees", max_len=300),
            "published": Field("Published", "bool"),
        },
    },
}


def now() -> datetime:
    return utcnow()
