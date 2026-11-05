"""Token revocation shared by every service.

Access tokens live 15 minutes, so revocation only has to outlast that
window. Two kinds of entry:

- a token id (`jti`): one session signed out;
- a user id with a timestamp: every token for that user issued at or
  before the timestamp is rejected (role revoked, account suspended).

Services read the store on each authenticated request; auth-service
writes it. Production uses Redis; tests use the in-memory store.
"""

import time

ACCESS_TOKEN_TTL = 15 * 60


class MemoryRevocationStore:
    def __init__(self):
        self._jti: dict[str, float] = {}  # jti -> entry expiry
        self._user: dict[str, tuple[float, float]] = {}  # user -> (cutoff, entry expiry)

    def _alive(self, expires_at: float) -> bool:
        return expires_at > time.time()

    def revoke_token(self, jti: str, ttl: int = ACCESS_TOKEN_TTL) -> None:
        self._jti[jti] = time.time() + ttl

    def revoke_user(self, user_id: str, at: float | None = None, ttl: int = ACCESS_TOKEN_TTL) -> None:
        self._user[user_id] = (at if at is not None else time.time(), time.time() + ttl)

    def is_revoked(self, claims: dict) -> bool:
        jti = claims.get("jti")
        if jti and jti in self._jti and self._alive(self._jti[jti]):
            return True
        entry = self._user.get(claims.get("sub"))
        return entry is not None and self._alive(entry[1]) and claims.get("iat", 0) <= entry[0]


class RedisRevocationStore:
    def __init__(self, redis_client, prefix: str = "ncit:revoked"):
        self.r = redis_client
        self.prefix = prefix

    def revoke_token(self, jti: str, ttl: int = ACCESS_TOKEN_TTL) -> None:
        self.r.set(f"{self.prefix}:jti:{jti}", "1", ex=ttl)

    def revoke_user(self, user_id: str, at: float | None = None, ttl: int = ACCESS_TOKEN_TTL) -> None:
        self.r.set(f"{self.prefix}:user:{user_id}", str(at if at is not None else time.time()), ex=ttl)

    def is_revoked(self, claims: dict) -> bool:
        jti, sub = claims.get("jti"), claims.get("sub")
        jti_hit, cutoff = self.r.mget(f"{self.prefix}:jti:{jti}", f"{self.prefix}:user:{sub}")
        if jti_hit:
            return True
        return cutoff is not None and claims.get("iat", 0) <= float(cutoff)
