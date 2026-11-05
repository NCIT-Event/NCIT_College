"""Joining clubs.

- Any signed-in college account can ask to join a club that is accepting members.
- The request waits until an ECA Admin approves or rejects it.
- Someone rejected (or who left) may ask again later.
"""

from ncit_common import ApiError
from ncit_common.editor import emit
from ncit_common.notify import notify
from sqlalchemy import func, select

from .collections import now
from .db import db
from .models import Club, Membership

ACTIVE = ("pending", "approved")


def view(m: Membership) -> dict:
    return {"id": m.id, "email": m.email, "name": m.name, "status": m.status, "position": m.position,
            "message": m.message, "created_at": m.created_at.isoformat() if m.created_at else None,
            "decided_at": m.decided_at.isoformat() if m.decided_at else None, "decided_by": m.decided_by}


def find(club: Club, email: str) -> Membership | None:
    return db().scalar(select(Membership).where(Membership.club_id == club.id, Membership.email == email))


def _event(event_type: str, club: Club, m: Membership, **extra) -> None:
    emit(event_type, entity="memberships", entity_id=m.id,
         data={"label": "club membership", "name": club.name, "club_id": club.id, "email": m.email, **extra})


def join(club: Club, principal, message: str) -> Membership:
    if not club.published or not club.join_open:
        raise ApiError(409, "join_closed", "This club isn't taking new members right now.")
    m = find(club, principal.email)
    if m is not None and m.status in ACTIVE:
        code = "already_member" if m.status == "approved" else "already_requested"
        text = "You're already a member of this club." if m.status == "approved" else "Your request is waiting for approval."
        raise ApiError(409, code, text)
    if m is None:
        m = Membership(club_id=club.id, email=principal.email)
        db().add(m)
    m.user_id, m.name, m.message = principal.user_id, principal.name or "", (message or "").strip()[:500]
    m.status, m.position, m.created_at, m.decided_at, m.decided_by = "pending", "", now(), None, ""
    db().commit()
    _event("memberships.requested", club, m)
    notify(role="eca_admin", kind="action", title=f"Join request: {m.name or m.email} for {club.name}",
           body=m.message or "No message.", link="/dashboard/#requests")
    return m


def leave(club: Club, principal) -> None:
    m = find(club, principal.email)
    if m is None or m.status not in ACTIVE:
        raise ApiError(404, "not_member", "You aren't a member of this club.")
    was = m.status
    m.status, m.position = "left", ""
    db().commit()
    _event("memberships.withdrawn" if was == "pending" else "memberships.left", club, m)


def decide(club: Club, m: Membership, data: dict, admin_email: str) -> Membership:
    changed = []
    status = data.get("status")
    if status is not None:
        if status not in ("approved", "rejected", "left"):
            raise ApiError(422, "invalid_field", "Choose approve, reject or remove.")
        if status != m.status:
            m.status, m.decided_at, m.decided_by = status, now(), admin_email
            if status != "approved":
                m.position = ""
            changed.append("status")
    if "position" in data:
        position = str(data["position"] or "").strip()
        if len(position) > 60:
            raise ApiError(422, "invalid_field", "Position is too long (60 characters at most).")
        if position and m.status != "approved":
            raise ApiError(422, "invalid_field", "Approve the member before giving them a position.")
        if position != m.position:
            m.position = position
            changed.append("position")
    db().commit()
    if changed:
        kind = {"approved": "approved", "rejected": "rejected", "left": "removed"}.get(m.status, "updated")
        _event(f"memberships.{kind if 'status' in changed else 'updated'}", club, m, fields=changed,
               position=m.position)
        link = f"/clubs/{club.slug}"
        if "status" in changed and m.status == "approved":
            notify(to=m.email, kind="success", title=f"Welcome to {club.name}", body="Your request to join was approved.", link=link)
        elif "status" in changed and m.status == "rejected":
            notify(to=m.email, kind="warning", title=f"Your request to join {club.name} wasn't approved", link=link)
        elif "status" in changed and m.status == "left":
            notify(to=m.email, kind="warning", title=f"You were removed from {club.name}", link=link)
        elif "position" in changed and m.position:
            notify(to=m.email, kind="success", title=f"You're now {m.position} of {club.name}", link=link)
    return m


def committee(club: Club) -> list[dict]:
    rows = db().scalars(select(Membership).where(Membership.club_id == club.id, Membership.status == "approved",
                                                 Membership.position != "").order_by(Membership.decided_at)).all()
    return [{"name": m.name, "position": m.position} for m in rows]


def pending_total() -> int:
    return db().scalar(select(func.count(Membership.id)).where(Membership.status == "pending")) or 0
