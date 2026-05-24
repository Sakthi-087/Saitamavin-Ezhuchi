from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.models.schemas import UserContext
from app.services.auth_validator import AuthValidator
from app.services.security_audit import SecurityAuditLogger
from app.services.supabase import SupabaseService

security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)
audit_logger = SecurityAuditLogger()
auth_validator = AuthValidator()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> UserContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        audit_logger.log_auth_failure("missing_or_invalid_bearer_scheme")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")

    logger.info("Received bearer token for auth verification.")
    if not auth_validator.prevalidate(credentials.credentials):
        audit_logger.log_auth_failure("prevalidation_failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token.")

    if not settings.supabase_configured:
        audit_logger.log_auth_failure("supabase_not_configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase environment variables are not configured on the backend.",
        )

    service = SupabaseService(settings)
    try:
        user = await service.verify_access_token(credentials.credentials)
    except HTTPException:
        audit_logger.log_auth_failure("token_verification_failed")
        raise
    logger.info("Resolved current user from access token: user_id=%s email=%s", user.id, user.email)
    return user
