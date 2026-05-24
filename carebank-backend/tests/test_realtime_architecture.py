import io
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.auth import get_current_user
from app.main import app
from app.models.schemas import SystemEvent, Transaction, UserContext
from app.services.event_bus import InMemoryEventBus
from app.services.idempotency_store import IdempotencyStore
from app.services.realtime_manager import RealtimeManager
from app.services.realtime_pipeline import RealtimePipeline


def _event(event_type: str = "transaction_ingested") -> SystemEvent:
    return SystemEvent(
        event_id="evt_test_1",
        event_type=event_type,
        user_id="u1",
        correlation_id="c1",
        idempotency_key=f"{event_type}:u1:c1",
        payload={"inserted_count": 1, "source": "manual"},
        status="pending",
        attempt_count=0,
        max_attempts=2,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=None,
    )


class TestRealtimeCore(unittest.IsolatedAsyncioTestCase):
    async def test_system_event_schema_defaults(self):
        event = _event()
        self.assertEqual(event.status, "pending")
        self.assertEqual(event.attempt_count, 0)
        self.assertIsInstance(event.payload, dict)

    async def test_event_publish_consume_ack_in_memory(self):
        bus = InMemoryEventBus()
        event = _event()
        await bus.publish(event)
        consumed = await bus.consume(count=1)
        self.assertEqual(len(consumed), 1)
        self.assertEqual(consumed[0].status, "processing")
        await bus.ack(consumed[0], elapsed_ms=1.2)
        self.assertEqual(bus.metrics["events_published"], 1)
        self.assertEqual(bus.metrics["events_processed"], 1)

    async def test_idempotency_duplicate_skip(self):
        bus = InMemoryEventBus()
        pipe = RealtimePipeline(bus=bus)
        event = _event()
        pipe.idempotency.mark_processed(event.idempotency_key)
        result = await pipe.process_event(event)
        self.assertEqual(result["status"], "duplicate_skipped")

    async def test_retry_and_dlq(self):
        bus = InMemoryEventBus()
        pipe = RealtimePipeline(bus=bus)
        event = _event()
        with patch.object(pipe.workers, "dispatch", new=AsyncMock(side_effect=RuntimeError("boom"))):
            first = await pipe.process_event(event)
            self.assertEqual(first["status"], "retry_scheduled")
            # second attempt hits DLQ due to max_attempts=2
            second = await pipe.process_event(event)
            self.assertEqual(second["status"], "dlq")
            self.assertEqual(bus.metrics["dlq_events"], 1)

    async def test_replay_dlq_event(self):
        bus = InMemoryEventBus()
        pipe = RealtimePipeline(bus=bus)
        event = _event()
        event.status = "dlq"
        pipe._dlq[event.event_id] = event
        replayed = await pipe.replay_dlq_event(event.event_id)
        self.assertIsNotNone(replayed)
        consumed = await bus.consume(count=1)
        self.assertTrue(consumed[0].event_id.endswith("_replay"))

    async def test_recover_stuck_events(self):
        bus = InMemoryEventBus()
        pipe = RealtimePipeline(bus=bus)
        event = _event()
        event.status = "processing"
        event.updated_at = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()
        bus.processing[event.event_id] = event
        recovered = await pipe.recover_stuck_events(max_age_minutes=10)
        self.assertEqual(recovered, 1)

    async def test_realtime_manager_send_path(self):
        manager = RealtimeManager()

        class DummyWS:
            def __init__(self):
                self.sent = []

            async def send_json(self, payload):
                self.sent.append(payload)

        ws = DummyWS()
        manager._connections["u1"].add(ws)  # direct inject for unit test
        await manager.send_to_user("u1", {"hello": "world", "authorization": "Bearer secret"})
        self.assertEqual(ws.sent[0]["authorization"], "***REDACTED***")


class TestRealtimeRoutes(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: UserContext(id="u1", email="u1@example.com")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    async def test_websocket_auth_rejection_missing_token(self):
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/ws/u1"):
                pass

    async def test_websocket_user_mismatch_rejected(self):
        with patch("app.services.supabase.SupabaseService.verify_access_token", new=AsyncMock(return_value=UserContext(id="u2", email="u2@example.com"))):
            with self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect("/ws/u1?token=fake"):
                    pass

    async def test_manual_transaction_publishes_event_without_token_leak(self):
        txs = [
            {"amount": 10, "category": "Food", "description": "x", "created_at": "2026-05-01T00:00:00+00:00"},
        ]
        with patch("app.services.supabase.SupabaseService.build_transaction_row_async", new=AsyncMock(return_value=txs[0])), patch(
            "app.services.supabase.SupabaseService.fetch_transaction_history", new=AsyncMock(return_value=[])
        ), patch("app.services.supabase.SupabaseService.insert_transactions", new=AsyncMock(return_value=1)), patch(
            "app.routes.transactions.get_event_bus"
        ) as bus_get:
            bus = InMemoryEventBus()
            bus.publish = AsyncMock()  # type: ignore[method-assign]
            bus_get.return_value = bus
            response = self.client.post(
                "/transactions/manual",
                headers={"Authorization": "Bearer test-token"},
                json={"date": "2026-05-01", "description": "Coffee", "amount": 100, "category": "Food"},
            )
            self.assertEqual(response.status_code, 200)
            event = bus.publish.await_args.args[0]
            self.assertEqual(event.event_type, "transaction_ingested")
            self.assertNotIn("access_token", event.payload)
            self.assertNotIn("authorization", event.payload)

    async def test_csv_upload_publishes_event(self):
        csv_content = "date,description,amount,category\n2026-05-01,Coffee,100,Food\n"
        with patch("app.services.supabase.SupabaseService.parse_csv_upload", new=AsyncMock(return_value=([{"amount": 100, "category": "Food", "description": "Coffee", "created_at": "2026-05-01T00:00:00+00:00"}], []))), patch(
            "app.services.supabase.SupabaseService.fetch_transaction_history", new=AsyncMock(return_value=[])
        ), patch("app.services.supabase.SupabaseService.insert_transactions", new=AsyncMock(return_value=1)), patch(
            "app.routes.transactions.get_event_bus"
        ) as bus_get:
            bus = InMemoryEventBus()
            bus.publish = AsyncMock()  # type: ignore[method-assign]
            bus_get.return_value = bus
            files = {"file": ("tx.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
            response = self.client.post("/transactions/upload-csv", headers={"Authorization": "Bearer t"}, files=files)
            self.assertEqual(response.status_code, 200)
            event = bus.publish.await_args.args[0]
            self.assertEqual(event.event_type, "transaction_ingested")
            self.assertEqual(event.payload.get("source"), "csv")

    async def test_health_and_metrics_expose_realtime(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("realtime_metrics", response.json())
        with patch("app.routes.health.get_settings") as settings_mock:
            settings = settings_mock.return_value
            settings.internal_metrics_token = "token"
            metrics = self.client.get("/metrics", headers={"X-Internal-Metrics-Token": "token"})
        self.assertEqual(metrics.status_code, 200)
        self.assertIn("realtime", metrics.json())


if __name__ == "__main__":
    unittest.main()
