from __future__ import annotations

import os
import time
from threading import Lock

try:
    from redis import Redis  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    Redis = None  # type: ignore[assignment]


class IdempotencyStore:
    def __init__(self) -> None:
        self.redis_url = os.getenv("REDIS_URL", "").strip()
        self.redis_prefix = os.getenv("IDEMPOTENCY_PREFIX", "carebank:idempotency").strip()
        self.redis: Redis | None = Redis.from_url(self.redis_url, decode_responses=True) if (self.redis_url and Redis is not None) else None
        self._memory: dict[str, float] = {}
        self._lock = Lock()

    @staticmethod
    def make_key(event_type: str, user_id: str, correlation_id: str, resource_id: str | None = None) -> str:
        suffix = f":{resource_id}" if resource_id else ""
        return f"{event_type}:{user_id}:{correlation_id}{suffix}"

    def is_processed(self, key: str) -> bool:
        if self.redis is not None:
            # best-effort redis read; fallback to memory if unavailable
            try:
                return bool(self.redis.get(f"{self.redis_prefix}:{key}"))  # type: ignore[func-returns-value]
            except Exception:
                pass
        now = time.time()
        with self._lock:
            expiry = self._memory.get(key)
            if expiry is None:
                return False
            if expiry < now:
                del self._memory[key]
                return False
            return True

    def mark_processed(self, key: str, ttl_seconds: int = 86400) -> None:
        if self.redis is not None:
            try:
                self.redis.setex(f"{self.redis_prefix}:{key}", ttl_seconds, "1")  # type: ignore[func-returns-value]
            except Exception:
                pass
        with self._lock:
            self._memory[key] = time.time() + ttl_seconds

    def clear(self, key: str) -> None:
        if self.redis is not None:
            try:
                self.redis.delete(f"{self.redis_prefix}:{key}")  # type: ignore[func-returns-value]
            except Exception:
                pass
        with self._lock:
            self._memory.pop(key, None)
