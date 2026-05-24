from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException, status

from app.core.config import get_settings
from app.services.metrics_service import get_metrics_service
from app.services.security_audit import SecurityAuditLogger

router = APIRouter(tags=["health"])
audit_logger = SecurityAuditLogger()


def _verify_internal_token(provided: str | None) -> None:
    settings = get_settings()
    expected = settings.internal_metrics_token
    if not expected or provided != expected:
        audit_logger.log_permission_denied("metrics_token_invalid_or_missing")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.get("/health")
async def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.app_env,
        "version": "1.0.0",
    }


@router.get("/metrics")
async def metrics(x_internal_metrics_token: str | None = Header(default=None)) -> dict[str, object]:
    _verify_internal_token(x_internal_metrics_token)
    return {"status": "ok", "realtime": get_metrics_service().snapshot()}


@router.get("/health/internal")
async def health_internal(x_internal_metrics_token: str | None = Header(default=None)) -> dict[str, object]:
    _verify_internal_token(x_internal_metrics_token)
    settings = get_settings()
    llm_configured = bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY"))
    return {
        "status": "ok",
        "environment": settings.app_env,
        "supabase_configured": settings.supabase_configured,
        "service_role_configured": settings.supabase_service_role_configured,
        "llm_configured": llm_configured,
        "realtime_metrics": get_metrics_service().snapshot(),
    }
