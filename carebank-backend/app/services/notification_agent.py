from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha1
from pathlib import Path

from app.services.event_store import EventStore
from app.services.notification_queue import NotificationJob, NotificationQueue
from app.services.notification_service import NotificationService
from app.services.redaction import redact_dict


class NotificationAgent:
    def __init__(self) -> None:
        self.queue = NotificationQueue()
        self.service = NotificationService()
        self.store = EventStore(Path(__file__).resolve().parents[2])

    def queue_notification(self, *, alert_id: str, user_id: str, channel: str, payload: dict[str, object]) -> str:
        base = f"{alert_id}:{user_id}:{channel}:{datetime.now(UTC).isoformat()}"
        job_id = f"notif_{sha1(base.encode('utf-8')).hexdigest()[:12]}"
        job = NotificationJob(
            job_id=job_id,
            alert_id=alert_id,
            user_id=user_id,
            channel=channel,
            payload=redact_dict(payload),
            created_at=datetime.now(UTC).isoformat(),
        )
        self.queue.enqueue(job)
        self.store.persist_processing_event(
            event=self._as_event(job),
            stage="notification",
            status="queued",
        )
        return job_id

    def process_next(self) -> dict[str, str] | None:
        job = self.queue.pop()
        if job is None:
            return None

        job.attempt_count += 1
        try:
            status = self.service.send(job.channel, job.payload)
            if status in {"delivered", "skipped_noop"}:
                self.store.persist_audit_log(
                    "notification_dispatched",
                    {
                        "job_id": job.job_id,
                        "alert_id": job.alert_id,
                        "user_id": job.user_id,
                        "channel": job.channel,
                        "status": status,
                    },
                )
                return {"status": status, "job_id": job.job_id}
        except (RuntimeError, TimeoutError, ValueError, ConnectionError):
            pass

        if job.attempt_count >= job.max_attempts:
            self.queue.move_to_dlq(job)
            self.store.persist_audit_log(
                "notification_failed",
                {
                    "job_id": job.job_id,
                    "alert_id": job.alert_id,
                    "user_id": job.user_id,
                    "channel": job.channel,
                    "attempt_count": job.attempt_count,
                    "status": "dlq",
                },
            )
            return {"status": "dlq", "job_id": job.job_id}

        self.queue.requeue(job)
        self.store.persist_audit_log(
            "notification_failed",
            {
                "job_id": job.job_id,
                "alert_id": job.alert_id,
                "user_id": job.user_id,
                "channel": job.channel,
                "attempt_count": job.attempt_count,
                "status": "retry",
            },
        )
        return {"status": "retry", "job_id": job.job_id}

    @staticmethod
    def _as_event(job: NotificationJob):
        from app.models.schemas import SystemEvent

        return SystemEvent(
            event_id=job.job_id,
            event_type="notification_dispatch",
            user_id=job.user_id,
            correlation_id=job.alert_id,
            idempotency_key=f"notification:{job.job_id}",
            payload=job.payload,
            status="pending",
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            created_at=job.created_at,
            updated_at=None,
        )
