from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.models.schemas import ChatRequest, ChatResponse, UserContext
from app.services.coordinator import CoordinatorAgent
from app.services.rate_limiter import get_rate_limiter
from app.services.supabase import SupabaseService

router = APIRouter(tags=["chat"])
coordinator = CoordinatorAgent()
security = HTTPBearer(auto_error=False)


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    payload: ChatRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> ChatResponse:
    await get_rate_limiter().enforce(request, user.id)
    service = SupabaseService(get_settings())
    transactions = await service.fetch_transactions(credentials.credentials if credentials else "")
    response = await coordinator.chat(payload.message, transactions)
    return ChatResponse(**response)
