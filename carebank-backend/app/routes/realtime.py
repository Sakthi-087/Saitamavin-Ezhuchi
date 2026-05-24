from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.services.rate_limiter import get_rate_limiter
from app.services.realtime_manager import get_realtime_manager
from app.services.security_audit import SecurityAuditLogger
from app.services.supabase import SupabaseService

router = APIRouter(tags=["realtime"])
audit_logger = SecurityAuditLogger()


def _extract_token(websocket: WebSocket) -> str:
    auth = websocket.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (websocket.query_params.get("token") or "").strip()


@router.websocket("/ws/{user_id}")
async def realtime_socket(websocket: WebSocket, user_id: str) -> None:
    token = _extract_token(websocket)
    if not token:
        audit_logger.log_ws_auth_failure("missing_token", {"path_user_id": user_id})
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

    service = SupabaseService(get_settings())
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

    manager = get_realtime_manager()
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(user_id, websocket)
