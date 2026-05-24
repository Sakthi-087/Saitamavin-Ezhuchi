from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.models.schemas import SimulationRequest, SimulationResponse, UserContext
from app.services.llm import LLMService
from app.services.rate_limiter import get_rate_limiter
from app.services.simulation import SimulationEngine
from app.services.supabase import SupabaseService

router = APIRouter(tags=["simulation"])
security = HTTPBearer(auto_error=False)
simulation_engine = SimulationEngine()
llm_service = LLMService()


@router.post("/simulate", response_model=SimulationResponse)
async def simulate_financial_decision(
    payload: SimulationRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> SimulationResponse:
    await get_rate_limiter().enforce(request, user.id)
    service = SupabaseService(get_settings())
    transactions = await service.fetch_transactions(credentials.credentials if credentials else "")
    result = simulation_engine.simulate(
        transactions=transactions,
        simulated_cost=payload.amount,
        window_days=payload.window_days,
        safety_threshold=payload.safety_threshold,
    )
    result.ai_explanation = await llm_service.explain_simulation(result.model_dump(exclude={"ai_explanation"}))
    return result
