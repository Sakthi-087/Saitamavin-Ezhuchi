from __future__ import annotations

import asyncio
import json
import os
from collections import deque
from time import perf_counter
from typing import Any

from app.models.schemas import SystemEvent

try:
    from redis import Redis  # type: ignore[import-not-found]
    from redis.exceptions import RedisError  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    Redis = None  # type: ignore[assignment]
    RedisError = Exception  # type: ignore[assignment]


class InMemoryEventBus:
    def __init__(self, *, max_queue_size: int = 1000) -> None:
        self.stream_name = os.getenv("EVENT_STREAM_NAME", "carebank:events")
        self.consumer_group = os.getenv("EVENT_CONSUMER_GROUP", "carebank-workers")
        self.consumer_name = os.getenv("EVENT_CONSUMER_NAME", "worker-1")
        self.redis_url = os.getenv("REDIS_URL", "").strip()
        self.redis: Redis | None = Redis.from_url(self.redis_url, decode_responses=True) if (self.redis_url and Redis is not None) else None
        self.queue: deque[SystemEvent] = deque(maxlen=max_queue_size)
        self.processing: dict[str, SystemEvent] = {}
        self._redis_stream_ids: dict[str, str] = {}
        self.metrics = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
            "dlq_events": 0,
            "avg_processing_ms": 0.0,
            "active_websocket_connections": 0,
        }
        self._lock = asyncio.Lock()

    async def publish(self, event: SystemEvent) -> str:
        if self.redis is not None:
            try:
                event_id = await asyncio.to_thread(
                    self.redis.xadd,
                    self.stream_name,
                    {"event_json": event.model_dump_json()},
                )
                self.metrics["events_published"] += 1
                return str(event_id)
            except (RuntimeError, TimeoutError, ValueError, ConnectionError, RedisError, OSError):
                pass
        async with self._lock:
            self.queue.append(event)
            self.metrics["events_published"] += 1
        return event.event_id

    async def consume(self, count: int = 10) -> list[SystemEvent]:
        if self.redis is not None:
            try:
                await asyncio.to_thread(self._ensure_group)
                entries = await asyncio.to_thread(
                    self.redis.xreadgroup,
                    self.consumer_group,
                    self.consumer_name,
                    {self.stream_name: ">"},
                    count,
                    1,
                )
                events: list[SystemEvent] = []
                for _, stream_entries in entries or []:
                    for event_id, fields in stream_entries:
                        data = json.loads(fields.get("event_json", "{}"))
                        event = SystemEvent(**data)
                        event.status = "processing"
                        self.processing[str(event_id)] = event
                        self._redis_stream_ids[event.event_id] = str(event_id)
                        events.append(event)
                return events
            except (RuntimeError, TimeoutError, ValueError, ConnectionError, RedisError, OSError, json.JSONDecodeError):
                pass
        events: list[SystemEvent] = []
        async with self._lock:
            while self.queue and len(events) < count:
                event = self.queue.popleft()
                event.status = "processing"
                self.processing[event.event_id] = event
                events.append(event)
        return events

    async def ack(self, event: SystemEvent, elapsed_ms: float = 0.0) -> None:
        if self.redis is not None:
            try:
                stream_id = self._redis_stream_ids.get(event.event_id, event.event_id)
                await asyncio.to_thread(self.redis.xack, self.stream_name, self.consumer_group, stream_id)
            except (RuntimeError, TimeoutError, ValueError, ConnectionError, RedisError, OSError):
                pass
        async with self._lock:
            self.processing.pop(event.event_id, None)
            event.status = "completed"
            self.metrics["events_processed"] += 1
            c = self.metrics["events_processed"]
            avg = self.metrics["avg_processing_ms"]
            self.metrics["avg_processing_ms"] = ((avg * (c - 1)) + elapsed_ms) / c if c > 0 else 0.0

    async def mark_failed(self, event: SystemEvent, *, dlq: bool = False) -> None:
        async with self._lock:
            self.processing.pop(event.event_id, None)
            event.status = "dlq" if dlq else "failed"
            self.metrics["events_failed"] += 1
            if dlq:
                self.metrics["dlq_events"] += 1

    async def pending_summary(self) -> dict[str, int]:
        if self.redis is not None:
            try:
                info = await asyncio.to_thread(self.redis.xpending, self.stream_name, self.consumer_group)
                pending = int(info.get("pending", 0) if isinstance(info, dict) else 0)
                return {"queued": pending, "processing": len(self.processing)}
            except (RuntimeError, TimeoutError, ValueError, ConnectionError, RedisError, OSError):
                pass
        async with self._lock:
            return {"queued": len(self.queue), "processing": len(self.processing)}

    def status(self) -> dict[str, Any]:
        return {
            "stream_name": self.stream_name,
            "consumer_group": self.consumer_group,
            "consumer_name": self.consumer_name,
            "backend": "redis" if self.redis is not None else "memory",
            "metrics": dict(self.metrics),
        }

    def _ensure_group(self) -> None:
        if self.redis is None:
            return
        try:
            self.redis.xgroup_create(self.stream_name, self.consumer_group, id="$", mkstream=True)
        except (RuntimeError, TimeoutError, ValueError, ConnectionError, RedisError, OSError):
            # group may already exist
            return

    async def process(self, stream: str) -> None:
        del stream
        events = await self.consume()
        for event in events:
            start = perf_counter()
            await self.ack(event, elapsed_ms=(perf_counter() - start) * 1000.0)


_EVENT_BUS: InMemoryEventBus | None = None


def get_event_bus() -> InMemoryEventBus:
    global _EVENT_BUS
    if _EVENT_BUS is None:
        _EVENT_BUS = InMemoryEventBus()
    return _EVENT_BUS
