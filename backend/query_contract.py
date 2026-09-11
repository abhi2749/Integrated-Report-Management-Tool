"""Canonical query contract adapter.

Keeps the public legacy /report/query payload compatible while making
QueryDefinition the internal contract used by planning and execution jobs.
"""
from __future__ import annotations

from typing import Any

from query_model import QueryDefinition


def canonical_query_from_payload(payload: dict[str, Any]) -> QueryDefinition:
    """Normalize legacy and canonical query payloads into QueryDefinition."""
    if not isinstance(payload, dict):
        raise ValueError("Report query payload must be a JSON object")
    data = dict(payload)
    if "calculations" not in data and "calculated_columns" in data:
        data["calculations"] = data.get("calculated_columns")
    return QueryDefinition.model_validate(data)


def canonical_query_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the stable execution-layer representation of a query."""
    return canonical_query_from_payload(payload).normalized()
