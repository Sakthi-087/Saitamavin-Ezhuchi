from __future__ import annotations

from typing import Any


SENSITIVE_KEYS = {
    "access_token",
    "authorization",
    "bearer",
    "api_key",
    "service_role",
    "service_role_key",
    "password",
    "secret",
    "refresh_token",
    "openrouter_api_key",
    "openrouter",
    "openai_api_key",
}


def _mask(value: str) -> str:
    if len(value) <= 6:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, str):
        lower = value.lower()
        if "bearer " in lower or "sk-" in lower or "openrouter" in lower:
            return _mask(value)
        # jwt-like token pattern: three dot-separated base64url chunks
        parts = value.split(".")
        if len(parts) == 3 and all(part and all(ch.isalnum() or ch in "-_" for ch in part) for part in parts):
            return "***JWT***"
        if "@" in value and "." in value:
            local, _, domain = value.partition("@")
            return f"{(local[:1] + '***') if local else '***'}@{domain}"
    return value


def redact_dict(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = key.lower()
        if lowered in SENSITIVE_KEYS:
            redacted[key] = "***REDACTED***"
            continue
        if isinstance(value, dict):
            redacted[key] = redact_dict(value)
        elif isinstance(value, list):
            redacted[key] = [redact_dict(item) if isinstance(item, dict) else redact_sensitive(item) for item in value]
        else:
            redacted[key] = redact_sensitive(value)
    return redacted
