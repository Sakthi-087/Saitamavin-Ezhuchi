import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app
from app.models.schemas import Transaction, UserContext
from app.services.alerts import AlertAgent
from app.services.copilot_orchestrator import CopilotOrchestrator
from app.services.guidance_engine import GuidanceEngine
from app.services.risk_intelligence import RiskIntelligenceEngine


def _tx(date: str, amount: float, category: str, description: str, transaction_type: str = "debit") -> dict:
    return {
        "date": date,
        "amount": amount,
        "category": category,
        "description": description,
        "transaction_type": transaction_type,
    }


class TestRiskIntelligence(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = RiskIntelligenceEngine()
        self.transactions = [
            _tx("2026-05-01", 2500, "Shopping", "Store A"),
            _tx("2026-05-02", 1800, "Food", "Store B"),
            _tx("2026-05-03", 3000, "Travel", "Store C"),
            _tx("2026-05-04", 900, "Bills", "Store D"),
        ]
        self.behavior = {
            "drift_score": 68.0,
            "anomaly_score": 0.72,
            "spend_velocity_7d_vs_30d": 0.8,
            "merchant_recurrence": [
                {"merchant": "NETFLIX", "recurrence_confidence": 0.9},
                {"merchant": "SPOTIFY", "recurrence_confidence": 0.85},
                {"merchant": "GYM", "recurrence_confidence": 0.8},
            ],
            "parse_errors": [],
            "valid_transaction_count": 4,
            "metrics": {"anomaly_count": 4},
            "drift_severity": "High",
        }
        self.scoring = {"score": 38, "metrics": {"income": 5000, "expenses": 8200}, "breakdown": {"risk_score": 30}}

    def test_empty_input_safe_result(self):
        result = self.engine.analyze_risk(transactions=[], behavior={}, scoring={})
        self.assertGreaterEqual(result.overall_risk_score, 0)
        self.assertLessEqual(result.overall_risk_score, 100)
        self.assertGreaterEqual(result.confidence, 0)
        self.assertLessEqual(result.confidence, 1)

    def test_score_and_confidence_bounds(self):
        result = self.engine.analyze_risk(transactions=self.transactions, behavior=self.behavior, scoring=self.scoring)
        self.assertGreaterEqual(result.overall_risk_score, 0)
        self.assertLessEqual(result.overall_risk_score, 100)
        self.assertGreaterEqual(result.confidence, 0)
        self.assertLessEqual(result.confidence, 1)

    def test_detectors_present(self):
        result = self.engine.analyze_risk(transactions=self.transactions, behavior=self.behavior, scoring=self.scoring)
        types = {event.event_type for event in result.risk_events}
        self.assertIn("cashflow_instability", types)
        self.assertIn("spending_velocity_spike", types)
        self.assertIn("category_drift", types)
        self.assertIn("anomaly_surge", types)
        self.assertIn("high_value_spend", types)
        self.assertIn("income_expense_imbalance", types)
        self.assertIn("low_financial_health_score", types)
        self.assertIn("recurring_burden", types)

    def test_legacy_and_new_drift_scale_supported(self):
        new_scale = self.engine.analyze_risk(transactions=self.transactions, behavior={"drift_score": 60, "anomaly_score": 0.1}, scoring=self.scoring)
        legacy_scale = self.engine.analyze_risk(transactions=self.transactions, behavior={"drift_score": 0.6, "anomaly_score": 0.1}, scoring=self.scoring)
        self.assertTrue(any(e.event_type == "category_drift" for e in new_scale.risk_events))
        self.assertTrue(any(e.event_type == "category_drift" for e in legacy_scale.risk_events))

    def test_negative_values_clamped(self):
        result = self.engine.analyze_risk(
            transactions=self.transactions,
            behavior={"drift_score": -50, "anomaly_score": -0.5, "spend_velocity_7d_vs_30d": -2},
            scoring={"score": 80, "metrics": {"income": 10000, "expenses": 3000}},
        )
        self.assertGreaterEqual(result.confidence, 0)
        self.assertGreaterEqual(result.overall_risk_score, 0)

    def test_event_schema_fields(self):
        result = self.engine.analyze_risk(transactions=self.transactions, behavior=self.behavior, scoring=self.scoring)
        self.assertTrue(len(result.risk_events) > 0)
        event = result.risk_events[0].model_dump()
        for field in (
            "risk_event_id",
            "event_type",
            "risk_type",
            "severity",
            "confidence",
            "evidence",
            "recommendation",
            "source_signals",
            "created_at",
        ):
            self.assertIn(field, event)

    def test_evidence_and_recommendation_text(self):
        result = self.engine.analyze_risk(transactions=self.transactions, behavior=self.behavior, scoring=self.scoring)
        self.assertTrue(result.evidence_summary)
        self.assertTrue(result.recommendation_text)

    def test_backward_compat_alias_output(self):
        payload = self.engine.analyze(self.behavior, self.scoring)
        self.assertIn("severity", payload)
        self.assertIn("overall_risk_score", payload)
        self.assertIn("risk_events", payload)


class TestRiskRouteAndIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: UserContext(id="u1", email="u1@example.com")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    async def test_risk_analysis_endpoint(self):
        transactions = [
            Transaction(date="2026-05-01", amount=2500, category="Shopping", description="Store A"),
            Transaction(date="2026-05-02", amount=1200, category="Food", description="Store B"),
        ]
        with patch("app.services.supabase.SupabaseService.fetch_transactions", new=AsyncMock(return_value=transactions)), patch(
            "app.services.supabase.SupabaseService.persist_risk_snapshot", new=AsyncMock()
        ) as persist_mock:
            response = self.client.get("/risk-analysis", headers={"Authorization": "Bearer t"})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIn("overall_risk_score", body)
            self.assertIn("risk_level", body)
            self.assertIn("confidence", body)
            self.assertIn("risk_events", body)
            self.assertIn("risk_signals", body)
            self.assertIn("evidence_summary", body)
            self.assertIn("recommendation_text", body)
            persist_mock.assert_awaited()

    async def test_analyze_backward_compat(self):
        transactions = [
            Transaction(date="2026-05-01", amount=2500, category="Shopping", description="Store A"),
            Transaction(date="2026-05-02", amount=1200, category="Food", description="Store B"),
        ]
        with patch("app.services.supabase.SupabaseService.fetch_transactions", new=AsyncMock(return_value=transactions)):
            response = self.client.get("/analyze", headers={"Authorization": "Bearer t"})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIn("insights", body)
            self.assertIn("risk_intelligence", body["insights"])
            self.assertIn("severity", body["insights"]["risk_intelligence"])
            self.assertIn("typed", body["insights"]["risk_intelligence"])

    async def test_alerts_consume_high_severity_events(self):
        risk = {
            "risk_events": [
                {
                    "severity": "High",
                    "recommendation": "Reduce discretionary spend.",
                    "evidence": {"expense_ratio": 1.2},
                }
            ]
        }
        spending_context = {
            "current_totals": {"Shopping": 0.0, "Food": 0.0, "Travel": 0.0},
            "previous_totals": {"Shopping": 0.0, "Food": 0.0, "Travel": 0.0},
        }
        from app.models.schemas import FinancialHealth, ScoreBreakdown, ScoreMetrics

        health = FinancialHealth(
            score=40,
            status="Risky",
            risk_indicator="High",
            summary="s",
            savings_rate=0,
            breakdown=ScoreBreakdown(savings_score=0, stability_score=0, discipline_score=0, risk_score=0),
            metrics=ScoreMetrics(
                savings_ratio=0,
                income=0,
                expenses=0,
                expense_volatility=0,
                high_value_expense_count=0,
                impulse_spend_count=0,
                expense_ratio=0,
                net_balance_trend=0,
            ),
        )
        alerts = AlertAgent().analyze(spending_context, health, risk)
        self.assertTrue(any("Risk alert:" in alert for alert in alerts))

    async def test_copilot_context_includes_risk(self):
        orchestrator = CopilotOrchestrator()
        ctx = orchestrator._scoped_context(
            {
                "financial_health": {},
                "spending": {},
                "alerts": [],
                "recommendations": [],
                "insights": {
                    "risk_intelligence": {
                        "overall_risk_score": 67,
                        "risk_level": "High",
                        "confidence": 0.8,
                        "evidence_summary": "Detected risk events.",
                        "mitigation_suggestion": "Act now.",
                        "source_signals": ["behavior_drift"],
                        "typed": {"risk_events": [{"risk_event_id": "r1"}]},
                    }
                },
            }
        )
        self.assertIn("risk_intelligence", ctx)
        self.assertIn("overall_risk_score", ctx["risk_intelligence"])
        self.assertIn("top_risk_events", ctx["risk_intelligence"])

    def test_risk_guidance_pipeline(self):
        risk = RiskIntelligenceEngine().analyze({"drift_score": 0.8, "anomaly_score": 0.7}, {"breakdown": {"risk_score": 30}})
        self.assertEqual(risk["severity"], "High")
        guidance = GuidanceEngine().build(risk, {"weekend_spending_drift": 0.6}, {"metrics": {"savings_ratio": 0.1}})
        self.assertTrue(len(guidance["items"]) >= 1)


if __name__ == "__main__":
    unittest.main()
