from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.services.security_audit import SecurityAuditLogger

try:
    from redis import Redis  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    Redis = None  # type: ignore[assignment]


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int


class RateLimiter:
    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = settings.rate_limit_enabled
        self.limit_per_minute = settings.rate_limit_per_minute
        self.redis_url = os.getenv("REDIS_URL", "").strip()
        self.redis: Redis | None = Redis.from_url(self.redis_url, decode_responses=True) if (self.redis_url and Redis is not None) else None
        self._memory: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self.audit = SecurityAuditLogger()

    async def check(self, key: str, *, limit: int | None = None, window_seconds: int = 60) -> RateLimitResult:
        if not self.enabled:
            return RateLimitResult(True, 999999)
        effective_limit = limit or self.limit_per_minute
        if self.redis is not None:
            return await self._check_redis(key, effective_limit, window_seconds)
        return await self._check_memory(key, effective_limit, window_seconds)

    async def enforce(self, request: Request, user_id: str | None = None, *, limit: int | None = None) -> None:
        who = user_id or request.client.host if request.client else "unknown"
        key = f"{request.url.path}:{who}"
        result = await self.check(key, limit=limit)
        if not result.allowed:
            self.audit.log_rate_limit(
                {"path": request.url.path, "user_id": user_id, "ip": request.client.host if request.client else "unknown"}
            )
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded.")

    async def _check_redis(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        redis_key = f"rl:{key}"
        try:
            current = int(await asyncio.to_thread(self.redis.incr, redis_key))
            if current == 1:
                await asyncio.to_thread(self.redis.expire, redis_key, window_seconds)
            return RateLimitResult(current <= limit, max(0, limit - current))
        except Exception:
            return await self._check_memory(key, limit, window_seconds)

    async def _check_memory(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = time.time()
        async with self._lock:
            bucket = self._memory[key]
            while bucket and (now - bucket[0]) > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return RateLimitResult(False, 0)
            bucket.append(now)
            return RateLimitResult(True, max(0, limit - len(bucket)))


_RATE_LIMITER: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _RATE_LIMITER
    if _RATE_LIMITER is None:
        _RATE_LIMITER = RateLimiter()
    return _RATE_LIMITER

