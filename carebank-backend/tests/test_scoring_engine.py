import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app
from app.models.schemas import Transaction, UserContext
from app.services.copilot_orchestrator import CopilotOrchestrator
from app.services.scoring import FinancialScoringEngine
from app.services.scoring_policy import ScoringPolicy


class TestScoringPolicy(unittest.TestCase):
    def test_weights_sum_to_one(self):
        policy = ScoringPolicy()
        self.assertAlmostEqual(sum(policy.component_weights.values()), 1.0, places=9)
        policy.validate_weights()


class TestScoringEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = FinancialScoringEngine()
        self.transactions = [
            Transaction(date="2026-05-01", description="Salary", amount=-50000, category="Income"),
            Transaction(date="2026-05-02", description="Rent", amount=15000, category="Bills"),
            Transaction(date="2026-05-03", description="Shopping", amount=6000, category="Shopping"),
            Transaction(date="2026-05-04", description="Food", amount=2500, category="Food"),
            Transaction(date="2026-05-05", description="Travel", amount=1800, category="Travel"),
        ]

    def test_status_mapping_required_bands(self):
        self.assertEqual(self.engine.get_status(85), "Excellent")
        self.assertEqual(self.engine.get_status(70), "Good")
        self.assertEqual(self.engine.get_status(50), "Moderate")
        self.assertEqual(self.engine.get_status(30), "Weak")
        self.assertEqual(self.engine.get_status(10), "Critical")

    def test_score_and_components_bounded(self):
        result = self.engine.calculate(self.transactions)
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 100)
        self.assertGreaterEqual(result.breakdown.savings_score, 0)
        self.assertLessEqual(result.breakdown.savings_score, 100)
        self.assertGreaterEqual(result.breakdown.stability_score, 0)
        self.assertLessEqual(result.breakdown.stability_score, 100)
        self.assertGreaterEqual(result.breakdown.discipline_score, 0)
        self.assertLessEqual(result.breakdown.discipline_score, 100)
        self.assertGreaterEqual(result.breakdown.risk_score, 0)
        self.assertLessEqual(result.breakdown.risk_score, 100)

    def test_contribution_trace_exists(self):
        result = self.engine.calculate(self.transactions)
        self.assertTrue(len(result.explainability.contributions) >= 4)

    def test_penalty_trace_exists(self):
        result = self.engine.calculate(
            self.transactions,
            behavior_result={"drift_score": 80, "metrics": {"anomaly_count": 4}},
            risk_result={"overall_risk_score": 80, "risk_events": [{"event_type": "cashflow_instability"}]},
        )
        self.assertTrue(len(result.explainability.penalties) >= 1)

    def test_high_risk_drift_anomaly_penalties(self):
        result = self.engine.calculate(
            self.transactions,
            behavior_result={"drift_score": 90, "metrics": {"anomaly_count": 5}},
            risk_result={"overall_risk_score": 90, "risk_events": [{"event_type": "cashflow_instability"}]},
        )
        penalty_types = {p.penalty_type for p in result.explainability.penalties}
        self.assertIn("high_risk_intelligence", penalty_types)
        self.assertIn("high_behavior_drift", penalty_types)
        self.assertIn("multiple_anomalies", penalty_types)
        self.assertIn("cashflow_instability", penalty_types)

    def test_low_savings_penalty(self):
        txs = [
            Transaction(date="2026-05-01", description="Salary", amount=-10000, category="Income"),
            Transaction(date="2026-05-02", description="Rent", amount=9000, category="Bills"),
            Transaction(date="2026-05-03", description="Food", amount=1500, category="Food"),
        ]
        result = self.engine.calculate(txs)
        self.assertTrue(any(p.penalty_type == "low_savings_ratio" for p in result.explainability.penalties))

    def test_sparse_and_no_income_confidence(self):
        txs = [Transaction(date="2026-05-01", description="Food", amount=500, category="Food")]
        result = self.engine.calculate(txs)
        self.assertLess(result.confidence.confidence_score, 0.8)
        self.assertTrue(any("Limited transaction history" in l for l in result.confidence.limitations))
        self.assertTrue(any("No income data" in l for l in result.confidence.limitations))

    def test_empty_input_safe(self):
        result = self.engine.calculate([])
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 100)
        self.assertEqual(result.scoring_version, "carebank-score-v1.0")

    def test_confidence_quality_bounded(self):
        result = self.engine.calculate(self.transactions)
        self.assertGreaterEqual(result.confidence.confidence_score, 0)
        self.assertLessEqual(result.confidence.confidence_score, 1)
        self.assertGreaterEqual(result.confidence.data_quality_score, 0)
        self.assertLessEqual(result.confidence.data_quality_score, 1)


class TestScoringRouteIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: UserContext(id="u1", email="u1@example.com")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    async def test_financial_score_endpoint_contract(self):
        txs = [
            Transaction(date="2026-05-01", description="Salary", amount=-50000, category="Income"),
            Transaction(date="2026-05-02", description="Rent", amount=15000, category="Bills"),
        ]
        with patch("app.services.supabase.SupabaseService.fetch_transactions", new=AsyncMock(return_value=txs)), patch(
            "app.services.supabase.SupabaseService.persist_financial_score_snapshot", new=AsyncMock()
        ) as persist_mock:
            response = self.client.get("/financial-score", headers={"Authorization": "Bearer t"})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIn("score", body)
            self.assertIn("status", body)
            self.assertIn("breakdown", body)
            self.assertIn("metrics", body)
            self.assertIn("summary", body)
            self.assertIn("major_issues", body)
            self.assertIn("positive_signals", body)
            self.assertIn("risk_timeline", body)
            self.assertIn("scoring_version", body)
            self.assertIn("explainability", body)
            self.assertIn("confidence", body)
            persist_mock.assert_awaited()

    async def test_analyze_backward_compatibility(self):
        txs = [
            Transaction(date="2026-05-01", description="Salary", amount=-50000, category="Income"),
            Transaction(date="2026-05-02", description="Rent", amount=15000, category="Bills"),
        ]
        with patch("app.services.supabase.SupabaseService.fetch_transactions", new=AsyncMock(return_value=txs)):
            response = self.client.get("/analyze", headers={"Authorization": "Bearer t"})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIn("financial_health", body)
            self.assertIn("score", body["financial_health"])
            self.assertIn("scoring_version", body["financial_health"])
            self.assertIn("recommendations", body)
            self.assertIsInstance(body["recommendations"], list)

    async def test_copilot_scoring_context(self):
        orchestrator = CopilotOrchestrator()
        scoped = orchestrator._scoped_context(
            {
                "financial_health": {
                    "score": 72,
                    "status": "Good",
                    "scoring_version": "carebank-score-v1.0",
                    "explainability": {"contributions": [{"component": "savings"}], "penalties": [{"penalty_type": "x"}]},
                    "confidence": {"confidence_score": 0.8, "data_quality_score": 0.9, "limitations": ["x"]},
                }
            }
        )
        self.assertIn("scoring", scoped)
        self.assertIn("top_contributions", scoped["scoring"])
        self.assertIn("top_penalties", scoped["scoring"])
        self.assertIn("confidence_score", scoped["scoring"])


if __name__ == "__main__":
    unittest.main()
