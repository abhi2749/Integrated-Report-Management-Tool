from __future__ import annotations

import os
import secrets
from typing import Any

from config import (
    APP_ENV,
    CORS_ALLOW_CREDENTIALS,
    CORS_ORIGINS,
    MAX_CONCURRENT_REPORTS,
    REPORT_RESOURCE_WAIT_SECONDS,
    SECRET_KEY,
    SECURE_COOKIES,
)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


# Configuration is now sourced from the centralized config module.
PRODUCTION = APP_ENV in {"production", "prod"}

# Do not put credentials or tokens in application logs.
SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "access_token",
    "refresh_token",
    "authorization",
    "token",
    "secret",
    "api_key",
}


def redact_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if str(key).lower() in SENSITIVE_KEYS else redact_mapping(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    return value


def validate_runtime() -> dict[str, Any]:
    """Return a safe runtime security summary; never exposes secrets."""
    warnings: list[str] = []

    if PRODUCTION:
        if not SECRET_KEY:
            warnings.append("SECRET_KEY is not configured.")
        if CORS_ALLOW_CREDENTIALS and "*" in CORS_ORIGINS:
            warnings.append("Wildcard CORS cannot be used with credentials in production.")

    return {
        "environment": APP_ENV,
        "production": PRODUCTION,
        "secure_cookies": SECURE_COOKIES,
        "cors_allow_credentials": CORS_ALLOW_CREDENTIALS,
        "max_concurrent_reports": MAX_CONCURRENT_REPORTS,
        "report_resource_wait_seconds": REPORT_RESOURCE_WAIT_SECONDS,
        "warnings": warnings,
        "secrets_redacted": True,
    }


def require_production_secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if PRODUCTION and len(value) < 32:
        raise RuntimeError(f"{name} must be configured with at least 32 characters in production.")
    if not value:
        return secrets.token_urlsafe(48)
    return value
