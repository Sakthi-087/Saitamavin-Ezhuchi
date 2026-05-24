from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

from app.services.redaction import redact_dict


class RealtimeManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[user_id].add(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(user_id)
            if not conns:
                return
            conns.discard(websocket)
            if not conns:
                self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, payload: dict[str, Any]) -> None:
        safe_payload = redact_dict(payload)
        async with self._lock:
            conns = list(self._connections.get(user_id, set()))
        for ws in conns:
            try:
                await ws.send_json(safe_payload)
            except (RuntimeError, ValueError, ConnectionError):
                await self.disconnect(user_id, ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        safe_payload = redact_dict(payload)
        async with self._lock:
            conns = [ws for user_conns in self._connections.values() for ws in user_conns]
        for ws in conns:
            try:
                await ws.send_json(safe_payload)
            except (RuntimeError, ValueError, ConnectionError):
                # Best effort for broadcast; drop failed socket silently.
                continue

    def active_connection_count(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


_REALTIME_MANAGER: RealtimeManager | None = None


def get_realtime_manager() -> RealtimeManager:
    global _REALTIME_MANAGER
    if _REALTIME_MANAGER is None:
        _REALTIME_MANAGER = RealtimeManager()
    return _REALTIME_MANAGER
