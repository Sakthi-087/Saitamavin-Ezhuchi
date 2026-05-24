from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.models.schemas import GuidanceResponse, UserContext
from app.services.behavioral_intelligence import BehavioralIntelligenceEngine
from app.services.coordinator import CoordinatorAgent
from app.services.health import FinancialHealthAgent
from app.services.rate_limiter import get_rate_limiter
from app.services.risk_intelligence import RiskIntelligenceEngine
from app.services.spending import SpendingAnalysisAgent
from app.services.supabase import SupabaseService
from app.core.config import get_settings

router = APIRouter(tags=["guidance"])
security = HTTPBearer(auto_error=False)
coordinator = CoordinatorAgent()
behavior_engine = BehavioralIntelligenceEngine()
risk_engine = RiskIntelligenceEngine()
spending_engine = SpendingAnalysisAgent()
health_engine = FinancialHealthAgent()


@router.get("/guidance", response_model=GuidanceResponse)
async def get_guidance(
    request: Request,
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> GuidanceResponse:
    await get_rate_limiter().enforce(request, user.id)
    service = SupabaseService(get_settings())
    access_token = credentials.credentials if credentials else ""
    transactions = await service.fetch_transactions(access_token)
    tx_payload = [tx.model_dump() for tx in transactions]
    behavior = behavior_engine.analyze(tx_payload)
    spending_context = spending_engine.analyze(transactions)
    health = health_engine.analyze(transactions, spending_context["summary"])
    risk = risk_engine.analyze(behavior, health.model_dump())
    result = coordinator.guidance_engine.generate_guidance(
        transactions=tx_payload,
        risk_result=risk,
        behavior_result=behavior,
        score_result=health.model_dump(),
    )
    await service.persist_guidance_items(access_token, user_id=user.id, items=[item.model_dump() for item in result.items])
    await service.persist_guidance_snapshot(access_token, user_id=user.id, snapshot=result.model_dump())
    return result
