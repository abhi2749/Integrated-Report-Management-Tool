"""Safe startup and clean-machine validation helpers for ReportingTool."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

REQUIRED_BACKEND_FILES = (
    "main.py", "config.py", "auth.py", "auth_api.py", "database.py",
    "execution_manager.py", "metadata_repository.py", "query_model.py",
    "query_planner.py", "join_engine.py",
)


def validate_backend_layout(base_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(base_dir or Path(__file__).resolve().parent)
    missing = [name for name in REQUIRED_BACKEND_FILES if not (root / name).is_file()]
    return {"ok": not missing, "base_dir": str(root), "missing_files": missing}


def validate_environment(env: dict[str, str] | None = None) -> dict[str, Any]:
    values = dict(os.environ if env is None else env)
    app_env = values.get("APP_ENV", "development").strip().lower()
    errors: list[str] = []
    warnings: list[str] = []
    if values.get("SECRET_KEY", "").strip() and len(values.get("SECRET_KEY", "").strip()) < 32:
        errors.append("SECRET_KEY must contain at least 32 characters when configured.")
    if values.get("ENCRYPTION_KEY", "").strip():
        try:
            from cryptography.fernet import Fernet
            Fernet(values["ENCRYPTION_KEY"].strip().encode("utf-8"))
        except Exception:
            errors.append("ENCRYPTION_KEY is not a valid Fernet key.")
    if values.get("SECRET_KEY_PREVIOUS", "").strip() and len(values.get("SECRET_KEY_PREVIOUS", "").strip()) < 32:
        errors.append("SECRET_KEY_PREVIOUS must contain at least 32 characters when configured.")
    if values.get("ENCRYPTION_KEY_PREVIOUS", "").strip():
        try:
            from cryptography.fernet import Fernet
            Fernet(values["ENCRYPTION_KEY_PREVIOUS"].strip().encode("utf-8"))
        except Exception:
            errors.append("ENCRYPTION_KEY_PREVIOUS is not a valid Fernet key.")
    if app_env == "production" and values.get("APP_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}:
        errors.append("APP_DEBUG must be false when APP_ENV=production.")
    if app_env == "production" and values.get("CORS_ALLOW_CREDENTIALS", "true").strip().lower() in {"1", "true", "yes", "on"}:
        origins = [item.strip() for item in values.get("CORS_ORIGINS", "").split(",") if item.strip()]
        if "*" in origins:
            errors.append("Wildcard CORS_ORIGINS cannot be used with credentials in production.")
    if app_env == "production" and values.get("SECURE_COOKIES", "true").strip().lower() in {"0", "false", "no", "off"}:
        errors.append("SECURE_COOKIES must be true when APP_ENV=production.")
    if not values.get("CORS_ORIGINS", "").strip():
        warnings.append("CORS_ORIGINS is not explicitly set; application defaults will apply.")
    return {"ok": not errors, "app_env": app_env, "errors": errors, "warnings": warnings}


def validate_runtime(base_dir: str | Path | None = None, env: dict[str, str] | None = None) -> dict[str, Any]:
    layout = validate_backend_layout(base_dir)
    environment = validate_environment(env)
    return {"ok": layout["ok"] and environment["ok"], "layout": layout, "environment": environment}


if __name__ == "__main__":
    result = validate_runtime()
    print(result)
    raise SystemExit(0 if result["ok"] else 1)
