from __future__ import annotations

import os
from urllib.parse import urlparse

from app.core.config import Settings
from app.services.security_audit import SecurityAuditLogger


class SecurityStartupError(RuntimeError):
    pass


def validate_security_startup(settings: Settings) -> None:
    strict = settings.is_production or settings.require_strict_security
    if not strict:
        return

    failures: list[str] = []
    if settings.enable_sample_data_fallback:
        failures.append("ENABLE_SAMPLE_DATA_FALLBACK must be disabled in strict mode.")
    if settings.enable_local_event_fallback:
        failures.append("ENABLE_LOCAL_EVENT_FALLBACK must be disabled in strict mode.")
    if settings.enable_websocket_dev_fallback:
        failures.append("ENABLE_WEBSOCKET_DEV_FALLBACK must be disabled in strict mode.")
    if not settings.enable_audit_persistence:
        failures.append("ENABLE_AUDIT_PERSISTENCE must be enabled in strict mode.")
    if not settings.supabase_service_role_configured:
        failures.append("SUPABASE_SERVICE_ROLE_KEY is required in strict mode.")
    if not settings.internal_metrics_token:
        failures.append("INTERNAL_METRICS_TOKEN is required in strict mode.")

    origins = [part.strip() for part in settings.frontend_url.split(",") if part.strip()]
    for origin in origins:
        lowered = origin.lower()
        if "*" in lowered or "vercel.app" in lowered and lowered.startswith("https://*."):
            failures.append("Wildcard/broad CORS origins are not allowed in strict mode.")
        parsed = urlparse(lowered)
        host = parsed.hostname or ""
        if host in {"localhost", "127.0.0.1"}:
            failures.append("Localhost frontend URL is not allowed in strict mode.")

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    llm_key = os.getenv("OPENAI_API_KEY", "").strip() or openrouter_key
    if settings.ai_categorization_enabled and not openrouter_key:
        failures.append("AI_CATEGORIZATION_ENABLED requires OPENROUTER_API_KEY in strict mode.")
    if not llm_key:
        failures.append("LLM features require OPENAI_API_KEY or OPENROUTER_API_KEY in strict mode.")

    if failures:
        audit = SecurityAuditLogger()
        for failure in failures:
            audit.log_security_startup_failure(failure, {"app_env": settings.app_env})
        raise SecurityStartupError(" ; ".join(failures))
