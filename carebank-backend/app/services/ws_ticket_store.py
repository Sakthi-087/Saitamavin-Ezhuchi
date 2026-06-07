from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock


@dataclass(frozen=True)
class WsTicketRecord:
    ticket: str
    user_id: str
    expires_at: str


class WsTicketStore:
    def __init__(self, ttl_seconds: int = 60) -> None:
        self.ttl_seconds = max(1, min(int(ttl_seconds), 60))
        self._tickets: dict[str, tuple[str, datetime]] = {}
        self._lock = Lock()

    def issue(self, user_id: str) -> WsTicketRecord:
        ticket = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=self.ttl_seconds)
        with self._lock:
            self._prune_locked()
            self._tickets[ticket] = (user_id, expires_at)
        return WsTicketRecord(ticket=ticket, user_id=user_id, expires_at=expires_at.isoformat())

    def consume(self, ticket: str, user_id: str) -> WsTicketRecord | None:
        now = datetime.now(UTC)
        with self._lock:
            self._prune_locked(now)
            record = self._tickets.get(ticket)
            if record is None:
                return None
            record_user_id, expires_at = record
            if record_user_id != user_id or expires_at <= now:
                return None
            del self._tickets[ticket]
            return WsTicketRecord(ticket=ticket, user_id=record_user_id, expires_at=expires_at.isoformat())

    def _prune_locked(self, now: datetime | None = None) -> None:
        current = now or datetime.now(UTC)
        expired = [ticket for ticket, (_, expires_at) in self._tickets.items() if expires_at <= current]
        for ticket in expired:
            self._tickets.pop(ticket, None)


_WS_TICKET_STORE: WsTicketStore | None = None


def get_ws_ticket_store() -> WsTicketStore:
    global _WS_TICKET_STORE
    if _WS_TICKET_STORE is None:
        _WS_TICKET_STORE = WsTicketStore()
    return _WS_TICKET_STORE
