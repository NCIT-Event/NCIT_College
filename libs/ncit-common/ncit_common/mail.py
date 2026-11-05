"""Outgoing email, sent by notification-service.

Services never talk to an SMTP server themselves. They queue a message on the
Redis stream `ncit:mail` with a template name and the data it needs;
notification-service renders it, sends it and keeps a log.

This is a separate stream from `ncit:events` on purpose: mail can contain
one-time sign-in codes, and the audit log must never store those.

    current_app.config["MAIL"].send("ada@gmail.com", "application_status",
                                    {"name": "Ada", "status": "accepted", ...})
"""

import json
import time
import uuid

MAIL_STREAM = "ncit:mail"


class MailQueue:
    def __init__(self, redis_client=None, service: str = "unknown", stream: str = MAIL_STREAM):
        self.r = redis_client
        self.service = service
        self.stream = stream

    def send(self, to: str, template: str, data: dict | None = None, *, sensitive: bool = False) -> dict:
        """Queue one email. `sensitive` = don't keep the body once sent (e.g. one-time codes)."""
        message = {"id": uuid.uuid4().hex, "to": to, "template": template, "data": data or {},
                   "sensitive": sensitive, "service": self.service, "at": time.time()}
        if self.r is not None:
            self.r.xadd(self.stream, {"mail": json.dumps(message)}, maxlen=50_000, approximate=True)
        return message


class MemoryMailQueue(MailQueue):
    """Keeps queued mail in a list; used in tests and when Redis is not configured."""

    def __init__(self, service: str = "unknown"):
        super().__init__(None, service)
        self.messages: list[dict] = []

    def send(self, to, template, data=None, *, sensitive=False):
        message = super().send(to, template, data, sensitive=sensitive)
        self.messages.append(message)
        return message
