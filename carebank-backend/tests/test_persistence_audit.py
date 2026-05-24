from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.config import Settings
from app.main import app
from app.models.schemas import UserContext
from app.services.event_store import EventStore


class TestPersistenceMigration(unittest.TestCase):
    def setUp(self) -> None:
        self.migration_path = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "001_initial_carebank_schema.sql"
        self.sql = self.migration_path.read_text(encoding="utf-8")

    def test_migration_file_exists(self):
        self.assertTrue(self.migration_path.exists())

    def test_required_tables_declared(self):
        required = [
            "profiles",
            "transactions",
            "behavior_snapshots",
            "risk_snapshots",
            "guidance_snapshots",
            "financial_score_snapshots",
            "system_events",
            "processing_events",
            "live_alert_events",
            "risk_events",
            "guidance_items",
            "dead_letter_events",
            "event_replay_history",
            "audit_logs",
        ]
        for table in required:
            self.assertIn(f"create table if not exists {table}", self.sql.lower())

    def test_required_indexes_declared(self):
        self.assertIn("idx_transactions_user_created", self.sql)
        self.assertIn("created_at desc", self.sql.lower())
        self.assertIn("correlation_id", self.sql.lower())
        self.assertIn("idempotency_key text unique", self.sql.lower())
        self.assertIn("event_id text not null unique", self.sql.lower())

    def test_rls_enabled_statements_exist(self):
        self.assertIn("alter table transactions enable row level security", self.sql.lower())
        self.assertIn("user_id = auth.uid()", self.sql.lower())


class TestPersistenceConfigAndSafety(unittest.TestCase):
    def test_service_role_config_present(self):
        settings = Settings()
        self.assertTrue(hasattr(settings, "supabase_service_role_key"))
        self.assertTrue(hasattr(settings, "enable_local_event_fallback"))
        self.assertTrue(hasattr(settings, "enable_audit_persistence"))

    def test_token_not_logged_by_auth_module(self):
        auth_path = Path(__file__).resolve().parents[1] / "app" / "core" / "auth.py"
        content = auth_path.read_text(encoding="utf-8")
        self.assertNotIn("credentials.credentials[:12]", content)

    def test_event_store_redacts_sensitive_payloads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "data" / "snapshots").mkdir(parents=True, exist_ok=True)
            store = EventStore(root)
            store.persist_audit_log("test_event", {"authorization": "Bearer abc", "metadata": {"access_token": "x"}})
            content = (root / "data" / "snapshots" / "audit_logs.jsonl").read_text(encoding="utf-8")
            self.assertIn("***REDACTED***", content)

    def test_local_fallback_gated_by_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "data" / "snapshots").mkdir(parents=True, exist_ok=True)
            settings = Settings()
            settings.enable_local_event_fallback = False
            settings.enable_audit_persistence = True
            settings.supabase_url = "https://example.supabase.co"
            settings.supabase_service_role_key = "service-key"
            with patch("app.services.event_store.get_settings", return_value=settings):
                store = EventStore(root)
                with patch.object(store, "_persist_service_role", return_value=False):
                    store.persist_audit_log("test_event", {"x": 1})
                self.assertFalse((root / "data" / "snapshots" / "audit_logs.jsonl").exists())


class TestHistoryRoutes(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: UserContext(id="u1", email="u1@example.com")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    async def test_history_routes_auth_required(self):
        app.dependency_overrides.clear()
        response = self.client.get("/history/financial-scores")
        self.assertEqual(response.status_code, 401)

    async def test_history_user_scoped_and_limit_bounded(self):
        with patch(
            "app.services.supabase.SupabaseService.get_financial_score_history",
            new=AsyncMock(return_value=[{"id": "1", "user_id": "u1", "score": 60}]),
        ) as mocked:
            response = self.client.get("/history/financial-scores?limit=200", headers={"Authorization": "Bearer t"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["limit"], 200)
            _, user_id = mocked.await_args.args[:2]
            self.assertEqual(user_id, "u1")

    async def test_audit_endpoint_sanitized(self):
        with patch(
            "app.services.supabase.SupabaseService.get_audit_history",
            new=AsyncMock(return_value=[{"id": "a1", "metadata": {"authorization": "Bearer abc"}}]),
        ):
            response = self.client.get("/history/audit-events", headers={"Authorization": "Bearer t"})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["items"][0]["metadata"]["authorization"], "***REDACTED***")


if __name__ == "__main__":
    unittest.main()
