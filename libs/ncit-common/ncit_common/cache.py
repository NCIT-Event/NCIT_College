"""Public-page cache in Redis, shared by every service.

Each service's anonymous `public` routes (news, events, departments, search …)
are answered from Redis when the same address was asked for recently, without
touching the database. It is safe because:

- **Only public data.** Only GET requests to the blueprint named `public` are
  cached. Those views never look at who is asking, so one visitor's answer is
  right for everyone. Signed-in routes (`/me/…`, editors) are never cached.
- **Changes show at once.** Any successful change made through a service (an
  editor saving, a student registering, which changes "places left") gives
  that service's cache a new version, so every cached answer for it is
  dropped in one step. Background jobs that change public data (the search
  worker) call `bump()` too.
- **Time-based changes are bounded.** Things that change by the clock (a
  banner's "show until", registration closing) can be at most `ttl` seconds
  late (60 by default, `PUBLIC_CACHE_TTL`).
- **It fails open.** If Redis is slow or down, the request is answered from
  the database as before.

Keys: `ncit:cache:<service>:ver` (the version) and
`ncit:cache:<service>:<version>:<hash of path and query>` (an answer).
Use a separate Redis with an LRU eviction policy (`CACHE_REDIS_URL`), so
cached pages can never push out sessions or the event streams.
"""

import hashlib
import json
import logging
import time

from flask import Response, g, request

PREFIX = "ncit:cache"
CACHEABLE_TYPES = ("application/json", "application/xml", "text/xml", "text/plain")
MAX_QUERY = 300           # longer query strings aren't cached (no flooding the cache with junk keys)
MAX_BODY = 1_000_000      # bigger answers aren't cached

log = logging.getLogger("ncit.cache")


class PublicCache:
    def __init__(self, client, service: str, ttl: int = 60, blueprints: tuple[str, ...] = ("public",)):
        self.r = client
        self.service = service
        self.ttl = ttl
        self.blueprints = blueprints
        self._warned = 0.0

    # --- storage (overridden by MemoryPublicCache) ---
    def _get(self, key):
        return self.r.get(key)

    def _set(self, key, value, ttl=None):
        self.r.set(key, value, ex=ttl)

    def _setnx(self, key, value):
        self.r.set(key, value, nx=True)

    # --- versioning ---
    @property
    def version_key(self) -> str:
        return f"{PREFIX}:{self.service}:ver"

    def version(self) -> str:
        v = self._get(self.version_key)
        if v is None:  # first use, or evicted: start a new version (never revive old answers)
            self._setnx(self.version_key, str(time.time_ns()))
            v = self._get(self.version_key)
        return str(v)

    def bump(self) -> None:
        """Drop every cached answer of this service (they become unreachable and expire)."""
        try:
            self._set(self.version_key, str(time.time_ns()))
        except Exception as exc:  # noqa: BLE001
            self._warn(exc)

    def key(self, version: str, full_path: str) -> str:
        digest = hashlib.sha256(full_path.encode()).hexdigest()[:32]
        return f"{PREFIX}:{self.service}:{version}:{digest}"

    def load(self, version: str, full_path: str) -> dict | None:
        raw = self._get(self.key(version, full_path))
        return json.loads(raw) if raw else None

    def store(self, version: str, full_path: str, payload: dict) -> None:
        self._set(self.key(version, full_path), json.dumps(payload), self.ttl)

    def _warn(self, exc) -> None:
        if time.time() - self._warned > 60:  # once a minute at most
            self._warned = time.time()
            log.warning("public cache unavailable, answering from the database: %s", exc)


class MemoryPublicCache(PublicCache):
    """In-process cache for tests."""

    def __init__(self, service: str = "test", ttl: int = 60, **kw):
        super().__init__(None, service, ttl, **kw)
        self.data: dict[str, tuple[str, float | None]] = {}

    def _get(self, key):
        value = self.data.get(key)
        if value is None or (value[1] is not None and value[1] < time.time()):
            return None
        return value[0]

    def _set(self, key, value, ttl=None):
        self.data[key] = (value, time.time() + ttl if ttl else None)

    def _setnx(self, key, value):
        if self._get(key) is None:
            self._set(key, value)


def _full_path() -> str:
    qs = request.query_string.decode("latin-1")
    # the same question asked with its parameters in another order is the same answer
    ordered = "&".join(sorted(qs.split("&"))) if qs else ""
    return request.path + ("?" + ordered if ordered else "")


def init_public_cache(app, cache: PublicCache) -> None:
    app.extensions["public_cache"] = cache
    cache.bump()  # a new deploy may change answers: start fresh

    @app.before_request
    def _serve_from_cache():
        g.cache_state = None
        if request.method not in ("GET", "HEAD") or request.blueprint not in cache.blueprints:
            return None
        if len(request.query_string) > MAX_QUERY:
            return None
        try:
            g.cache_version = cache.version()
            hit = cache.load(g.cache_version, _full_path())
        except Exception as exc:  # noqa: BLE001
            cache._warn(exc)
            return None
        g.cache_state = "MISS"
        if hit is None:
            return None
        resp = Response(hit["body"], status=200, mimetype=hit["mimetype"])
        if hit.get("cache_control"):
            resp.headers["Cache-Control"] = hit["cache_control"]
        resp.headers["X-App-Cache"] = "HIT"
        g.cache_state = "HIT"
        return resp

    @app.after_request
    def _store_or_invalidate(resp):
        state = g.get("cache_state")
        if request.method in ("GET", "HEAD", "OPTIONS"):
            if state == "MISS" and resp.status_code == 200 and not resp.direct_passthrough \
                    and resp.mimetype in CACHEABLE_TYPES and "Set-Cookie" not in resp.headers:
                body = resp.get_data(as_text=True)
                if len(body) <= MAX_BODY:
                    try:
                        cache.store(g.cache_version, _full_path(), {
                            "body": body, "mimetype": resp.mimetype,
                            "cache_control": resp.headers.get("Cache-Control", "")})
                    except Exception as exc:  # noqa: BLE001
                        cache._warn(exc)
                resp.headers["X-App-Cache"] = "MISS"
        elif 200 <= resp.status_code < 300:
            cache.bump()  # something changed: public answers must be rebuilt
        return resp
