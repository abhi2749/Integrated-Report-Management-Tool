from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from metadata_repository import create_metadata_repository
from config import METADATA_DB_FILE
import secrets

from config import DATA_DIR

REGISTRY_DIR = DATA_DIR
REGISTRY_FILE = REGISTRY_DIR / "datasets.json"
METADATA_REPOSITORY = create_metadata_repository(REGISTRY_FILE, collection="datasets", db_path=METADATA_DB_FILE)


def _ensure_file() -> None:
    METADATA_REPOSITORY.ensure()


def _read() -> list[dict[str, Any]]:
    return METADATA_REPOSITORY.read()


def _write(items: list[dict[str, Any]]) -> None:
    METADATA_REPOSITORY.write(items)


def _public(item: dict[str, Any]) -> dict[str, Any]:
    # Dataset registry deliberately contains no database credentials.
    return dict(item)


def list_datasets() -> list[dict[str, Any]]:
    return [_public(item) for item in _read()]


def get_dataset(dataset_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in _read() if item.get("id") == dataset_id),
        None,
    )


def create_dataset(data: dict[str, Any]) -> dict[str, Any]:
    items = _read()
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "id": data.get("id") or f"dataset_{secrets.token_hex(8)}",
        "name": str(data.get("name") or data.get("table") or data.get("object_name") or "Dataset").strip(),
        "connection_id": str(data["connection_id"]),
        "database": str(data["database"]).strip(),
        "object_name": str(data.get("object_name") or data.get("table") or data.get("collection") or "").strip(),
        "object_type": str(data.get("object_type") or "table").lower().strip(),
        "columns": data.get("columns") or [],
        "created_at": now,
        "updated_at": now,
    }

    if not item["object_name"]:
        raise ValueError("object_name/table/collection is required.")

    # One reporting dataset per connection + database + object.
    for existing in items:
        if (
            existing.get("connection_id") == item["connection_id"]
            and existing.get("database") == item["database"]
            and existing.get("object_name") == item["object_name"]
        ):
            return _public(existing)

    items.insert(0, item)
    _write(items)
    return _public(item)


def update_dataset(dataset_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    items = _read()

    for index, existing in enumerate(items):
        if existing.get("id") != dataset_id:
            continue

        allowed = {
            key: value
            for key, value in data.items()
            if key in {"name", "connection_id", "database", "object_name", "object_type", "columns"}
            and value is not None
        }

        updated = {
            **existing,
            **allowed,
            "id": dataset_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        items[index] = updated
        _write(items)
        return _public(updated)

    return None


def delete_dataset(dataset_id: str) -> bool:
    items = _read()
    updated = [item for item in items if item.get("id") != dataset_id]

    if len(updated) == len(items):
        return False

    _write(updated)
    return True
