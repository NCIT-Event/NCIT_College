"""Turn stream events into audit rows."""

import json
from datetime import UTC, datetime

from sqlalchemy import select

from .models import AuditEntry


def store_event(session, raw: str | dict) -> bool:
    """Insert one event; returns False when it was already stored."""
    event = json.loads(raw) if isinstance(raw, str) else raw
    if session.scalar(select(AuditEntry.id).where(AuditEntry.event_id == event["id"])):
        return False
    actor = event.get("actor") or {}
    session.add(AuditEntry(
        event_id=event["id"],
        type=event.get("type", "")[:64],
        service=event.get("service", "")[:64],
        actor_id=str(actor.get("id", ""))[:64],
        actor_email=str(actor.get("email", ""))[:254],
        entity=event.get("entity", "")[:64],
        entity_id=str(event.get("entity_id", ""))[:254],
        data=event.get("data") or {},
        ip=event.get("ip", "")[:64],
        at=datetime.fromtimestamp(float(event.get("at", 0)), tz=UTC),
    ))
    return True
