from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JWTValidationResult:
    valid: bool
    reason: str = ""


class JWTValidator:
    """Placeholder abstraction for future JWKS-backed token validation."""

    def __init__(self, cache_ttl_seconds: int = 3600) -> None:
        self.cache_ttl_seconds = cache_ttl_seconds

    def validate(self, token: str) -> JWTValidationResult:
        if not token:
            return JWTValidationResult(valid=False, reason="missing_token")
        return JWTValidationResult(valid=True, reason="delegated_to_supabase")

