"""Turn a queued mail message into a sent email and a log entry.

Sending: SMTP when SMTP_HOST is set (with STARTTLS by default), otherwise the
message is only logged (status "logged"), which is what local development and
tests use. Sensitive messages (sign-in codes) keep no body once handled,
unless MAIL_KEEP_SENSITIVE is on (local development, to read the codes).
"""

import json
import smtplib
from email.message import EmailMessage

from sqlalchemy import select

from .models import Message, utcnow
from .templates import render

REDACTED = "[Removed after sending: this email contained a one-time sign-in code.]"
REDACTED_SUBJECT = "Sign-in code (removed)"


class SmtpSender:
    def __init__(self, host, port=587, user="", password="", starttls=True, sender="NCIT <no-reply@ncit.edu.np>"):
        self.host, self.port, self.user, self.password = host, int(port), user, password
        self.starttls, self.sender = starttls, sender

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.sender, to, subject
        msg.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
            if self.starttls:
                smtp.starttls()
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(msg)


class LogOnlySender:
    """No mail server configured: record the email, send nothing."""

    logged = True

    def send(self, to, subject, body):
        return None


def sender_from_config(cfg) -> object:
    if cfg.get("SMTP_HOST"):
        return SmtpSender(cfg["SMTP_HOST"], cfg.get("SMTP_PORT", 587), cfg.get("SMTP_USER", ""),
                          cfg.get("SMTP_PASSWORD", ""), cfg.get("SMTP_STARTTLS", True), cfg.get("MAIL_FROM"))
    return LogOnlySender()


def attempt(message: Message, sender, data: dict | None, keep_sensitive: bool) -> None:
    """Send (or log) one message and record the outcome on it."""
    message.attempts += 1
    try:
        if data is not None:
            message.subject, message.body = render(message.template, data)
        sender.send(message.to, message.subject, message.body)
        message.status = "logged" if getattr(sender, "logged", False) else "sent"
        message.error, message.sent_at = "", utcnow()
    except Exception as exc:  # noqa: BLE001  (any send failure is recorded in the Email log; a Super Admin can retry)
        message.status, message.error = "failed", f"{type(exc).__name__}: {exc}"[:500]
    if message.sensitive and not keep_sensitive and message.status != "failed":
        message.body, message.subject = REDACTED, REDACTED_SUBJECT


def deliver(session, raw: str, sender, keep_sensitive: bool = False) -> Message:
    """Handle one message from the ncit:mail stream. Safe to call twice for the same message."""
    item = json.loads(raw)
    existing = session.scalar(select(Message).where(Message.queue_id == item["id"]))
    if existing is not None:
        return existing
    message = Message(queue_id=item["id"], to=item["to"], template=item["template"], service=item.get("service", ""), attempts=0,
                      sensitive=bool(item.get("sensitive")))
    session.add(message)
    attempt(message, sender, item.get("data") or {}, keep_sensitive)
    if message.status == "failed" and message.sensitive:
        message.body, message.subject = REDACTED, REDACTED_SUBJECT  # a failed code email is never retried: the person just asks for a new code
    return message
