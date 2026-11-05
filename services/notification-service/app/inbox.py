"""In-app notifications: store what services queue on ncit:notify, and decide who sees what.

Who sees a notification:
- one sent `to` an email address: only that person;
- one sent to a `role`: everyone who holds that role *now* (checked from the
  roles in their sign-in token, so a removed role stops showing its
  notifications at once). A scoped one (e.g. role hod, scope dept:civil) only
  reaches holders of that scope. Super Admins are not sent every role's
  notifications: they would drown in them.

Role notifications are shown for ROLE_DAYS, personal ones for KEEP_DAYS;
older ones are deleted by the worker.
"""

import json
from datetime import timedelta

from ncit_common.notify import KINDS, clean_link
from sqlalchemy import and_, delete, exists, false, func, or_, select, true

from .models import Notification, NotificationRead, utcnow

KEEP_DAYS = 180
ROLE_DAYS = 30


def store(session, raw: str) -> Notification | None:
    """Save one queued notification (idempotent: the same queue id is stored once)."""
    note = json.loads(raw)
    if session.scalar(select(Notification.id).where(Notification.queue_id == note["id"])):
        return None
    to, role = (note.get("to") or "").lower(), "" if note.get("to") else (note.get("role") or "")
    if not to and not role:
        return None
    n = Notification(queue_id=note["id"], to_email=to, to_role=role, to_scope=note.get("scope") or "*",
                     kind=note.get("kind") if note.get("kind") in KINDS else "info",
                     title=str(note.get("title") or "")[:200] or "Notification", body=str(note.get("body") or "")[:1000],
                     link=clean_link(note.get("link")), service=str(note.get("service") or "")[:40])
    session.add(n)
    return n


def visible_to(principal):
    """SQL condition: the notifications this signed-in person may see."""
    conds = [Notification.to_email == principal.email.lower()]
    for grant in principal.roles:
        role, scope = grant.get("role"), grant.get("scope", "*")
        if not role:
            continue
        match_scope = true() if scope == "*" else or_(Notification.to_scope == "*", Notification.to_scope == scope)
        conds.append(and_(Notification.to_role == role, match_scope,
                          Notification.created_at >= utcnow() - timedelta(days=ROLE_DAYS)))
    return or_(*conds) if conds else false()


def is_read(email: str):
    return exists().where(NotificationRead.notification_id == Notification.id, NotificationRead.email == email.lower())


def unread_count(session, principal, cap: int = 99) -> int:
    sub = (select(Notification.id).where(visible_to(principal), ~is_read(principal.email)).limit(cap + 1)).subquery()
    return session.scalar(select(func.count()).select_from(sub)) or 0


def listing(session, principal, page: int = 1, per_page: int = 10, unread_only: bool = False):
    stmt = select(Notification, is_read(principal.email).label("read")).where(visible_to(principal))
    if unread_only:
        stmt = stmt.where(~is_read(principal.email))
    rows = session.execute(stmt.order_by(Notification.created_at.desc(), Notification.id)
                           .offset((page - 1) * per_page).limit(per_page + 1)).all()
    return [(n, bool(read)) for n, read in rows[:per_page]], len(rows) > per_page


def mark_read(session, principal, ids: list[str] | None) -> int:
    """Mark the given notifications (or all visible unread ones) as read. Only ones this person can see."""
    stmt = select(Notification.id).where(visible_to(principal), ~is_read(principal.email))
    if ids is not None:
        ids = [str(i) for i in ids][:200]
        if not ids:
            return 0
        stmt = stmt.where(Notification.id.in_(ids))
    found = session.scalars(stmt.limit(1000)).all()
    email = principal.email.lower()
    for nid in found:
        session.add(NotificationRead(notification_id=nid, email=email))
    return len(found)


def prune(session) -> int:
    now = utcnow()
    result = session.execute(delete(Notification).where(or_(
        Notification.created_at < now - timedelta(days=KEEP_DAYS),
        and_(Notification.to_role != "", Notification.created_at < now - timedelta(days=ROLE_DAYS)))))
    return result.rowcount or 0


def view(n: Notification, read: bool) -> dict:
    return {"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "read": read,
            "for_role": n.to_role or None, "created_at": n.created_at.isoformat() if n.created_at else None}
