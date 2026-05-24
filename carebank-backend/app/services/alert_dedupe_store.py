from __future__ import annotations

import hashlib
import os
import time
from threading import Lock
from typing import Any

try:
    from redis import Redis  # type: ignore[import-not-found]
    from redis.exceptions import RedisError  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    Redis = None  # type: ignore[assignment]
    RedisError = Exception  # type: ignore[assignment]


class AlertDedupeStore:
    def __init__(self) -> None:
        self.redis_url = os.getenv("REDIS_URL", "").strip()
        self.redis_prefix = os.getenv("ALERT_DEDUPE_PREFIX", "carebank:alert-dedupe").strip()
        self.redis: Redis | None = Redis.from_url(self.redis_url, decode_responses=True) if (self.redis_url and Redis is not None) else None
        self._memory: dict[str, float] = {}
        self._lock = Lock()

    def _key(self, user_id: str, alert_type: str, semantic_signature: str) -> str:
        return f"{user_id}:{alert_type}:{semantic_signature}"

    def should_suppress(self, user_id: str, alert_type: str, semantic_signature: str) -> bool:
        key = self._key(user_id, alert_type, semantic_signature)
        if self.redis is not None:
            try:
                return bool(self.redis.get(f"{self.redis_prefix}:{key}"))  # type: ignore[func-returns-value]
            except (RuntimeError, TimeoutError, ConnectionError, ValueError, RedisError, OSError):
                pass

        now = time.time()
        with self._lock:
            expiry = self._memory.get(key)
            if expiry is None:
                return False
            if expiry < now:
                self._memory.pop(key, None)
                return False
            return True

    def mark_sent(self, user_id: str, alert_type: str, semantic_signature: str, ttl_seconds: int) -> None:
        key = self._key(user_id, alert_type, semantic_signature)
        if self.redis is not None:
            try:
                self.redis.setex(f"{self.redis_prefix}:{key}", int(ttl_seconds), "1")  # type: ignore[func-returns-value]
            except (RuntimeError, TimeoutError, ConnectionError, ValueError, RedisError, OSError):
                pass
        with self._lock:
            self._memory[key] = time.time() + max(1, int(ttl_seconds))

    @staticmethod
    def make_signature(alert_source: str, evidence: Any) -> str:
        raw = f"{alert_source}:{repr(evidence)}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
