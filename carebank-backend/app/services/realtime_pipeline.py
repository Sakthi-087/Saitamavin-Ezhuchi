from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

from app.models.schemas import SystemEvent
from app.services.event_bus import InMemoryEventBus, get_event_bus
from app.services.event_store import EventStore
from app.services.idempotency_store import IdempotencyStore
from app.services.realtime_workers import RealtimeWorkers


class RealtimePipeline:
    def __init__(self, bus: InMemoryEventBus | None = None) -> None:
        self.bus = bus or get_event_bus()
        self.idempotency = IdempotencyStore()
        self.store = EventStore(Path(__file__).resolve().parents[2])
        self.workers = RealtimeWorkers()
        self._dlq: dict[str, SystemEvent] = {}

    async def process_event(self, event: SystemEvent) -> dict[str, Any]:
        key = event.idempotency_key
        if self.idempotency.is_processed(key):
            self.store.persist_processing_event(event, "idempotency", "duplicate_skipped")
            await self.bus.ack(event, elapsed_ms=0.0)
            return {"status": "duplicate_skipped"}

        start = perf_counter()
        try:
            self.store.persist_processing_event(event, "dispatch", "processing")
            children = await self.workers.dispatch(event)
            for child in children:
                self.store.persist_system_event(child)
                await self.bus.publish(child)
            self.idempotency.mark_processed(key)
            event.status = "completed"
            event.updated_at = datetime.now(UTC).isoformat()
            self.store.persist_processing_event(event, "dispatch", "completed")
            await self.bus.ack(event, elapsed_ms=(perf_counter() - start) * 1000.0)
            return {"status": "completed", "children_published": len(children)}
        except (ValueError, KeyError, RuntimeError) as exc:
            return await self.handle_failure(event, str(exc))

    async def handle_failure(self, event: SystemEvent, error: str) -> dict[str, Any]:
        event.attempt_count += 1
        event.updated_at = datetime.now(UTC).isoformat()
        self.store.persist_processing_event(event, "dispatch", "failed", error=error)
        if event.attempt_count >= event.max_attempts:
            event.status = "dlq"
            self._dlq[event.event_id] = event
            self.store.persist_dead_letter_event(event, error)
            await self.bus.mark_failed(event, dlq=True)
            return {"status": "dlq", "attempt_count": event.attempt_count}

        event.status = "pending"
        await asyncio.sleep(min(0.01 * (2 ** max(event.attempt_count - 1, 0)), 0.05))
        await self.bus.publish(event)
        await self.bus.mark_failed(event, dlq=False)
        return {"status": "retry_scheduled", "attempt_count": event.attempt_count}

    async def replay_dlq_event(self, event_id: str) -> str | None:
        event = self._dlq.get(event_id)
        if event is None:
            return None
        replay = event.model_copy(deep=True)
        replay.event_id = f"{event.event_id}_replay"
        replay.status = "pending"
        replay.attempt_count = 0
        replay.created_at = datetime.now(UTC).isoformat()
        replay.updated_at = None
        self.store.persist_event_replay_history(event.event_id, replay.event_id, replay.user_id, replay.correlation_id)
        self.store.persist_system_event(replay)
        await self.bus.publish(replay)
        return replay.event_id

    async def recover_stuck_events(self, max_age_minutes: int = 10) -> int:
        recovered = 0
        cutoff = datetime.now(UTC) - timedelta(minutes=max_age_minutes)
        summary = await self.bus.pending_summary()
        if summary.get("processing", 0) == 0:
            return 0
        for event in list(self.bus.processing.values()):
            updated_at = event.updated_at or event.created_at
            try:
                event_time = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except ValueError:
                event_time = datetime.now(UTC)
            if event_time < cutoff:
                event.status = "pending"
                event.updated_at = datetime.now(UTC).isoformat()
                self.bus.processing.pop(event.event_id, None)
                await self.bus.publish(event)
                recovered += 1
        return recovered


_PIPELINE: RealtimePipeline | None = None


def get_realtime_pipeline() -> RealtimePipeline:
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = RealtimePipeline()
    return _PIPELINE

