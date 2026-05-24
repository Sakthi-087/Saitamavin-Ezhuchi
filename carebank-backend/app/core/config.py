from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class Settings:
    def __init__(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.app_env = os.getenv("APP_ENV", "development").strip().lower() or "development"
        self.supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY", "")
        self.supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        strict_default = "true" if self.app_env == "production" else "false"
        self.require_strict_security = os.getenv("REQUIRE_STRICT_SECURITY", strict_default).strip().lower() in {"1", "true", "yes", "on"}
        self.internal_metrics_token = os.getenv("INTERNAL_METRICS_TOKEN", "")
        rate_default = "true" if self.app_env == "production" else "false"
        self.rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", rate_default).strip().lower() in {"1", "true", "yes", "on"}
        self.rate_limit_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
        self.ws_rate_limit_per_minute = int(os.getenv("WS_RATE_LIMIT_PER_MINUTE", "20"))
        self.auth_jwks_cache_ttl_seconds = int(os.getenv("AUTH_JWKS_CACHE_TTL_SECONDS", "3600"))
        self.enable_websocket_dev_fallback = os.getenv("ENABLE_WEBSOCKET_DEV_FALLBACK", "false").strip().lower() in {"1", "true", "yes", "on"}
        self.ai_categorization_enabled = os.getenv("AI_CATEGORIZATION_ENABLED", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.ai_categorization_model = os.getenv("AI_CATEGORIZATION_MODEL", "google/gemini-2.5-flash-lite").strip() or "google/gemini-2.5-flash-lite"
        self.preferences_path = root / "data" / "preferences.json"
        self.enable_sample_data_fallback = os.getenv("ENABLE_SAMPLE_DATA_FALLBACK", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.enable_local_event_fallback = os.getenv("ENABLE_LOCAL_EVENT_FALLBACK", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.enable_audit_persistence = os.getenv("ENABLE_AUDIT_PERSISTENCE", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)

    @property
    def supabase_service_role_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
