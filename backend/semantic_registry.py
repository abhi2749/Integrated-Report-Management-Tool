"""Persistent registry for reusable semantic models.

Semantic models contain metadata only and are kept separate from physical
reporting datasets and execution results.
"""
from __future__ import annotations

from typing import Any

from config import METADATA_DB_FILE
from metadata_repository import create_metadata_repository
from semantic_model import SemanticModel

from pathlib import Path

from config import DATA_DIR

REGISTRY_DIR = DATA_DIR
REGISTRY_FILE = REGISTRY_DIR / "semantic_models.json"
REPOSITORY = create_metadata_repository(
    REGISTRY_FILE, collection="semantic_models", db_path=METADATA_DB_FILE
)


def list_semantic_models() -> list[dict[str, Any]]:
    return REPOSITORY.read()


def get_semantic_model(model_id: str) -> SemanticModel | None:
    item = next((item for item in REPOSITORY.read() if item.get("id") == model_id), None)
    return SemanticModel.model_validate(item["model"]) if item and item.get("model") else None


def save_semantic_model(model_id: str, model: SemanticModel) -> dict[str, Any]:
    items = REPOSITORY.read()
    payload = {"id": str(model_id).strip(), "model": model.model_dump(mode="json")}
    if not payload["id"]:
        raise ValueError("Semantic model id is required.")
    for index, item in enumerate(items):
        if item.get("id") == payload["id"]:
            items[index] = payload
            REPOSITORY.write(items)
            return payload
    items.append(payload)
    REPOSITORY.write(items)
    return payload


def delete_semantic_model(model_id: str) -> bool:
    items = REPOSITORY.read()
    updated = [item for item in items if item.get("id") != model_id]
    if len(updated) == len(items):
        return False
    REPOSITORY.write(updated)
    return True


def get_semantic_model_for_dataset(semantic_dataset_id: str) -> SemanticModel | None:
    """Find the persisted model containing a semantic dataset id."""
    target = str(semantic_dataset_id).strip()
    if not target:
        return None
    for item in REPOSITORY.read():
        model_data = item.get("model") if isinstance(item, dict) else None
        if not model_data:
            continue
        model = SemanticModel.model_validate(model_data)
        if any(dataset.id == target for dataset in model.datasets):
            return model
    return None
