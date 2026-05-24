import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app
from app.models.schemas import Transaction, UserContext
from app.services.copilot_orchestrator import CopilotOrchestrator
from app.services.guidance_engine import GuidanceEngine


def _risk_event(event_type: str, severity: str = "High", confidence: float = 0.8) -> dict:
    return {
        "risk_event_id": f"evt_{event_type}",
        "event_type": event_type,
        "risk_type": "behavior",
        "severity": severity,
        "confidence": confidence,
        "evidence": {"x": 1},
        "recommendation": f"Handle {event_type}",
        "source_signals": [f"signal.{event_type}"],
        "created_at": "2026-05-24T00:00:00+00:00",
    }


class TestGuidanceEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = GuidanceEngine()

    def test_empty_input_returns_positive_reinforcement(self):
        resp = self.engine.generate_guidance(transactions=[], risk_result={}, behavior_result={}, score_result={})
        self.assertEqual(resp.items[0].guidance_type, "PositiveReinforcement")

    def test_sparse_data_guidance(self):
        resp = self.engine.generate_guidance(
            transactions=[{"date": "2026-05-01", "amount": 100, "category": "Food", "description": "Cafe"}],
            risk_result={},
            behavior_result={"transaction_count": 1},
            score_result={},
        )
        self.assertTrue(any(i.title.startswith("Upload More History") for i in resp.items))

    def test_risk_event_action_generated(self):
        resp = self.engine.generate_guidance(
            transactions=[],
            risk_result={"risk_events": [_risk_event("cashflow_instability")]},
            behavior_result={},
            score_result={},
        )
        self.assertTrue(any(i.guidance_type == "RiskEventAction" for i in resp.items))

    def test_specific_guidance_types(self):
        events = [
            _risk_event("cashflow_instability"),
            _risk_event("spending_velocity_spike"),
            _risk_event("category_drift"),
            _risk_event("recurring_burden", "Medium"),
            _risk_event("low_financial_health_score"),
        ]
        resp = self.engine.generate_guidance(
            transactions=[],
            risk_result={"risk_events": events},
            behavior_result={"weekend_spending_drift": 0.6},
            score_result={"metrics": {"savings_ratio": 0.1}},
        )
        types = {i.guidance_type for i in resp.items}
        self.assertIn("CashflowStability", types)
        self.assertIn("SpendingVelocityControl", types)
        self.assertIn("WeekendSpendingControl", types)
        self.assertIn("SubscriptionOptimization", types)
        self.assertIn("MerchantHabitCorrection", types)
        self.assertIn("SavingsImprovement", types)

    def test_priority_ordering(self):
        resp = self.engine.generate_guidance(
            transactions=[],
            risk_result={"risk_events": [_risk_event("income_expense_imbalance", "Critical", 0.95)]},
            behavior_result={},
            score_result={},
        )
        priorities = [i.priority for i in resp.items]
        self.assertIn("Critical", priorities[0])

    def test_dedupe_merge_combines_signals(self):
        event = _risk_event("spending_velocity_spike")
        event2 = _risk_event("spending_velocity_spike")
        event2["source_signals"] = ["signal.extra"]
        resp = self.engine.generate_guidance(
            transactions=[],
            risk_result={"risk_events": [event, event2]},
            behavior_result={},
            score_result={},
        )
        actions = [i for i in resp.items if i.guidance_type == "RiskEventAction"]
        self.assertEqual(len(actions), 1)
        self.assertTrue("signal.extra" in actions[0].source_signals or "signal.spending_velocity_spike" in actions[0].source_signals)

    def test_schema_completeness(self):
        resp = self.engine.generate_guidance(transactions=[], risk_result={}, behavior_result={}, score_result={})
        item = resp.items[0].model_dump()
        required = [
            "guidance_id",
            "guidance_type",
            "priority",
            "confidence",
            "actionability_score",
            "title",
            "rationale",
            "action_steps",
            "expected_impact",
            "source_signals",
            "related_risk_events",
            "ttl_days",
            "created_at",
        ]
        for field in required:
            self.assertIn(field, item)


class TestGuidanceRouteIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: UserContext(id="u1", email="u1@example.com")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    async def test_guidance_endpoint_contract(self):
        txs = [
            Transaction(date="2026-05-01", amount=2500, category="Shopping", description="Store A"),
            Transaction(date="2026-05-02", amount=1200, category="Food", description="Store B"),
        ]
        with patch("app.services.supabase.SupabaseService.fetch_transactions", new=AsyncMock(return_value=txs)), patch(
            "app.services.supabase.SupabaseService.persist_guidance_items", new=AsyncMock()
        ) as persist_items, patch(
            "app.services.supabase.SupabaseService.persist_guidance_snapshot", new=AsyncMock()
        ) as persist_snapshot:
            response = self.client.get("/guidance", headers={"Authorization": "Bearer t"})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIn("items", body)
            self.assertIn("guidance_items", body)
            self.assertIn("top_priority", body)
            self.assertIn("summary", body)
            self.assertIn("engine_version", body)
            persist_items.assert_awaited()
            persist_snapshot.assert_awaited()

    async def test_analyze_compatibility(self):
        txs = [
            Transaction(date="2026-05-01", amount=2500, category="Shopping", description="Store A"),
            Transaction(date="2026-05-02", amount=1200, category="Food", description="Store B"),
        ]
        with patch("app.services.supabase.SupabaseService.fetch_transactions", new=AsyncMock(return_value=txs)):
            response = self.client.get("/analyze", headers={"Authorization": "Bearer t"})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIn("recommendations", body)
            self.assertIsInstance(body["recommendations"], list)
            self.assertIn("guidance", body["insights"])

    async def test_copilot_context_has_guidance(self):
        orchestrator = CopilotOrchestrator()
        scoped = orchestrator._scoped_context(
            {
                "insights": {
                    "guidance": {
                        "items": [
                            {
                                "guidance_type": "RiskReduction",
                                "priority": "High",
                                "title": "Reduce Risk",
                                "action_steps": ["a", "b"],
                                "expected_impact": "x",
                                "confidence": 0.9,
                                "related_risk_events": ["r1"],
                            }
                        ]
                    }
                }
            }
        )
        self.assertIn("guidance", scoped)
        self.assertTrue(len(scoped["guidance"]) >= 1)
        self.assertIn("action_steps", scoped["guidance"][0])


if __name__ == "__main__":
    unittest.main()
