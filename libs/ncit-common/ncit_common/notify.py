"""In-app notifications (the bell), stored and served by notification-service.

Services queue a notification on the Redis stream `ncit:notify`. The
notification worker stores it, and the person sees it under the bell in the
website header and the dashboard. A notification goes either to one person
(`to`, an email address) or to everyone holding a role (`role`, optionally
limited to a `scope` such as `dept:civil`).

    notify(to="ada@gmail.com", title="Your application was accepted",
           body="...", link="/apply", kind="success")
    notify(role="admission_officer", title="New application: Ada Lovelace", link="/dashboard/#applications")

`notify()` never raises: a notification is a convenience, and must not stop
the change that caused it. Links must be paths on this site.
"""

import json
import logging
import re
import time
import uuid

NOTIFY_STREAM = "ncit:notify"
KINDS = ("info", "success", "warning", "action")
SAFE_LINK = re.compile(r"^/(?![/\\])[^\s\\]*$")

log = logging.getLogger("ncit.notify")


def clean_link(link: str | None) -> str:
    link = (link or "").strip()
    return link if SAFE_LINK.match(link) and len(link) <= 300 else ""


class Notifier:
    def __init__(self, redis_client=None, service: str = "unknown", stream: str = NOTIFY_STREAM):
        self.r = redis_client
        self.service = service
        self.stream = stream

    def send(self, *, to: str | None = None, role: str | None = None, scope: str = "*", title: str,
             body: str = "", link: str = "", kind: str = "info") -> dict:
        if not to and not role:
            raise ValueError("a notification needs `to` or `role`")
        note = {
            "id": uuid.uuid4().hex,
            "to": (to or "").strip().lower()[:254],
            "role": (role or "")[:40] if not to else "",
            "scope": (scope or "*")[:80],
            "title": " ".join(str(title).split())[:200],
            "body": str(body or "")[:1000],
            "link": clean_link(link),
            "kind": kind if kind in KINDS else "info",
            "service": self.service,
            "at": time.time(),
        }
        if self.r is not None:
            self.r.xadd(self.stream, {"note": json.dumps(note)}, maxlen=100_000, approximate=True)
        return note


class MemoryNotifier(Notifier):
    """Keeps notifications in a list; used in tests and when Redis is not configured."""

    def __init__(self, service: str = "unknown"):
        super().__init__(None, service)
        self.sent: list[dict] = []

    def send(self, **kwargs):
        note = super().send(**kwargs)
        self.sent.append(note)
        return note


def notify(**kwargs) -> dict | None:
    """Queue a notification from inside a request. Never raises."""
    from flask import current_app

    try:
        notifier = current_app.config.get("NOTIFY")
        return notifier.send(**kwargs) if notifier is not None else None
    except Exception:
        log.exception("could not queue a notification")
        return None
