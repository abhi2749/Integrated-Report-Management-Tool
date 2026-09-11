"""Unified execution preparation contract for the reporting pipeline."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

from query_model import QueryDefinition
from query_planner import ExecutionPlan, plan_query
from query_contract import canonical_query_from_payload


@dataclass(frozen=True)
class PreparedExecution:
    """Immutable canonical query + plan pair shared by execution layers."""

    query: QueryDefinition
    plan: ExecutionPlan
    payload: dict[str, Any]
    fingerprint: str


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prepare_execution(
    payload: dict[str, Any] | QueryDefinition,
    *,
    planner: Callable[[QueryDefinition], ExecutionPlan] = plan_query,
) -> PreparedExecution:
    """Canonicalize and plan exactly once for a single execution request."""
    query = payload if isinstance(payload, QueryDefinition) else canonical_query_from_payload(payload)
    normalized = query.normalized()
    plan = planner(query)
    return PreparedExecution(
        query=query,
        plan=plan,
        payload=normalized,
        fingerprint=_fingerprint(normalized),
    )
