from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class NotificationJob:
    job_id: str
    alert_id: str
    user_id: str
    channel: str
    payload: dict[str, Any]
    attempt_count: int = 0
    max_attempts: int = 3
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class NotificationQueue:
    def __init__(self) -> None:
        self._queue: list[NotificationJob] = []
        self._dlq: list[NotificationJob] = []

    def enqueue(self, job: NotificationJob) -> None:
        self._queue.append(job)

    def pop(self) -> NotificationJob | None:
        if not self._queue:
            return None
        return self._queue.pop(0)

    def requeue(self, job: NotificationJob) -> None:
        self._queue.append(job)

    def move_to_dlq(self, job: NotificationJob) -> None:
        self._dlq.append(job)

    @property
    def dlq_size(self) -> int:
        return len(self._dlq)
