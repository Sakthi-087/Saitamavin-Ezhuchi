import logging

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.models.schemas import FraudCheckResponse, FraudFinding, UserContext
from app.services.rate_limiter import get_rate_limiter
from app.services.supabase import SupabaseService

router = APIRouter(tags=["fraud"])
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


@router.get("/fraud-check", response_model=FraudCheckResponse)
async def fraud_check(
    request: Request,
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> FraudCheckResponse:
    await get_rate_limiter().enforce(request, user.id)
    service = SupabaseService(get_settings())
    history = await service.fetch_transaction_history(credentials.credentials if credentials else "")
    logger.info("Fraud-check route loaded transaction history: count=%s user_id=%s", len(history), user.id)
    flagged_transactions = [
        FraudFinding(
            description=str(item.get("description") or "Unknown transaction"),
            amount=round(abs(float(item.get("amount") or 0)), 2),
            risk=str(item.get("fraud_risk") or "Low"),
            flags=[str(flag) for flag in (item.get("fraud_flags") or [])],
        )
        for item in history
        if str(item.get("fraud_risk") or "").lower() in {"medium", "high"}
    ]
    return FraudCheckResponse(flagged_transactions=flagged_transactions)
