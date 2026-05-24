from __future__ import annotations

from app.core.config import get_settings
from app.services.jwt_validator import JWTValidator


class AuthValidator:
    def __init__(self) -> None:
        settings = get_settings()
        self.jwt_validator = JWTValidator(cache_ttl_seconds=settings.auth_jwks_cache_ttl_seconds)

    def prevalidate(self, token: str) -> bool:
        result = self.jwt_validator.validate(token)
        return result.valid

