from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.auth import get_current_user
from app.core.config import Settings
from app.main import app
from app.models.schemas import UserContext
from app.services.rate_limiter import RateLimiter
from app.services.redaction import redact_dict
from app.services.security_startup import SecurityStartupError, validate_security_startup
from app.services.supabase import SupabaseService


class TestSecurityStartup(unittest.TestCase):
    def test_production_fails_if_sample_fallback_enabled(self):
        settings = Settings()
        settings.app_env = "production"
        settings.require_strict_security = True
        settings.enable_sample_data_fallback = True
        settings.enable_websocket_dev_fallback = False
        settings.supabase_url = "https://x.supabase.co"
        settings.supabase_service_role_key = "service"
        settings.internal_metrics_token = "token"
        settings.frontend_url = "https://app.example.com"
        with patch("os.getenv", return_value="openrouter-key"):
            with self.assertRaises(SecurityStartupError):
                validate_security_startup(settings)

    def test_production_fails_if_ws_dev_fallback_enabled(self):
        settings = Settings()
        settings.app_env = "production"
        settings.require_strict_security = True
        settings.enable_sample_data_fallback = False
        settings.enable_websocket_dev_fallback = True
        settings.supabase_url = "https://x.supabase.co"
        settings.supabase_service_role_key = "service"
        settings.internal_metrics_token = "token"
        settings.frontend_url = "https://app.example.com"
        with patch("os.getenv", return_value="openrouter-key"):
            with self.assertRaises(SecurityStartupError):
                validate_security_startup(settings)

    def test_production_fails_if_service_role_missing(self):
        settings = Settings()
        settings.app_env = "production"
        settings.require_strict_security = True
        settings.enable_sample_data_fallback = False
        settings.enable_websocket_dev_fallback = False
        settings.supabase_url = "https://x.supabase.co"
        settings.supabase_service_role_key = ""
        settings.internal_metrics_token = "token"
        settings.frontend_url = "https://app.example.com"
        with patch("os.getenv", return_value="openrouter-key"):
            with self.assertRaises(SecurityStartupError):
                validate_security_startup(settings)

    def test_production_fails_for_localhost_frontend(self):
        settings = Settings()
        settings.app_env = "production"
        settings.require_strict_security = True
        settings.enable_sample_data_fallback = False
        settings.enable_websocket_dev_fallback = False
        settings.supabase_url = "https://x.supabase.co"
        settings.supabase_service_role_key = "service"
        settings.internal_metrics_token = "token"
        settings.frontend_url = "http://localhost:5173"
        with patch("os.getenv", return_value="openrouter-key"):
            with self.assertRaises(SecurityStartupError):
                validate_security_startup(settings)

    def test_production_fails_for_wildcard_cors(self):
        settings = Settings()
        settings.app_env = "production"
        settings.require_strict_security = True
        settings.enable_sample_data_fallback = False
        settings.enable_websocket_dev_fallback = False
        settings.supabase_url = "https://x.supabase.co"
        settings.supabase_service_role_key = "service"
        settings.internal_metrics_token = "token"
        settings.frontend_url = "https://*.vercel.app"
        with patch("os.getenv", return_value="openrouter-key"):
            with self.assertRaises(SecurityStartupError):
                validate_security_startup(settings)

    def test_production_fails_if_metrics_token_missing(self):
        settings = Settings()
        settings.app_env = "production"
        settings.require_strict_security = True
        settings.enable_sample_data_fallback = False
        settings.enable_websocket_dev_fallback = False
        settings.supabase_url = "https://x.supabase.co"
        settings.supabase_service_role_key = "service"
        settings.internal_metrics_token = ""
        settings.frontend_url = "https://app.example.com"
        with patch("os.getenv", return_value="openrouter-key"):
            with self.assertRaises(SecurityStartupError):
                validate_security_startup(settings)

    def test_production_ai_enabled_without_key_fails(self):
        settings = Settings()
        settings.app_env = "production"
        settings.require_strict_security = True
        settings.enable_sample_data_fallback = False
        settings.enable_websocket_dev_fallback = False
        settings.supabase_url = "https://x.supabase.co"
        settings.supabase_service_role_key = "service"
        settings.internal_metrics_token = "token"
        settings.frontend_url = "https://app.example.com"
        settings.ai_categorization_enabled = True
        with patch("os.getenv", return_value=""):
            with self.assertRaises(SecurityStartupError):
                validate_security_startup(settings)


class TestSecurityRuntime(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_user] = lambda: UserContext(id="u1", email="u1@example.com")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    async def test_metrics_requires_internal_token(self):
        with patch("app.routes.health.get_settings") as settings_mock:
            settings = settings_mock.return_value
            settings.internal_metrics_token = "token"
            forbidden = self.client.get("/metrics")
            self.assertEqual(forbidden.status_code, 403)
            ok = self.client.get("/metrics", headers={"X-Internal-Metrics-Token": "token"})
            self.assertEqual(ok.status_code, 200)

    async def test_health_public_minimal(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("status", payload)
        self.assertIn("environment", payload)
        self.assertNotIn("realtime_metrics", payload)

    async def test_health_internal_protected(self):
        with patch("app.routes.health.get_settings") as settings_mock:
            settings = settings_mock.return_value
            settings.internal_metrics_token = "token"
            forbidden = self.client.get("/health/internal")
            self.assertEqual(forbidden.status_code, 403)
            ok = self.client.get("/health/internal", headers={"X-Internal-Metrics-Token": "token"})
            self.assertEqual(ok.status_code, 200)

    async def test_auth_failure_no_demo_user_in_production(self):
        settings = Settings()
        settings.app_env = "production"
        settings.enable_sample_data_fallback = True
        service = SupabaseService(settings)
        with patch("httpx.AsyncClient.get", side_effect=httpx.RequestError("fail", request=httpx.Request("GET", "https://x"))):
            with self.assertRaises(HTTPException):
                await service.verify_access_token("bad")

    async def test_rate_limiter_returns_429_after_limit(self):
        limiter = RateLimiter()
        limiter.enabled = True
        limiter.limit_per_minute = 1
        r1 = await limiter.check("u1:/chat", limit=1)
        r2 = await limiter.check("u1:/chat", limit=1)
        self.assertTrue(r1.allowed)
        self.assertFalse(r2.allowed)

    async def test_websocket_missing_token_rejected(self):
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/ws/u1"):
                pass

    async def test_websocket_user_mismatch_rejected(self):
        with patch("app.services.supabase.SupabaseService.verify_access_token", new=AsyncMock(return_value=UserContext(id="u2", email="u2@example.com"))):
            with self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect("/ws/u1?token=fake"):
                    pass

    async def test_websocket_rate_limit_rejected(self):
        limiter_mock = AsyncMock()
        limiter_mock.check.return_value.allowed = False
        with patch("app.routes.realtime.get_rate_limiter", return_value=limiter_mock), patch(
            "app.services.supabase.SupabaseService.verify_access_token", new=AsyncMock(return_value=UserContext(id="u1", email="u1@example.com"))
        ):
            with self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect("/ws/u1?token=fake"):
                    pass

    async def test_redaction_masks_secrets(self):
        red = redact_dict(
            {
                "access_token": "abc",
                "authorization": "Bearer secret",
                "service_role_key": "role",
                "openrouter_api_key": "sk-123",
                "email": "test@example.com",
                "jwt": "aaa.bbb.ccc",
            }
        )
        self.assertEqual(red["access_token"], "***REDACTED***")
        self.assertEqual(red["authorization"], "***REDACTED***")
        self.assertEqual(red["service_role_key"], "***REDACTED***")
        self.assertEqual(red["openrouter_api_key"], "***REDACTED***")
        self.assertIn("***", red["email"])

    async def test_audit_logger_called_for_auth_failure(self):
        app.dependency_overrides.clear()
        with patch("app.core.auth.audit_logger.log_auth_failure") as audit_mock:
            response = self.client.get("/analyze")
            self.assertEqual(response.status_code, 401)
            audit_mock.assert_called()


if __name__ == "__main__":
    unittest.main()
