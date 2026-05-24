import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app
from app.models.schemas import UserContext
from app.services.behavioral_intelligence import BehavioralIntelligenceEngine


def _tx(date: str, amount: float, category: str, description: str, transaction_type: str = "debit") -> dict:
    return {
        "date": date,
        "amount": amount,
        "category": category,
        "description": description,
        "transaction_type": transaction_type,
    }


class TestBehavioralIntelligence(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = BehavioralIntelligenceEngine()
        self.transactions = [
            _tx("2026-05-15T10:00:00+00:00", 500, "Food", "Swiggy"),
            _tx("2026-05-16T00:30:00+00:00", 1200, "shopping", "Amazon"),
            _tx("2026-05-17T01:45:00+00:00", 2200, "Travel", "Uber"),
            _tx("2026-05-18T11:00:00+00:00", 300, "Food", "Swiggy"),
            _tx("2026-04-10T12:00:00+00:00", 700, "Bills", "Electricity"),
            _tx("2026-04-12T12:00:00+00:00", 650, "Bills", "Electricity"),
            _tx("2026-04-15T12:00:00+00:00", 680, "Bills", "Electricity"),
            _tx("2026-05-10T08:00:00+00:00", 2000, "Food", "Restaurant"),
        ]

    def test_empty_input(self):
        result = self.engine.analyze_behavior([])
        self.assertEqual(result.transaction_count, 0)
        self.assertEqual(result.valid_transaction_count, 0)
        self.assertEqual(result.anomaly_score, 0.0)

    def test_invalid_date_reported(self):
        result = self.engine.analyze_behavior([_tx("bad-date", 100, "Food", "Cafe")])
        self.assertEqual(result.valid_transaction_count, 0)
        self.assertTrue(any("invalid date" in err for err in result.parse_errors))

    def test_invalid_amount_reported(self):
        bad = {"date": "2026-05-10", "amount": "not-a-number", "category": "Food", "description": "Cafe"}
        result = self.engine.analyze_behavior([bad])
        self.assertEqual(result.valid_transaction_count, 0)
        self.assertTrue(any("invalid amount" in err for err in result.parse_errors))

    def test_income_refund_excluded(self):
        txs = [
            _tx("2026-05-01", 1000, "Food", "Cafe"),
            _tx("2026-05-02", -50000, "Income", "Salary"),
            _tx("2026-05-03", 800, "Refund", "Store", "refund"),
        ]
        result = self.engine.analyze_behavior(txs)
        self.assertAlmostEqual(result.last_30_days_spend, 1000.0)

    def test_dynamic_category_and_casing_normalization(self):
        txs = [_tx("2026-05-01", 400, "food", "Cafe"), _tx("2026-05-02", 600, "Food", "Cafe")]
        result = self.engine.analyze_behavior(txs)
        self.assertEqual(result.category_totals["Food"], 1000.0)
        self.assertEqual(result.category_transaction_counts["Food"], 2)

    def test_rolling_windows_anchored_to_latest_transaction(self):
        result = self.engine.analyze_behavior(self.transactions)
        self.assertGreater(result.last_7_days_spend, 0)
        self.assertGreater(result.last_30_days_spend, 0)
        self.assertGreater(result.last_90_days_spend, 0)
        self.assertGreater(result.previous_30_days_spend, 0)

    def test_spend_velocity_and_mom(self):
        result = self.engine.analyze_behavior(self.transactions)
        self.assertIsInstance(result.spend_velocity_7d_vs_30d, float)
        self.assertIsInstance(result.month_over_month_change, float)

    def test_baseline_profile_exists(self):
        result = self.engine.analyze_behavior(self.transactions)
        self.assertGreaterEqual(result.baseline.average_transaction_amount, 0)
        self.assertIsInstance(result.baseline.usual_active_hours, list)
        self.assertIsInstance(result.baseline.top_merchants, list)

    def test_category_drift_and_bounds(self):
        result = self.engine.analyze_behavior(self.transactions)
        self.assertTrue(len(result.category_drift) >= 1)
        self.assertGreaterEqual(result.drift_score, 0)
        self.assertLessEqual(result.drift_score, 100)

    def test_merchant_recurrence_interval_expected_date_and_bounds(self):
        result = self.engine.analyze_behavior(self.transactions)
        self.assertTrue(any(item.merchant == "ELECTRICITY" for item in result.merchant_recurrence))
        for item in result.merchant_recurrence:
            self.assertGreaterEqual(item.recurrence_confidence, 0)
            self.assertLessEqual(item.recurrence_confidence, 1)

    def test_anomaly_events_structure(self):
        result = self.engine.analyze_behavior(self.transactions)
        for event in result.anomaly_events:
            self.assertIn("event_type", event.model_dump())
            self.assertIn("severity", event.model_dump())
            self.assertIn("confidence", event.model_dump())
            self.assertIn("evidence", event.model_dump())
            self.assertIn("recommendation_hint", event.model_dump())

    def test_specific_anomaly_types_present(self):
        result = self.engine.analyze_behavior(self.transactions)
        event_types = {item.event_type for item in result.anomaly_events}
        self.assertIn("high_value_transaction", event_types)
        self.assertIn("weekend_spending_drift", event_types)
        self.assertIn("unusual_time_activity", event_types)

    def test_backward_compat_aliases_present(self):
        payload = self.engine.analyze(self.transactions)
        self.assertIn("rolling_spend_windows", payload)
        self.assertIn("anomaly_score", payload)
        self.assertIn("drift_score", payload)


class TestBehaviorAnalysisRoute(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: UserContext(id="u1", email="u1@example.com")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_behavior_analysis_endpoint(self):
        sample = [
            _tx("2026-05-10", 500, "Food", "Cafe"),
            _tx("2026-05-11", 2500, "Travel", "Uber"),
        ]
        with patch("app.services.supabase.SupabaseService.fetch_transactions", new=AsyncMock()) as fetch_mock, patch(
            "app.services.supabase.SupabaseService.persist_behavior_snapshot", new=AsyncMock()
        ) as persist_mock:
            from app.models.schemas import Transaction

            fetch_mock.return_value = [Transaction(**item) for item in sample]
            response = self.client.get("/behavior-analysis", headers={"Authorization": "Bearer test-token"})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIn("drift_score", body)
            self.assertIn("drift_severity", body)
            self.assertIn("last_7_days_spend", body)
            self.assertIn("last_30_days_spend", body)
            self.assertIn("spend_velocity_7d_vs_30d", body)
            self.assertIn("anomaly_events", body)
            self.assertIn("merchant_recurrence", body)
            self.assertIn("parse_errors", body)
            persist_mock.assert_awaited()


if __name__ == "__main__":
    unittest.main()
