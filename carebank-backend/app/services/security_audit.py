from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.event_store import EventStore
from app.services.redaction import redact_dict

logger = logging.getLogger(__name__)


class SecurityAuditLogger:
    def __init__(self) -> None:
        self.store = EventStore(Path(__file__).resolve().parents[2])

    def log_prompt_injection(self, message: str, metadata: dict[str, Any] | None = None) -> None:
        self._write("prompt_injection", {"message": message, "metadata": metadata or {}})

    def log_unsupported_advice(self, advice_type: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        self._write("unsupported_advice", {"advice_type": advice_type, "message": message, "metadata": metadata or {}})

    def log_copilot_fallback(self, reason: str, metadata: dict[str, Any] | None = None) -> None:
        self._write("copilot_fallback", {"reason": reason, "metadata": metadata or {}})

    def log_llm_validation_failure(self, reason: str, raw_response: str | None = None) -> None:
        self._write("llm_validation_failure", {"reason": reason, "raw_response": raw_response or ""})

    def log_auth_failure(self, reason: str, metadata: dict[str, Any] | None = None) -> None:
        self._write("auth_failure", {"reason": reason, "metadata": metadata or {}})

    def log_ws_auth_failure(self, reason: str, metadata: dict[str, Any] | None = None) -> None:
        self._write("ws_auth_failure", {"reason": reason, "metadata": metadata or {}})

    def log_rate_limit(self, metadata: dict[str, Any]) -> None:
        self._write("rate_limit_hit", {"metadata": metadata})

    def log_permission_denied(self, reason: str, metadata: dict[str, Any] | None = None) -> None:
        self._write("permission_denied", {"reason": reason, "metadata": metadata or {}})

    def log_security_startup_failure(self, reason: str, metadata: dict[str, Any] | None = None) -> None:
        self._write("security_startup_failure", {"reason": reason, "metadata": metadata or {}})

    def _write(self, event_type: str, payload: dict[str, Any]) -> None:
        record = {
            "event_type": event_type,
            "created_at": datetime.now(UTC).isoformat(),
            "payload": redact_dict(payload),
        }
        try:
            self.store.persist_audit_log(event_type, record)
        except OSError:
            logger.warning("Security audit write failed for event_type=%s", event_type)
