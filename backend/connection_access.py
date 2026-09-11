from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

from metadata_repository import create_metadata_repository
from config import METADATA_DB_FILE

from config import DATA_DIR

BASE_DIR = Path(__file__).resolve().parent
ACCESS_FILE = DATA_DIR / "connection_access.json"
METADATA_REPOSITORY = create_metadata_repository(ACCESS_FILE, collection="connection_access", db_path=METADATA_DB_FILE)


def _ensure_file():
    METADATA_REPOSITORY.ensure()


def _read() -> list[dict[str, Any]]:
    return METADATA_REPOSITORY.read()


def _write(items: list[dict[str, Any]]) -> None:
    METADATA_REPOSITORY.write(items)


def get_connection_access(connection_id: str) -> dict[str, Any]:
    for item in _read():
        if item.get("connection_id") == connection_id:
            return dict(item)
    # Backward-compatible default: old connections stay accessible until
    # an administrator explicitly restricts them.
    return {
        "connection_id": connection_id,
        "mode": "all",
        "user_ids": [],
        "owner_user_id": None,
        "updated_at": None,
    }


def can_access_connection(user: dict, connection_id: str) -> bool:
    if str(user.get("role", "")).lower() == "admin":
        return True
    access = get_connection_access(connection_id)
    if access.get("mode", "all") == "all":
        return True
    return str(user.get("id")) in {str(x) for x in access.get("user_ids", [])}


def require_connection_access(user: dict, connection_id: str) -> None:
    from fastapi import HTTPException, status
    if connection_id and not can_access_connection(user, connection_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this database connection.",
        )


def set_connection_access(connection_id: str, mode: str, user_ids=None, owner_user_id=None):
    mode = str(mode).strip().lower()
    if mode not in {"all", "restricted"}:
        raise ValueError("Access mode must be 'all' or 'restricted'.")
    normalized = []
    for user_id in user_ids or []:
        value = str(user_id).strip()
        if value and value not in normalized:
            normalized.append(value)
    if mode == "all":
        normalized = []

    item = {
        "connection_id": str(connection_id),
        "mode": mode,
        "user_ids": normalized,
        "owner_user_id": owner_user_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    items = _read()
    for index, existing in enumerate(items):
        if existing.get("connection_id") == connection_id:
            items[index] = item
            _write(items)
            return item

    items.append(item)
    _write(items)
    return item


def remove_connection_access(connection_id: str):
    _write([x for x in _read() if x.get("connection_id") != connection_id])


def grant_new_connection_to_user(connection_id: str, user: dict):
    if str(user.get("role", "")).lower() == "admin":
        return set_connection_access(connection_id, "all", [], str(user.get("id")))
    return set_connection_access(
        connection_id, "restricted", [str(user.get("id"))], str(user.get("id"))
    )


def public_access_record(connection_id: str):
    return get_connection_access(connection_id)
