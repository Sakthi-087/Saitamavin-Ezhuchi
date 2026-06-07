from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.models.schemas import LiveAlertEvent, SystemEvent
from app.services.redaction import redact_dict

logger = logging.getLogger(__name__)


class EventStore:
    def __init__(self, root: Path) -> None:
        self.settings = get_settings()
        self.base = root / "data" / "snapshots"
        self.base.mkdir(parents=True, exist_ok=True)

    def append(self, stream: str, payload: dict[str, Any]) -> None:
        self._write(stream, {"payload": redact_dict(payload)})

    def latest(self, stream: str) -> dict[str, Any] | None:
        path = self.base / f"{stream}.jsonl"
        if not path.exists():
            return None
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        if not lines:
            return None
        return json.loads(lines[-1])

    def persist_system_event(self, event: SystemEvent) -> None:
        record = redact_dict(event.model_dump())
        self._persist_or_fallback("system_events", record, critical=False)

    def persist_processing_event(self, event: SystemEvent, stage: str, status: str, error: str | None = None) -> None:
        self._persist_or_fallback(
            "processing_events",
            redact_dict(
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "user_id": event.user_id,
                    "correlation_id": event.correlation_id,
                    "stage": stage,
                    "status": status,
                    "attempt_count": event.attempt_count,
                    "error": error or "",
                }
            ),
            critical=False,
        )

    def persist_live_alert(self, alert: LiveAlertEvent) -> None:
        payload = alert.model_dump()
        payload.setdefault("expires_at", None)
        payload.setdefault("archived_at", None)
        self._persist_or_fallback("live_alert_events", redact_dict(payload), critical=False)

    def persist_dead_letter_event(self, event: SystemEvent, reason: str) -> None:
        self._persist_or_fallback(
            "dead_letter_events",
            redact_dict(
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "user_id": event.user_id,
                    "correlation_id": event.correlation_id,
                    "idempotency_key": event.idempotency_key,
                    "payload": event.payload,
                    "status": "dlq",
                    "reason": reason,
                    "replayed_at": None,
                    "expires_at": None,
                }
            ),
            critical=True,
        )

    def persist_event_replay_history(
        self,
        original_event_id: str,
        replayed_event_id: str,
        user_id: str,
        correlation_id: str,
    ) -> None:
        self._persist_or_fallback(
            "event_replay_history",
            redact_dict(
                {
                    "original_event_id": original_event_id,
                    "replayed_event_id": replayed_event_id,
                    "user_id": user_id,
                    "correlation_id": correlation_id,
                    "payload": {},
                }
            ),
            critical=False,
        )

    def persist_audit_log(self, event_type: str, payload: dict[str, Any]) -> None:
        self._persist_or_fallback(
            "audit_logs",
            {
                "user_id": payload.get("user_id"),
                "audit_type": event_type,
                "severity": "warning" if "failure" in event_type or "failed" in event_type else "info",
                "metadata": redact_dict(payload),
                "expires_at": None,
                "archived_at": None,
            },
            critical=True,
        )

    def _persist_or_fallback(self, table: str, payload: dict[str, Any], *, critical: bool) -> None:
        if self._persist_service_role(table, payload):
            return
        if not self.settings.enable_audit_persistence:
            logger.warning("Persistence degraded mode for table=%s (local snapshot only).", table)
            self._write(table, payload)
            return
        if self.settings.enable_local_event_fallback or not self.settings.supabase_service_role_configured:
            logger.warning("Persistence degraded mode for table=%s (local fallback).", table)
            self._write(table, payload)
            return
        if critical:
            logger.error("Critical persistence failed for table=%s with local fallback disabled.", table)
        else:
            logger.warning("Best-effort persistence failed for table=%s with local fallback disabled.", table)

    def _persist_service_role(self, table: str, payload: dict[str, Any]) -> bool:
        if not self.settings.enable_audit_persistence or not self.settings.supabase_service_role_configured:
            return False
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    f"{self.settings.supabase_url}/rest/v1/{table}",
                    headers={
                        "apikey": self.settings.supabase_service_role_key,
                        "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal",
                    },
                    json=[payload],
                )
        except httpx.RequestError:
            return False
        return bool(response.is_success)

    def _write(self, stream: str, payload: dict[str, Any]) -> None:
        path = self.base / f"{stream}.jsonl"
        record = {"ts": datetime.now(UTC).isoformat(), "version": "v4", **payload}
        with path.open("a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(record) + "\n")
