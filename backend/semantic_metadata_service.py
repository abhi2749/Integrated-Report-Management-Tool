"""Datasource-neutral semantic metadata discovery and consistency checks."""
from __future__ import annotations

from typing import Any

from semantic_model import SemanticDataset, SemanticDimension, SemanticMeasure, SemanticModel


_NUMERIC_TYPES = {"integer", "decimal", "number", "float", "double", "numeric", "int", "bigint"}
_DATE_TYPES = {"date", "datetime", "timestamp"}
_BOOLEAN_TYPES = {"boolean", "bool"}


def normalize_data_type(value: Any) -> str:
    """Map connector-specific type labels into the semantic type vocabulary."""
    raw = str(value or "unknown").strip().lower()
    if raw in _NUMERIC_TYPES:
        return "integer" if raw in {"integer", "int", "bigint"} else "decimal"
    if raw in _DATE_TYPES:
        return "datetime" if raw in {"datetime", "timestamp"} else "date"
    if raw in _BOOLEAN_TYPES:
        return "boolean"
    if raw in {"string", "text", "varchar", "char", "object"}:
        return "string"
    if raw == "time":
        return "time"
    return "unknown"


def _column_name(column: Any) -> str:
    if isinstance(column, str):
        return column.strip()
    if isinstance(column, dict):
        return str(
            column.get("name")
            or column.get("field")
            or column.get("column")
            or ""
        ).strip()
    return ""


def _column_type(column: Any) -> str:
    if not isinstance(column, dict):
        return "unknown"
    return normalize_data_type(
        column.get("data_type") or column.get("dataType") or column.get("type")
    )


def _role(column: Any, data_type: str) -> str:
    if isinstance(column, dict):
        explicit = str(column.get("role") or "").strip().lower()
        if explicit in {"dimension", "measure", "attribute"}:
            return explicit
    return "measure" if data_type in {"integer", "decimal"} else "dimension"


def build_semantic_model(dataset: dict[str, Any]) -> SemanticModel:
    """Build metadata only; this function never reads or materializes dataset rows."""
    dataset_id = str(dataset.get("id") or "").strip()
    if not dataset_id:
        raise ValueError("Dataset id is required.")

    semantic_id = f"semantic_{dataset_id}"
    dimensions: list[SemanticDimension] = []
    measures: list[SemanticMeasure] = []

    for column in dataset.get("columns") or []:
        physical = _column_name(column)
        if not physical:
            continue
        data_type = _column_type(column)
        role = _role(column, data_type)
        display_name = column.get("display_name") if isinstance(column, dict) else None
        description = column.get("description") if isinstance(column, dict) else None
        nullable = column.get("nullable") if isinstance(column, dict) else None
        hierarchy = column.get("hierarchy") if isinstance(column, dict) else []
        if not isinstance(hierarchy, list):
            hierarchy = []

        common = {
            "name": str(column.get("name") if isinstance(column, dict) and column.get("name") else physical),
            "physical_field": physical,
            "data_type": data_type,
            "display_name": display_name,
            "description": description,
            "nullable": nullable if isinstance(nullable, bool) else None,
        }
        if role == "measure":
            default_aggregation = str(
                column.get("default_aggregation") if isinstance(column, dict) else ""
            ).upper() or "SUM"
            if default_aggregation not in {"SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT"}:
                default_aggregation = "SUM"
            measures.append(SemanticMeasure(**common, default_aggregation=default_aggregation))
        else:
            dimensions.append(SemanticDimension(**common, hierarchy=[str(item) for item in hierarchy]))

    semantic_dataset = SemanticDataset(
        id=semantic_id,
        name=str(dataset.get("name") or dataset.get("object_name") or dataset_id),
        physical_dataset_id=dataset_id,
        dimensions=dimensions,
        measures=measures,
        calculated_measures=[],
    )
    return SemanticModel(version=1, datasets=[semantic_dataset], relationships=[])


def consistency_report(dataset: dict[str, Any], model: SemanticModel) -> dict[str, Any]:
    """Compare physical registry columns with semantic physical-field mappings."""
    physical = {_column_name(item) for item in dataset.get("columns") or [] if _column_name(item)}
    semantic = {
        field.physical_field
        for item in model.datasets
        for field in [*item.dimensions, *item.measures]
    }
    duplicate_physical = []
    seen: set[str] = set()
    for item in dataset.get("columns") or []:
        name = _column_name(item)
        if not name:
            continue
        if name in seen and name not in duplicate_physical:
            duplicate_physical.append(name)
        seen.add(name)
    missing = sorted(physical - semantic)
    stale = sorted(semantic - physical)
    return {
        "consistent": not missing and not stale and not duplicate_physical,
        "physical_column_count": len(physical),
        "semantic_field_count": len(semantic),
        "missing_semantic_fields": missing,
        "stale_semantic_fields": stale,
        "duplicate_physical_fields": duplicate_physical,
    }


def dataset_semantic_payload(dataset: dict[str, Any], model: SemanticModel | None = None) -> dict[str, Any]:
    model = model or build_semantic_model(dataset)
    semantic_dataset = model.datasets[0] if model.datasets else None
    return {
        "id": dataset.get("id"),
        "name": dataset.get("name"),
        "source_type": dataset.get("source_type"),
        "connection_id": dataset.get("connection_id"),
        "database": dataset.get("database"),
        "object_name": dataset.get("object_name"),
        "object_type": dataset.get("object_type"),
        "column_count": len(dataset.get("columns") or []),
        "semantic_dataset_id": semantic_dataset.id if semantic_dataset else None,
        "semantic": semantic_dataset.model_dump(mode="json") if semantic_dataset else None,
        "semantic_model": model.model_dump(mode="json"),
        "consistency": consistency_report(dataset, model),
    }
