from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.models.schemas import BehavioralIntelligenceResult, UserContext
from app.services.behavior_analysis import BehaviorAnalysisService
from app.services.rate_limiter import get_rate_limiter
from app.services.supabase import SupabaseService

router = APIRouter(tags=["behavior"])
security = HTTPBearer(auto_error=False)
engine = BehaviorAnalysisService()


@router.get("/behavior-analysis", response_model=BehavioralIntelligenceResult)
async def behavior_analysis(
    request: Request,
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> BehavioralIntelligenceResult:
    await get_rate_limiter().enforce(request, user.id)
    service = SupabaseService(get_settings())
    access_token = credentials.credentials if credentials else ""
    transactions = await service.fetch_transactions(access_token)
    result = engine.analyze_behavior([tx.model_dump() for tx in transactions])
    await service.persist_behavior_snapshot(access_token, user_id=user.id, snapshot=result.model_dump())
    return result
