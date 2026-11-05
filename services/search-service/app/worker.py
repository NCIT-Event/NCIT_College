"""Keep the search index fresh.

Run:  python -m app.worker
- Rebuilds everything at start and every 15 minutes (a safety net).
- Listens to ncit:events: when a service announces a change (an editor saved
  something), that service's part of the index is rebuilt a few seconds later.
"""

import logging
import os
import socket
import time

import redis
from ncit_common.cache import PublicCache
from ncit_common.events import STREAM
from ncit_common.shared import cache_client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .indexer import SERVICE_SOURCE, http_fetcher, reindex
from .settings import source_urls

GROUP = "search"
FULL_EVERY = 15 * 60
log = logging.getLogger("search-worker")


def sources_for(events: list[dict]) -> set[str]:
    return {SERVICE_SOURCE[e.get("service")] for e in events if e.get("service") in SERVICE_SOURCE}


def main():
    import json

    logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","service":"search-worker","message":"%(message)s"}')
    r = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    Session = sessionmaker(bind=create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True), expire_on_commit=False)
    fetch = http_fetcher(source_urls())
    # search answers are cached by the web app (ncit_common.cache); a re-index makes them out of date
    results_cache = PublicCache(cache_client(r), "search-service")
    consumer = os.environ.get("HOSTNAME", socket.gethostname())
    try:
        r.xgroup_create(STREAM, GROUP, id="$", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise
    last_full = 0.0
    while True:
        try:
            if time.time() - last_full > FULL_EVERY:
                with Session() as s:
                    result = reindex(s, fetch)
                log.info("full reindex: %s", result)
                results_cache.bump()
                last_full = time.time()
                if any(isinstance(v, str) for v in result.values()):
                    last_full -= FULL_EVERY - 60  # a service wasn't ready (e.g. just starting): try again in a minute
            replies = r.xreadgroup(GROUP, consumer, {STREAM: ">"}, count=200, block=5000)
            batch, ids = [], []
            for _stream, messages in replies or []:
                for msg_id, fields in messages:
                    ids.append(msg_id)
                    try:
                        batch.append(json.loads(fields["event"]))
                    except (KeyError, ValueError):
                        pass
            changed = sources_for(batch)
            if changed:
                time.sleep(2)  # let a burst of edits settle; by then the changed service has also dropped its cached answers
                with Session() as s:
                    log.info("changed %s: %s", sorted(changed), reindex(s, fetch, sorted(changed)))
                results_cache.bump()
            if ids:
                r.xack(STREAM, GROUP, *ids)
        except redis.ConnectionError:
            log.warning("redis unavailable, retrying in 3s")
            time.sleep(3)


if __name__ == "__main__":
    main()
