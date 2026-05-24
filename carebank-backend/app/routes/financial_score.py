import logging

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.models.schemas import FinancialScoreResponse, UserContext
from app.services.rate_limiter import get_rate_limiter
from app.services.scoring import FinancialScoringEngine
from app.services.supabase import SupabaseService

router = APIRouter(tags=["score"])
security = HTTPBearer(auto_error=False)
scoring_engine = FinancialScoringEngine()
logger = logging.getLogger(__name__)


@router.get("/financial-score", response_model=FinancialScoreResponse)
async def get_financial_score(
    request: Request,
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> FinancialScoreResponse:
    await get_rate_limiter().enforce(request, user.id)
    service = SupabaseService(get_settings())
    access_token = credentials.credentials if credentials else ""
    transactions = await service.fetch_transactions(access_token)
    logger.info("Financial-score route loaded transactions: count=%s user_id=%s", len(transactions), user.id)
    response = scoring_engine.calculate(transactions)
    await service.persist_financial_score_snapshot(access_token, user_id=user.id, snapshot=response.model_dump())
    return response
