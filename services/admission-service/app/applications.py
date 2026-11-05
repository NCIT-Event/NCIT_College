"""The life of an application, and the rules for each step.

    draft ──submit──► submitted ──► under_review ──► accepted
                         │               │      └──► waitlisted ──► accepted / rejected
                         │               └─────────► rejected
                         └──► documents_requested ──(applicant fixes, submits again)──► submitted

- The applicant edits only while the application is a draft, or when the
  office has asked for more documents.
- Every step is kept in the application's history, with who took it.
- The applicant is emailed when they submit and whenever the office changes
  the status (with the office's message, if any).
"""

import re
from functools import partial

from flask import current_app
from ncit_common import ApiError
from ncit_common.editor import emit
from ncit_common.fields import Field as _Field
from ncit_common.notify import notify as send_notification
from sqlalchemy import func, select

from .collections import intake_status, now
from .db import db
from .models import Application, ApplicationEvent

Field = partial(_Field, media_root="admissions")

EDITABLE = ("draft", "documents_requested")
DECISIONS = ("accepted", "waitlisted", "rejected")
# what the office may move an application to, from each status
OFFICE_MOVES = {
    "submitted": ("under_review", "documents_requested", *DECISIONS),
    "under_review": ("documents_requested", *DECISIONS),
    "documents_requested": ("under_review", "rejected"),
    "accepted": ("waitlisted", "rejected"),  # correcting a decision
    "waitlisted": ("accepted", "rejected"),
    "rejected": ("accepted", "waitlisted"),
}
LABELS = {"draft": "Draft", "submitted": "Submitted", "under_review": "Under review",
          "documents_requested": "More documents needed", "accepted": "Accepted", "waitlisted": "Waiting list",
          "rejected": "Not accepted", "withdrawn": "Withdrawn"}
DOCUMENTS = {"photo": ("Passport-size photo", "image"), "transcript": ("Academic transcript (PDF)", "pdf"),
             "citizenship": ("Citizenship or passport (PDF)", "pdf")}

# what applicants fill in
APPLICANT_FIELDS = {
    "offering_id": Field("Programme", max_len=36),
    "second_choice_id": Field("Second choice", max_len=36),
    "full_name": Field("Full name", max_len=160),
    "date_of_birth": Field("Date of birth", max_len=10),
    "gender": Field("Gender", max_len=20, choices=("", "female", "male", "other", "prefer_not")),
    "phone": Field("Mobile number", max_len=30),
    "address": Field("Address", max_len=300),
    "guardian_name": Field("Parent or guardian", max_len=160),
    "guardian_phone": Field("Guardian's phone", max_len=30),
    "school": Field("School or college", max_len=200),
    "board": Field("Board", max_len=80),
    "passed_year": Field("Year passed", max_len=4),
    "grade": Field("GPA or percentage", max_len=20),
    "entrance_score": Field("Entrance score", max_len=20),
}
REQUIRED_TO_SUBMIT = ("full_name", "date_of_birth", "phone", "address", "guardian_name", "school", "board",
                      "passed_year", "grade", "photo", "transcript")
DATE_RE = re.compile(r"^(19|20)\d\d-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
PHONE_RE = re.compile(r"^\+?[\d\s-]{7,20}$")


def check_fields(app: Application) -> None:
    # "no second choice" arrives as an empty string; the column holds an id or NULL
    if not app.second_choice_id:
        app.second_choice_id = None
    if not app.offering_id:
        raise ApiError(422, "invalid_field", "Choose a programme.")
    with db().no_autoflush:
        _check_fields(app)


def _check_fields(app: Application) -> None:
    if app.date_of_birth and not DATE_RE.match(app.date_of_birth):
        raise ApiError(422, "invalid_field", "Date of birth must look like 2007-04-15.")
    for name, label in (("phone", "Mobile number"), ("guardian_phone", "Guardian's phone")):
        if getattr(app, name) and not PHONE_RE.match(getattr(app, name)):
            raise ApiError(422, "invalid_field", f"{label} doesn't look like a phone number.")
    if app.passed_year and not re.fullmatch(r"(19|20)\d\d", app.passed_year):
        raise ApiError(422, "invalid_field", "Year passed must be a year, like 2025.")
    from .models import Offering

    for key in ("offering_id", "second_choice_id"):
        value = getattr(app, key)
        if not value:
            continue
        o = db().get(Offering, value)
        if o is None or o.intake_id != app.intake_id or not o.published:
            raise ApiError(422, "invalid_field", "Choose a programme from this intake.")
    if app.second_choice_id and app.second_choice_id == app.offering_id:
        app.second_choice_id = None


def missing(app: Application) -> list[str]:
    labels = {**{k: f.label for k, f in APPLICANT_FIELDS.items()}, **{k: v[0] for k, v in DOCUMENTS.items()}}
    return [labels[k] for k in REQUIRED_TO_SUBMIT if not getattr(app, k)]


def _record(app: Application, to_status: str, by: str, message: str = "", emailed: bool = False) -> None:
    app.history.append(ApplicationEvent(from_status=app.status, to_status=to_status, by=by, message=message,
                                        emailed=emailed))
    app.status = to_status


def _mail(app: Application, template: str, extra: dict | None = None) -> None:
    data = {"name": app.full_name, "reference": app.reference, "programme": app.offering.programme,
            "intake": app.intake.name, **(extra or {})}
    try:
        current_app.config["MAIL"].send(app.email, template, data)
    except Exception:  # a mail outage must not lose the application
        current_app.logger.exception("could not queue %s for %s", template, app.id)


def _new_reference(app: Application) -> str:
    year = (app.intake.opens_at or now()).year
    prefix = f"NCIT-{year}-"
    last = db().scalar(select(func.max(Application.reference)).where(Application.reference.like(f"{prefix}%")))
    n = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:05d}"


def submit(app: Application, principal) -> Application:
    if app.status not in EDITABLE:
        raise ApiError(409, "not_editable", "This application has already been sent.")
    if intake_status(app.intake, now()) != "open" and app.status == "draft":
        raise ApiError(409, "intake_closed", "Applications for this intake are closed.")
    gaps = missing(app)
    if gaps:
        raise ApiError(422, "incomplete", "Fill in: " + ", ".join(gaps) + ".")
    first = app.reference is None
    if first:
        app.reference = _new_reference(app)
        app.submitted_at = now()
    _record(app, "submitted", principal.email, "" if first else "Updated and sent again by the applicant.", emailed=first)
    db().commit()
    if first:
        _mail(app, "application_submitted")
    send_notification(role="admission_officer", kind="action",
                      title=f"{'New application' if first else 'Application sent again'}: {app.full_name or app.email}",
                      body=f"{app.reference} · {app.offering.programme} · {app.intake.name}",
                      link=f"/dashboard/#applications/{app.id}")
    emit("applications.submitted", entity="applications", entity_id=app.id,
         data={"label": "application", "name": app.reference, "programme": app.offering.programme, "resubmitted": not first})
    return app


def withdraw(app: Application, principal) -> Application:
    if app.status in ("accepted", "rejected", "withdrawn"):
        raise ApiError(409, "not_withdrawable", "This application can't be withdrawn now. Contact the admissions office.")
    _record(app, "withdrawn", principal.email)
    db().commit()
    emit("applications.withdrawn", entity="applications", entity_id=app.id,
         data={"label": "application", "name": app.reference or "draft"})
    return app


def move(app: Application, to_status: str, message: str, officer, notify: bool = True) -> Application:
    allowed = OFFICE_MOVES.get(app.status, ())
    if to_status not in allowed:
        raise ApiError(409, "invalid_move", f"An application that is “{LABELS.get(app.status, app.status)}” can't be "
                                            f"moved to “{LABELS.get(to_status, to_status)}”.")
    message = (message or "").strip()[:4000]
    if to_status == "documents_requested" and not message:
        raise ApiError(422, "message_required", "Tell the applicant what's needed.")
    app.message = message
    _record(app, to_status, officer.email, message, emailed=notify)
    db().commit()
    if notify:
        _mail(app, "application_status", {"status": to_status, "message": message})
        send_notification(to=app.email, kind=STATUS_KIND.get(to_status, "info"),
                          title=f"Your application: {label(to_status)}",
                          body=message or f"{app.reference} · {app.offering.programme}", link="/apply")
    emit(f"applications.{to_status}", entity="applications", entity_id=app.id,
         data={"label": "application", "name": app.reference, "programme": app.offering.programme,
               "applicant": app.email, "emailed": notify})
    return app


# how each step looks under the applicant's bell
STATUS_KIND = {"accepted": "success", "documents_requested": "action", "rejected": "warning"}


def label(status: str) -> str:
    return LABELS.get(status, status)


def view(app: Application, *, for_office: bool = False) -> dict:
    out = {
        "id": app.id, "reference": app.reference, "email": app.email, "status": app.status, "status_label": label(app.status),
        "intake": {"id": app.intake.id, "name": app.intake.name, "status": intake_status(app.intake, now()),
                   "closes_at": app.intake.closes_at.isoformat()},
        "offering": {"id": app.offering.id, "programme": app.offering.programme},
        "second_choice": {"id": app.second_choice.id, "programme": app.second_choice.programme} if app.second_choice else None,
        **{k: getattr(app, k) for k in APPLICANT_FIELDS if k not in ("offering_id", "second_choice_id")},
        "documents": {k: bool(getattr(app, k)) for k in DOCUMENTS},
        "message": app.message, "editable": app.status in EDITABLE, "missing": missing(app),
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        "history": [{"at": h.at.isoformat(), "status": h.to_status, "status_label": label(h.to_status),
                     "message": h.message, **({"by": h.by, "emailed": h.emailed} if for_office else {})}
                    for h in app.history],
    }
    if for_office:
        out["officer_note"] = app.officer_note
        out["moves"] = list(OFFICE_MOVES.get(app.status, ()))
    return out
