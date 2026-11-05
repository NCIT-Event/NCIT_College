"""Consume ncit:events from Redis Streams into the audit log.

Run:  python -m app.worker
Uses a consumer group, so several workers can share the load and an event
is acknowledged only after it is committed to Postgres.
"""

import logging
import os
import socket
import time

import redis
from ncit_common.events import STREAM
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .ingest import store_event

GROUP = "audit"
log = logging.getLogger("audit-worker")


def ensure_group(r):
    try:
        r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def process_batch(r, Session, consumer: str, block_ms: int = 5000) -> int:
    # first re-deliver anything this consumer read but never acknowledged, then new events
    handled = 0
    for start in ("0", ">"):
        replies = r.xreadgroup(GROUP, consumer, {STREAM: start}, count=100, block=None if start == "0" else block_ms)
        for _stream, messages in replies or []:
            for msg_id, fields in messages:
                session = Session()
                try:
                    store_event(session, fields["event"])
                    session.commit()
                    r.xack(STREAM, GROUP, msg_id)
                    handled += 1
                except Exception:
                    session.rollback()
                    log.exception("could not store event %s", msg_id)
                finally:
                    session.close()
    return handled


def main():
    logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","service":"audit-worker","message":"%(message)s"}')
    r = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    Session = sessionmaker(bind=create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True))
    consumer = os.environ.get("HOSTNAME", socket.gethostname())
    ensure_group(r)
    log.info("listening on %s as %s", STREAM, consumer)
    while True:
        try:
            process_batch(r, Session, consumer)
        except redis.ConnectionError:
            log.warning("redis unavailable, retrying in 3s")
            time.sleep(3)


if __name__ == "__main__":
    main()
