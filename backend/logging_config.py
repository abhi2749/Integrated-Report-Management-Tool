from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from api_security import sanitize_error_message

from config import LOG_DIR
APP_LOG_FILE = LOG_DIR / "application.log"
AUDIT_LOG_FILE = LOG_DIR / "audit.log"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_error_message(record.getMessage(), fallback=record.getMessage() or ""),
        }
        extra = getattr(record, "audit_data", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = sanitize_error_message(self.formatException(record.exc_info), fallback="Unhandled exception.")
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    numeric_level = getattr(logging, str(level).upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Avoid duplicate handlers when uvicorn --reload imports the module again.
    if any(getattr(h, "_reporting_tool_handler", False) for h in root.handlers):
        return

    formatter = JsonFormatter()

    app_handler = RotatingFileHandler(
        APP_LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    app_handler._reporting_tool_handler = True
    app_handler.setFormatter(formatter)
    app_handler.setLevel(numeric_level)

    audit_handler = RotatingFileHandler(
        AUDIT_LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8"
    )
    audit_handler._reporting_tool_handler = True
    audit_handler.setFormatter(formatter)
    audit_handler.setLevel(logging.INFO)

    root.addHandler(app_handler)

    audit_logger = logging.getLogger("reporting.audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
    audit_logger.addHandler(audit_handler)


def get_logger(name: str = "reporting") -> logging.Logger:
    return logging.getLogger(name)


def audit_event(
    action: str,
    *,
    user: dict[str, Any] | None = None,
    success: bool = True,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
    **extra: Any,
) -> None:
    logger = logging.getLogger("reporting.audit")
    data: dict[str, Any] = {
        "event_type": "audit",
        "action": action,
        "success": bool(success),
    }

    if user:
        data["user_id"] = user.get("id")
        data["username"] = user.get("username")
        data["role"] = user.get("role")

    if resource_type:
        data["resource_type"] = resource_type
    if resource_id:
        data["resource_id"] = resource_id
    if detail:
        data["detail"] = detail

    # Never accept/store common secret fields.
    secret_names = {
        "password", "passwd", "secret", "token", "access_token",
        "refresh_token", "authorization", "api_key", "private_key",
    }
    def _safe_value(key: str, value: Any) -> Any:
        if key.lower() in secret_names:
            return "[redacted]"
        if isinstance(value, dict):
            return {str(k): _safe_value(str(k), v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_safe_value(key, item) for item in value]
        if isinstance(value, str):
            return sanitize_error_message(value, fallback=value)
        return value

    for key, value in extra.items():
        data[key] = _safe_value(str(key), value)

    logger.info(
        action,
        extra={"audit_data": data},
    )
