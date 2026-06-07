from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, status
from starlette.websockets import WebSocketDisconnect

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.models.schemas import RealtimeTicketResponse, UserContext
from app.services.rate_limiter import get_rate_limiter
from app.services.realtime_manager import get_realtime_manager
from app.services.security_audit import SecurityAuditLogger
from app.services.supabase import SupabaseService
from app.services.ws_ticket_store import get_ws_ticket_store

router = APIRouter(tags=["realtime"])
audit_logger = SecurityAuditLogger()


def _extract_ticket(websocket: WebSocket) -> str:
    return (websocket.query_params.get("ticket") or "").strip()


def _extract_dev_token(websocket: WebSocket) -> str:
    auth = websocket.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (websocket.query_params.get("token") or "").strip()


@router.post("/realtime/ws-ticket", response_model=RealtimeTicketResponse)
async def issue_realtime_ticket(request: Request, user: UserContext = Depends(get_current_user)) -> RealtimeTicketResponse:
    await get_rate_limiter().enforce(request, user.id)
    ticket = get_ws_ticket_store().issue(user.id)
    return RealtimeTicketResponse(ticket=ticket.ticket, expires_in=60, expires_at=ticket.expires_at)


@router.websocket("/ws/{user_id}")
async def realtime_socket(websocket: WebSocket, user_id: str) -> None:
    settings = get_settings()
    ticket = _extract_ticket(websocket)
    if ticket:
        consumed = get_ws_ticket_store().consume(ticket, user_id)
        if consumed is None:
            audit_logger.log_ws_auth_failure("ticket_validation_failed", {"path_user_id": user_id})
            await websocket.close(code=1008)
            return
    elif settings.is_production or not settings.enable_websocket_dev_fallback:
        audit_logger.log_ws_auth_failure("missing_ticket", {"path_user_id": user_id})
        await websocket.close(code=1008)
        return
    else:
        token = _extract_dev_token(websocket)
        if not token:
            audit_logger.log_ws_auth_failure("missing_token", {"path_user_id": user_id})
            await websocket.close(code=1008)
            return

        service = SupabaseService(settings)
        try:
            user = await service.verify_access_token(token)
        except HTTPException:
            audit_logger.log_ws_auth_failure("token_validation_failed", {"path_user_id": user_id})
            await websocket.close(code=1008)
            return

        if user.id != user_id:
            audit_logger.log_ws_auth_failure("user_id_mismatch", {"path_user_id": user_id, "token_user_id": user.id})
            await websocket.close(code=1008)
            return

    limiter = get_rate_limiter()
    ip = websocket.client.host if websocket.client else "unknown"
    limit_key = f"ws_connect:{user_id}:{ip}"
    limit_result = await limiter.check(limit_key, limit=get_settings().ws_rate_limit_per_minute)
    if not limit_result.allowed:
        audit_logger.log_rate_limit({"channel": "websocket", "user_id": user_id, "ip": ip})
        await websocket.close(code=1008)
        return

    manager = get_realtime_manager()
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(user_id, websocket)
