import logging
from datetime import UTC, datetime
from hashlib import sha1
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.models.schemas import AnalysisResponse, SystemEvent, UserContext
from app.services.coordinator import CoordinatorAgent
from app.services.event_bus import get_event_bus
from app.services.event_store import EventStore
from app.services.idempotency_store import IdempotencyStore
from app.services.rate_limiter import get_rate_limiter
from app.services.supabase import SupabaseService

router = APIRouter(tags=["analysis"])
coordinator = CoordinatorAgent()
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)
event_store = EventStore(Path(__file__).resolve().parents[2])


@router.get("/analyze", response_model=AnalysisResponse)
async def analyze_finances(
    request: Request,
    user: UserContext = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> AnalysisResponse:
    await get_rate_limiter().enforce(request, user.id)
    service = SupabaseService(get_settings())
    correlation_id = f"corr_{uuid4().hex[:12]}"
    start_event = _build_event("analysis_started", user.id, correlation_id, {"source": "analyze_route"})
    event_store.persist_system_event(start_event)
    await get_event_bus().publish(start_event)
    transactions = await service.fetch_transactions(credentials.credentials if credentials else "")
    logger.info("Analyze route loaded transactions: count=%s user_id=%s", len(transactions), user.id)
    try:
        response = await coordinator.analyze(transactions)
        completed_event = _build_event(
            "analysis_completed",
            user.id,
            correlation_id,
            {"transaction_count": len(transactions), "source": "analyze_route"},
        )
        event_store.persist_system_event(completed_event)
        await get_event_bus().publish(completed_event)
        return response
    except Exception:
        failed_event = _build_event(
            "analysis_failed",
            user.id,
            correlation_id,
            {"transaction_count": len(transactions), "source": "analyze_route"},
        )
        event_store.persist_system_event(failed_event)
        await get_event_bus().publish(failed_event)
        raise


def _build_event(event_type: str, user_id: str, correlation_id: str, payload: dict[str, object]) -> SystemEvent:
    raw = f"{event_type}:{user_id}:{correlation_id}:{uuid4().hex}"
    event_id = f"evt_{sha1(raw.encode('utf-8')).hexdigest()[:16]}"
    return SystemEvent(
        event_id=event_id,
        event_type=event_type,
        user_id=user_id,
        correlation_id=correlation_id,
        idempotency_key=IdempotencyStore.make_key(event_type, user_id, correlation_id),
        payload=payload,
        status="pending",
        attempt_count=0,
        max_attempts=3,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=None,
    )
