from __future__ import annotations

from typing import Any

from app.services.event_bus import get_event_bus
from app.services.realtime_manager import get_realtime_manager


class MetricsService:
    def snapshot(self) -> dict[str, Any]:
        bus = get_event_bus()
        manager = get_realtime_manager()
        snap = dict(bus.metrics)
        snap["active_websocket_connections"] = manager.active_connection_count()
        return snap


_METRICS_SERVICE: MetricsService | None = None


def get_metrics_service() -> MetricsService:
    global _METRICS_SERVICE
    if _METRICS_SERVICE is None:
        _METRICS_SERVICE = MetricsService()
    return _METRICS_SERVICE

