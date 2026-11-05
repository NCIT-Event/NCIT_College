"""Domain events over Redis Streams.

Producers call `publish(...)` and never know who listens; audit-service,
notification-service and future services consume the same stream.
"""

import json
import time
import uuid

STREAM = "ncit:events"


class EventPublisher:
    def __init__(self, redis_client=None, service: str = "unknown", stream: str = STREAM):
        self.r = redis_client
        self.service = service
        self.stream = stream

    def publish(self, event_type: str, *, actor: dict | None, entity: str, entity_id: str,
                data: dict | None = None, ip: str | None = None) -> dict:
        event = {
            "id": uuid.uuid4().hex,
            "type": event_type,
            "service": self.service,
            "at": time.time(),
            "actor": actor or {},
            "entity": entity,
            "entity_id": entity_id,
            "data": data or {},
            "ip": ip or "",
        }
        if self.r is not None:
            self.r.xadd(self.stream, {"event": json.dumps(event)}, maxlen=100_000, approximate=True)
        return event


class MemoryEventPublisher(EventPublisher):
    """Collects events in a list; used in tests and when Redis is not configured."""

    def __init__(self, service: str = "unknown"):
        super().__init__(None, service)
        self.events: list[dict] = []

    def publish(self, event_type, **kwargs):
        event = super().publish(event_type, **kwargs)
        self.events.append(event)
        return event
