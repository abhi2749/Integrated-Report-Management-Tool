"""API-facing security helpers for safe error reporting."""

from __future__ import annotations

import re
from typing import Any


_SECRET_PATTERNS = (
    re.compile(r"(?i)(password|passwd|pwd)\s*[=:]\s*[^\s,;]+"),
    re.compile(r"(?i)(authorization|bearer|token|api[_-]?key|secret)\s*[=:]\s*[^\s,;]+"),
    re.compile(r"(?i)(mysql|mongodb|clickhouse)(?:\+[^:]+)?://[^\s]+"),
)


def sanitize_error_message(message: Any, fallback: str = "The request could not be completed.") -> str:
    """Redact common credential/connection-string material without exposing internals."""
    text = str(message or "").strip()
    if not text:
        return fallback
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[redacted]", redacted)
    return redacted[:1000] or fallback


def public_exception_message(error: BaseException, fallback: str) -> str:
    """Return a bounded, credential-redacted message suitable for API responses."""
    return sanitize_error_message(error, fallback=fallback)
