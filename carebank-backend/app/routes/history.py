from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.models.schemas import UserContext
from app.services.rate_limiter import get_rate_limiter
from app.services.redaction import redact_dict
from app.services.supabase import SupabaseService

router = APIRouter(tags=["history"])
security = HTTPBearer(auto_error=False)


def _bounded_limit(limit: int) -> int:
    return max(1, min(int(limit), 200))


@router.get("/history/financial-scores")
async def financial_score_history(
    request: Request,
    limit: int = Query(default=25, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, object]:
    await get_rate_limiter().enforce(request, user.id)
    token = credentials.credentials if credentials else ""
    rows = await SupabaseService(get_settings()).get_financial_score_history(token, user.id, limit=_bounded_limit(limit))
    return {"items": [redact_dict(item) for item in rows], "limit": _bounded_limit(limit)}


@router.get("/history/risk-events")
async def risk_event_history(
    request: Request,
    limit: int = Query(default=25, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, object]:
    await get_rate_limiter().enforce(request, user.id)
    token = credentials.credentials if credentials else ""
    rows = await SupabaseService(get_settings()).get_risk_event_history(token, user.id, limit=_bounded_limit(limit))
    return {"items": [redact_dict(item) for item in rows], "limit": _bounded_limit(limit)}


@router.get("/history/guidance-items")
async def guidance_history(
    request: Request,
    limit: int = Query(default=25, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, object]:
    await get_rate_limiter().enforce(request, user.id)
    token = credentials.credentials if credentials else ""
    rows = await SupabaseService(get_settings()).get_guidance_history(token, user.id, limit=_bounded_limit(limit))
    return {"items": [redact_dict(item) for item in rows], "limit": _bounded_limit(limit)}


@router.get("/history/behavior-snapshots")
async def behavior_history(
    request: Request,
    limit: int = Query(default=25, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, object]:
    await get_rate_limiter().enforce(request, user.id)
    token = credentials.credentials if credentials else ""
    rows = await SupabaseService(get_settings()).get_behavior_history(token, user.id, limit=_bounded_limit(limit))
    return {"items": [redact_dict(item) for item in rows], "limit": _bounded_limit(limit)}


@router.get("/history/audit-events")
async def audit_history(
    request: Request,
    limit: int = Query(default=25, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, object]:
    await get_rate_limiter().enforce(request, user.id)
    token = credentials.credentials if credentials else ""
    rows = await SupabaseService(get_settings()).get_audit_history(token, user.id, limit=_bounded_limit(limit))
    return {"items": [redact_dict(item) for item in rows], "limit": _bounded_limit(limit)}
