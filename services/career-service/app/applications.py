"""Job applications: apply once per vacancy (with a CV), HR moves them along, the applicant is emailed.

    submitted ──► shortlisted ──► interview ──► offered
        └──────────────┴──────────────┴──────────► rejected
"""

import re

from flask import current_app
from ncit_common import ApiError
from ncit_common.editor import emit
from ncit_common.notify import notify as send_notification

from .collections import now
from .db import db

MOVES = {
    "submitted": ("shortlisted", "interview", "rejected"),
    "shortlisted": ("interview", "offered", "rejected"),
    "interview": ("offered", "rejected"),
    "offered": ("rejected",),
    "rejected": ("shortlisted",),  # correcting a decision
}
LABELS = {"submitted": "Received", "shortlisted": "Shortlisted", "interview": "Interview", "offered": "Offered",
          "rejected": "Not taken forward", "withdrawn": "Withdrawn"}
PHONE_RE = re.compile(r"^\+?[\d\s-]{7,20}$")


def _log(app, status, by, message=""):
    app.history = [*(app.history or []), {"at": now().isoformat(), "status": status, "by": by, "message": message}]
    app.status = status


def mail(app, template, extra=None):
    try:
        current_app.config["MAIL"].send(app.email, template, {"name": app.full_name, "job": app.job.title, **(extra or {})})
    except Exception:
        current_app.logger.exception("could not queue %s", template)


def move(app, to_status, message, officer, notify=True):
    if to_status not in MOVES.get(app.status, ()):
        raise ApiError(409, "invalid_move", f"An application that is “{LABELS.get(app.status)}” can't be moved to "
                                            f"“{LABELS.get(to_status, to_status)}”.")
    message = (message or "").strip()[:4000]
    if to_status == "interview" and not message:
        raise ApiError(422, "message_required", "Give the interview date, time and place.")
    app.message = message
    _log(app, to_status, officer.email, message)
    db().commit()
    if notify:
        mail(app, "job_application_status", {"status": to_status, "message": message})
        send_notification(to=app.email, kind={"offered": "success", "interview": "action", "rejected": "warning"}.get(to_status, "info"),
                          title=f"{app.job.title}: {LABELS.get(to_status, to_status)}",
                          body=message or "Your application has moved to the next step.", link=f"/careers/{app.job.slug}")
    emit(f"job_applications.{to_status}", entity="job_applications", entity_id=app.id,
         data={"label": "job application", "name": app.job.title, "applicant": app.email, "emailed": notify})
    return app


def view(app, *, for_hr=False) -> dict:
    out = {"id": app.id, "status": app.status, "status_label": LABELS.get(app.status, app.status),
           "job": {"id": app.job.id, "slug": app.job.slug, "title": app.job.title, "department": app.job.department},
           "full_name": app.full_name, "email": app.email, "phone": app.phone, "qualification": app.qualification,
           "experience_years": app.experience_years, "cover_letter": app.cover_letter, "has_cv": bool(app.cv),
           "message": app.message, "created_at": app.created_at.isoformat() if app.created_at else None,
           "history": [{k: v for k, v in h.items() if for_hr or k != "by"} | {"status_label": LABELS.get(h["status"])}
                       for h in (app.history or [])]}
    if for_hr:
        out["hr_note"] = app.hr_note
        out["moves"] = list(MOVES.get(app.status, ()))
    return out
