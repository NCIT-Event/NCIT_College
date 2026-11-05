"""Alumni registration and verification.

- An alumnus signs in (emailed code, or a college account), fills in their
  profile and sends it: status "pending".
- The Alumni Coordinator checks the name, programme, year and Pokhara
  University registration number against the college's records and marks
  the profile "verified" or "rejected" (with a reason). The alumnus is emailed.
- Verified alumni who agree appear in the public directory. Changing any of
  the checked details sends the profile back for verification.
"""

import re
from functools import partial

from flask import current_app
from ncit_common import ApiError
from ncit_common.editor import emit
from ncit_common.fields import Field as _Field
from ncit_common.notify import notify

from .db import db
from .models import utcnow

Field = partial(_Field, media_root="alumni")

CHECKED = ("full_name", "programme", "graduation_year", "registration_no")
FIELDS = {
    "full_name": Field("Full name", max_len=160),
    "programme": Field("Programme", max_len=120),
    "graduation_year": Field("Year of graduation", max_len=4),
    "registration_no": Field("PU registration number", max_len=40),
    "phone": Field("Phone", max_len=30),
    "current_role": Field("Current role", max_len=120),
    "employer": Field("Organisation", max_len=120),
    "city": Field("City", max_len=80),
    "country": Field("Country", max_len=80),
    "linkedin_url": Field("LinkedIn", "url", max_len=300),
    "bio": Field("A line about you", max_len=400),
    "photo": Field("Photo", "media"),
    "show_in_directory": Field("Show me in the alumni directory", "bool"),
}
REQUIRED = ("full_name", "programme", "graduation_year", "registration_no")
LABELS = {"draft": "Not sent yet", "pending": "Waiting for verification", "verified": "Verified", "rejected": "Not verified"}


def check(p) -> None:
    if p.graduation_year and not re.fullmatch(r"(19|20)\d\d", p.graduation_year):
        raise ApiError(422, "invalid_field", "Year of graduation must be a year, like 2015.")
    if p.graduation_year and not 2001 <= int(p.graduation_year) <= utcnow().year + 1:
        raise ApiError(422, "invalid_field", "NCIT's first batch started in 2001; check the year.")
    if p.linkedin_url and not re.match(r"^https://([a-z]{2,3}\.)?linkedin\.com/", p.linkedin_url):
        raise ApiError(422, "invalid_field", "Use your LinkedIn profile link (https://www.linkedin.com/in/…).")


def after_edit(p, changed: list[str]) -> None:
    """Editing a checked detail of a verified or rejected profile sends it back to the coordinator."""
    if p.status in ("verified", "rejected") and any(c in CHECKED for c in changed):
        p.status, p.featured, p.verified_at, p.verified_by = "pending", False, None, ""
        p.submitted_at = utcnow()


def submit(p) -> None:
    gaps = [FIELDS[k].label for k in REQUIRED if not getattr(p, k)]
    if gaps:
        raise ApiError(422, "incomplete", "Fill in: " + ", ".join(gaps) + ".")
    if p.status in ("verified", "pending"):
        raise ApiError(409, "already_sent", "Your profile has already been sent.")
    p.status, p.submitted_at, p.review_note = "pending", utcnow(), ""
    db().commit()
    emit("alumni.submitted", entity="alumni", entity_id=p.id, data={"label": "alumni profile", "name": p.full_name})
    notify(role="alumni_coordinator", kind="action", title=f"Alumni registration to verify: {p.full_name}",
           body=f"{p.programme} · {p.graduation_year}", link="/dashboard/#alumni-review")


def decide(p, status: str, message: str, coordinator) -> None:
    if status not in ("verified", "rejected"):
        raise ApiError(422, "invalid_field", "Choose verify or reject.")
    if p.status == "draft":
        raise ApiError(409, "not_sent", "This profile hasn't been sent for verification yet.")
    message = (message or "").strip()[:2000]
    if status == "rejected" and not message:
        raise ApiError(422, "message_required", "Tell the alumnus why, so they can correct it.")
    p.status, p.review_note = status, message if status == "rejected" else ""
    p.verified_by, p.verified_at = coordinator.email, utcnow() if status == "verified" else None
    if status == "rejected":
        p.featured = False
    db().commit()
    try:
        current_app.config["MAIL"].send(p.email, "alumni_status", {"name": p.full_name, "status": status,
                                                                    "message": message, "listed": p.show_in_directory})
    except Exception:
        current_app.logger.exception("could not queue alumni_status")
    if status == "verified":
        notify(to=p.email, kind="success", title="You're verified as NCIT alumni",
               body="Your profile is in the alumni directory." if p.show_in_directory else "Welcome back to the NCIT community.",
               link="/alumni/join")
    else:
        notify(to=p.email, kind="action", title="We couldn't verify your alumni registration",
               body=message, link="/alumni/join")
    emit(f"alumni.{status}", entity="alumni", entity_id=p.id,
         data={"label": "alumni profile", "name": p.full_name, "email": p.email})


def public_card(p) -> dict:
    return {"id": p.id, "full_name": p.full_name, "programme": p.programme, "graduation_year": p.graduation_year,
            "current_role": p.current_role, "employer": p.employer, "city": p.city, "country": p.country,
            "linkedin_url": p.linkedin_url, "bio": p.bio, "photo": p.photo}


def view(p, *, for_coordinator=False) -> dict:
    out = public_card(p) | {"email": p.email, "phone": p.phone, "registration_no": p.registration_no,
                            "show_in_directory": p.show_in_directory, "status": p.status,
                            "status_label": LABELS.get(p.status, p.status), "review_note": p.review_note,
                            "submitted_at": p.submitted_at.isoformat() if p.submitted_at else None,
                            "verified_at": p.verified_at.isoformat() if p.verified_at else None}
    if for_coordinator:
        out |= {"featured": p.featured, "verified_by": p.verified_by}
    return out
