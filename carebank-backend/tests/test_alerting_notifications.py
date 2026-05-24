import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.models.schemas import NotificationPreferences, SystemEvent
from app.services.alert_dedupe_store import AlertDedupeStore
from app.services.notification_agent import NotificationAgent
from app.services.notification_queue import NotificationQueue
from app.services.realtime_manager import RealtimeManager
from app.services.realtime_workers import RealtimeWorkers


def make_event(event_type: str, payload: dict | None = None) -> SystemEvent:
    return SystemEvent(
        event_id=f"evt_{event_type}",
        event_type=event_type,
        user_id="u1",
        correlation_id="corr_1",
        idempotency_key=f"{event_type}:u1:corr_1",
        payload=payload or {},
        status="pending",
        attempt_count=0,
        max_attempts=3,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=None,
    )


class TestAlertingNotifications(unittest.IsolatedAsyncioTestCase):
    async def test_risk_high_critical_creates_live_alert(self):
        worker = RealtimeWorkers()
        evt = make_event("risk_detected", {"risk_level": "High", "recommendation_text": "Act now"})
        children = await worker.dispatch(evt)
        self.assertTrue(any(c.event_type == "alert_created" for c in children))

    async def test_behavior_anomaly_creates_live_alert(self):
        worker = RealtimeWorkers()
        evt = make_event("analysis_completed", {"drift_severity": "High", "anomaly_severity": "Critical"})
        children = await worker.dispatch(evt)
        self.assertTrue(any(c.payload.get("alert_type") == "behavior_alert" for c in children))

    async def test_high_priority_guidance_creates_live_alert(self):
        worker = RealtimeWorkers()
        evt = make_event("guidance_generated", {"top_priority": "High", "guidance_type": "CashflowStability"})
        children = await worker.dispatch(evt)
        self.assertTrue(any(c.payload.get("alert_type") == "guidance_alert" for c in children))

    async def test_weak_score_creates_live_alert(self):
        worker = RealtimeWorkers()
        evt = make_event("analysis_completed", {"score_status": "Weak", "score": 24})
        children = await worker.dispatch(evt)
        self.assertTrue(any(c.payload.get("alert_type") == "score_alert" for c in children))

    async def test_pipeline_failure_creates_alert(self):
        worker = RealtimeWorkers()
        evt = make_event("analysis_failed", {"error": "boom"})
        with patch.object(worker, "_handle_alert_created", new=AsyncMock()) as mocked:
            await worker.dispatch(evt)
            mocked.assert_awaited()

    async def test_low_noise_suppressed(self):
        worker = RealtimeWorkers()
        evt = make_event("alert_created", {"alert_type": "risk_alert", "severity": "Low", "source": "risk_intelligence"})
        with patch.object(worker.store, "persist_live_alert") as persist_mock:
            await worker.dispatch(evt)
            persist_mock.assert_not_called()

    def test_cooldown_cross_user_isolation(self):
        store = AlertDedupeStore()
        sig = store.make_signature("risk_intelligence", {"risk_level": "High"})
        store.mark_sent("u1", "risk_alert", sig, 60)
        self.assertTrue(store.should_suppress("u1", "risk_alert", sig))
        self.assertFalse(store.should_suppress("u2", "risk_alert", sig))

    async def test_stable_alert_id_and_duplicate_suppression(self):
        worker = RealtimeWorkers()
        evt = make_event("alert_created", {"alert_type": "risk_alert", "severity": "High", "source": "risk_intelligence", "evidence": {"x": 1}})
        with patch.object(worker.store, "persist_live_alert") as persist_mock, patch.object(worker.manager, "send_to_user", new=AsyncMock()):
            await worker.dispatch(evt)
            await worker.dispatch(evt)
            first = persist_mock.call_args_list[0].args[0]
            second = persist_mock.call_args_list[-1].args[0]
            self.assertEqual(first.alert_id, second.alert_id)
            self.assertEqual(second.delivery_status, "suppressed")

    async def test_preference_disables_realtime_delivery(self):
        worker = RealtimeWorkers()
        evt = make_event("alert_created", {"alert_type": "risk_alert", "severity": "High", "source": "risk_intelligence", "evidence": {"x": 2}})
        with patch.object(worker.preferences, "get", return_value=NotificationPreferences(overspending_alerts=False, weekly_wellness_summary=False, ai_assistant_tips=False)), patch.object(worker.manager, "send_to_user", new=AsyncMock()) as send_mock:
            await worker.dispatch(evt)
            send_mock.assert_not_awaited()

    async def test_preference_enables_email_queue(self):
        worker = RealtimeWorkers()
        evt = make_event("alert_created", {"alert_type": "risk_alert", "severity": "High", "source": "risk_intelligence", "evidence": {"x": 3}})
        with patch.object(worker.preferences, "get", return_value=NotificationPreferences(overspending_alerts=False, weekly_wellness_summary=True, ai_assistant_tips=False)), patch.object(worker.notification_agent, "queue_notification") as q_mock:
            await worker.dispatch(evt)
            q_mock.assert_called_once()

    def test_notification_retry_and_dlq(self):
        agent = NotificationAgent()
        with patch.object(agent.service, "send", side_effect=RuntimeError("fail")):
            job_id = agent.queue_notification(alert_id="a1", user_id="u1", channel="email", payload={"x": 1})
            r1 = agent.process_next()
            r2 = agent.process_next()
            r3 = agent.process_next()
            self.assertEqual(job_id, r1["job_id"])
            self.assertEqual(r1["status"], "retry")
            self.assertEqual(r3["status"], "dlq")
            self.assertGreaterEqual(agent.queue.dlq_size, 1)

    def test_notification_dispatched_after_success_or_skipped(self):
        agent = NotificationAgent()
        job_id = agent.queue_notification(alert_id="a1", user_id="u1", channel="email", payload={"x": 1})
        result = agent.process_next()
        self.assertEqual(result["job_id"], job_id)
        self.assertIn(result["status"], {"delivered", "skipped_noop"})

    async def test_live_alert_persistence_includes_delivery_status(self):
        worker = RealtimeWorkers()
        evt = make_event("alert_created", {"alert_type": "risk_alert", "severity": "High", "source": "risk_intelligence", "evidence": {"x": 4}})
        with patch.object(worker.store, "persist_live_alert") as persist_mock, patch.object(worker.manager, "send_to_user", new=AsyncMock()):
            await worker.dispatch(evt)
            statuses = [call.args[0].delivery_status for call in persist_mock.call_args_list]
            self.assertTrue(any(status in {"created", "delivered", "queued"} for status in statuses))

    async def test_payload_redacted(self):
        worker = RealtimeWorkers()
        evt = make_event(
            "alert_created",
            {
                "alert_type": "risk_alert",
                "severity": "High",
                "source": "risk_intelligence",
                "evidence": {"authorization": "Bearer secret"},
            },
        )
        with patch.object(worker.store, "persist_live_alert") as persist_mock, patch.object(worker.manager, "send_to_user", new=AsyncMock()):
            await worker.dispatch(evt)
            payload = persist_mock.call_args_list[0].args[0].payload
            self.assertNotIn("secret", str(payload).lower())

    async def test_websocket_send_failure_isolated(self):
        manager = RealtimeManager()

        class GoodWS:
            def __init__(self):
                self.sent = []

            async def send_json(self, payload):
                self.sent.append(payload)

        class BadWS:
            async def send_json(self, payload):
                raise RuntimeError("socket fail")

        good = GoodWS()
        bad = BadWS()
        manager._connections["u1"].add(good)
        manager._connections["u1"].add(bad)

        await manager.send_to_user("u1", {"title": "t"})
        self.assertEqual(len(good.sent), 1)


if __name__ == "__main__":
    unittest.main()
