"""One call that gives a service the shared Redis-backed features:

- the public-page cache (`ncit_common.cache`), and
- in-app notifications (`ncit_common.notify`, as `app.config["NOTIFY"]`).

    init_shared(app, redis_client, SERVICE_NAME)

Without Redis (tests, a quick local run) notifications are kept in memory and
there is no cache, unless a test passes `PUBLIC_CACHE` in the app config.
Settings: `CACHE_REDIS_URL` (a separate Redis for the cache; defaults to the
main one), `PUBLIC_CACHE_TTL` (seconds, default 60), `PUBLIC_CACHE=off`.
"""

import os

from .cache import PublicCache, init_public_cache
from .notify import MemoryNotifier, Notifier


def init_shared(app, client, service: str) -> None:
    if app.config.get("NOTIFY") is None:
        app.config["NOTIFY"] = Notifier(client, service) if client is not None else MemoryNotifier(service)

    cache = app.config.get("PUBLIC_CACHE")
    if cache is None and client is not None and os.environ.get("PUBLIC_CACHE", "on").lower() not in ("off", "0", "false"):
        cache = PublicCache(cache_client(client), service, ttl=int(os.environ.get("PUBLIC_CACHE_TTL", "60")))
    if cache:
        init_public_cache(app, cache)


def cache_client(default_client):
    """The Redis used for the cache: CACHE_REDIS_URL if set, otherwise the main one."""
    url = os.environ.get("CACHE_REDIS_URL", "")
    if not url:
        return default_client
    import redis

    return redis.Redis.from_url(url, decode_responses=True, socket_timeout=0.5, socket_connect_timeout=0.5)
