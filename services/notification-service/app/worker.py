"""Send the emails queued on ncit:mail, and store the in-app notifications queued on ncit:notify.

Run:  python -m app.worker
Uses a consumer group, so several workers can share the load, and a message is
acknowledged only after its log entry is committed.
"""

import logging
import os
import socket
import time

import redis
from ncit_common.mail import MAIL_STREAM
from ncit_common.notify import NOTIFY_STREAM
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import inbox
from .delivery import deliver, sender_from_config
from .settings import config_from_env

GROUP = "notifications"
log = logging.getLogger("notification-worker")


def ensure_group(r):
    for stream in (MAIL_STREAM, NOTIFY_STREAM):
        try:
            r.xgroup_create(stream, GROUP, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise


def _handle(r, Session, stream, msg_id, fields, sender, keep_sensitive) -> bool:
    session = Session()
    try:
        if stream == MAIL_STREAM:
            m = deliver(session, fields["mail"], sender, keep_sensitive)
            session.commit()
            log.info("%s %s to %s", m.status, m.template, m.to)
        else:
            n = inbox.store(session, fields["note"])
            session.commit()
            if n is not None:
                log.info("notification for %s: %s", n.to_email or f"role {n.to_role}", n.title)
        r.xack(stream, GROUP, msg_id)
        return True
    except Exception:
        session.rollback()
        log.exception("could not handle %s %s", stream, msg_id)
        return False
    finally:
        session.close()


def process_batch(r, Session, consumer: str, sender, keep_sensitive=False, block_ms: int = 5000) -> int:
    """Emails (ncit:mail) and in-app notifications (ncit:notify), read together so neither waits for the other."""
    handled = 0
    streams = (MAIL_STREAM, NOTIFY_STREAM)
    # anything read earlier but not acknowledged first, then new messages
    for start, block in (("0", None), (">", block_ms)):
        replies = r.xreadgroup(GROUP, consumer, {s: start for s in streams}, count=50, block=block)
        for stream, messages in replies or []:
            for msg_id, fields in messages:
                handled += _handle(r, Session, stream, msg_id, fields, sender, keep_sensitive)
    return handled


def prune_old(Session) -> None:
    with Session() as session:
        removed = inbox.prune(session)
        session.commit()
    if removed:
        log.info("removed %s old notifications", removed)


def main():
    logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","service":"notification-worker","message":"%(message)s"}')
    r = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    Session = sessionmaker(bind=create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True), expire_on_commit=False)
    consumer = os.environ.get("HOSTNAME", socket.gethostname())
    sender = sender_from_config(config_from_env())
    keep = os.environ.get("MAIL_KEEP_SENSITIVE", "false").lower() in ("1", "true", "yes")
    ensure_group(r)
    log.info("listening on %s and %s as %s (%s)", MAIL_STREAM, NOTIFY_STREAM, consumer, "SMTP" if os.environ.get("SMTP_HOST") else "log only, no SMTP_HOST")
    last_prune = 0.0
    while True:
        try:
            if time.time() - last_prune > 3600:
                prune_old(Session)
                last_prune = time.time()
            process_batch(r, Session, consumer, sender, keep)
        except redis.ConnectionError:
            log.warning("redis unavailable, retrying in 3s")
            time.sleep(3)


if __name__ == "__main__":
    main()
