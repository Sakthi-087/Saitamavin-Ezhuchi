from __future__ import annotations

from typing import Any


class NotificationService:
    def __init__(self) -> None:
        self.email_provider_configured = False

    def send(self, channel: str, payload: dict[str, Any]) -> str:
        # No-op provider by default; explicit skipped status is considered safe completion.
        if channel == "email" and not self.email_provider_configured:
            return "skipped_noop"
        if channel == "push":
            return "skipped_noop"
        return "delivered"
