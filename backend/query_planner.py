"""Connector-neutral query planning with deterministic JOIN-graph analysis."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, ClassVar

from query_model import QueryDefinition
from query_pushdown import build_plan, can_pushdown_join, join_capabilities


class ExecutionStrategy:
    """Stable planner strategy names consumed by execution layers."""

    SINGLE_SOURCE: ClassVar[str] = "SINGLE_SOURCE"
    MULTI_SOURCE: ClassVar[str] = "MULTI_SOURCE"
    SOURCE_JOIN: ClassVar[str] = "SOURCE_JOIN"
    CROSS_SOURCE_JOIN: ClassVar[str] = "CROSS_SOURCE_JOIN"
    REJECT: ClassVar[str] = "REJECT"


@dataclass
class JoinGraph:
    """Deterministic, validated view of datasets and JOIN relationships."""
    dataset_ids: list[str] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    execution_order: list[str] = field(default_factory=list)
    connected: bool = True
    disconnected_datasets: list[str] = field(default_factory=list)
    duplicate_edges: list[str] = field(default_factory=list)
    invalid_joins: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "dataset_ids": list(self.dataset_ids),
            "edges": [dict(edge) for edge in self.edges],
            "execution_order": list(self.execution_order),
            "connected": self.connected,
            "disconnected_datasets": list(self.disconnected_datasets),
            "duplicate_edges": list(self.duplicate_edges),
            "invalid_joins": list(self.invalid_joins),
        }


@dataclass
class ExecutionPlan:
    """A descriptive plan; it does not execute anything."""
    source_count: int = 0
    join_count: int = 0
    cross_source_join: bool = False
    join_strategy: str = "none"
    join_capabilities: list[dict[str, Any]] = field(default_factory=list)
    execution_strategy: str = ExecutionStrategy.REJECT
    pushdown: dict[str, Any] = field(default_factory=dict)
    stages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    join_graph: dict[str, Any] = field(default_factory=dict)
    source_plans: list[dict[str, Any]] = field(default_factory=list)
    requires_application_execution: bool = False

    def summary(self) -> dict[str, Any]:
        return {
            "source_count": self.source_count,
            "join_count": self.join_count,
            "cross_source_join": self.cross_source_join,
            "join_strategy": self.join_strategy,
            "join_capabilities": [dict(item) for item in self.join_capabilities],
            "execution_strategy": self.execution_strategy,
            "pushdown": self.pushdown,
            "stages": list(self.stages),
            "warnings": list(self.warnings),
            "join_graph": self.join_graph,
            "source_plans": [dict(item) for item in self.source_plans],
            "requires_application_execution": self.requires_application_execution,
        }


def _source_key(dataset: dict[str, Any]) -> str:
    if dataset.get("connection_id"):
        return f"connection:{dataset['connection_id']}"
    source = str(dataset.get("source_type") or "").strip().lower()
    host = str(dataset.get("host") or "").strip().lower()
    port = str(dataset.get("port") or "").strip()
    return ":".join(part for part in (source, host, port) if part)


def _execution_strategy(dataset_count: int, join_count: int, cross_source_join: bool, graph_valid: bool) -> str:
    if dataset_count == 0 or not graph_valid:
        return ExecutionStrategy.REJECT
    if join_count == 0:
        return ExecutionStrategy.SINGLE_SOURCE if dataset_count == 1 else ExecutionStrategy.MULTI_SOURCE
    return ExecutionStrategy.CROSS_SOURCE_JOIN if cross_source_join else ExecutionStrategy.SOURCE_JOIN


def _build_join_graph(datasets: list[dict[str, Any]], joins: list[dict[str, Any]]) -> JoinGraph:
    """Build a deterministic undirected connectivity graph without executing JOINs."""
    ids = [str(item.get("id", "")).strip() for item in datasets]
    id_set = set(ids)
    adjacency: dict[str, list[str]] = {item: [] for item in ids}
    edges: list[dict[str, Any]] = []
    invalid: list[str] = []
    duplicates: list[str] = []
    seen_edges: set[tuple[str, str, str, str, str]] = set()

    for index, join in enumerate(joins):
        left = str(join.get("left_dataset", "")).strip()
        right = str(join.get("right_dataset", "")).strip()
        left_col = str(join.get("left_column", "")).strip()
        right_col = str(join.get("right_column", "")).strip()
        join_type = str(join.get("join_type", "INNER")).strip().upper()
        label = f"join[{index}]"

        if left not in id_set or right not in id_set:
            invalid.append(f"{label}: references an unknown dataset ({left} -> {right}).")
            continue
        if left == right:
            invalid.append(f"{label}: self-join is not supported by the current execution model ({left}).")
            continue
        if not left_col or not right_col:
            invalid.append(f"{label}: both JOIN columns are required.")
            continue
        if join_type not in {"INNER", "LEFT", "RIGHT", "FULL"}:
            invalid.append(f"{label}: unsupported JOIN type {join_type}.")
            continue

        canonical = (left, right, left_col, right_col, join_type)
        reverse = (right, left, right_col, left_col, join_type)
        if canonical in seen_edges or reverse in seen_edges:
            duplicates.append(f"{label}: duplicate relationship {left} <-> {right}.")
            continue
        seen_edges.add(canonical)

        edge = {
            "left_dataset": left,
            "right_dataset": right,
            "left_column": left_col,
            "right_column": right_col,
            "join_type": join_type,
            "index": index,
        }
        edges.append(edge)
        adjacency[left].append(right)
        adjacency[right].append(left)

    if not ids:
        return JoinGraph(dataset_ids=[], edges=edges, execution_order=[], connected=False, invalid_joins=invalid, duplicate_edges=duplicates)

    # Deterministic traversal starts with the first dataset in the query payload.
    start = ids[0]
    visited: set[str] = {start}
    queue: deque[str] = deque([start])
    order: list[str] = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for neighbor in sorted(adjacency[current], key=ids.index):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    disconnected = [item for item in ids if item not in visited]
    connected = not disconnected and not invalid and not duplicates
    return JoinGraph(
        dataset_ids=ids,
        edges=edges,
        execution_order=order,
        connected=connected,
        disconnected_datasets=disconnected,
        duplicate_edges=duplicates,
        invalid_joins=invalid,
    )


def plan_query(query: QueryDefinition) -> ExecutionPlan:
    """Normalize the query and describe a safe execution strategy."""
    datasets = [item.model_dump(exclude_none=True) for item in query.datasets]
    joins = [item.model_dump() for item in query.joins]
    columns = [item.field for item in query.columns]
    filters = [item.model_dump() for item in query.filters]
    aggregations = [item.model_dump() for item in query.aggregations]
    sorts = [item.model_dump() for item in query.sorts]

    graph = _build_join_graph(datasets, joins)
    source_keys = {_source_key(item) for item in datasets if _source_key(item)}
    cross_source = len(source_keys) > 1 and bool(joins)

    pushdown = build_plan(
        columns=columns,
        filters=filters,
        group_by=query.group_by,
        aggregations=aggregations,
        sort=sorts,
        datasets=datasets,
        limit=query.limit,
        allow_limit_pushdown=(len(datasets) == 1 and not joins),
    )

    stages = ["source"]
    if filters:
        stages.append("filter")
    if joins:
        stages.append("join")
    if query.group_by:
        stages.append("group")
    if aggregations:
        stages.append("aggregate")
    if query.calculations:
        stages.append("calculate")
    if sorts:
        stages.append("sort")
    stages.append("limit")

    warnings: list[str] = []
    join_capability_summary: list[dict[str, Any]] = []
    if joins:
        by_id = {str(item.get("id")): item for item in datasets}
        for index, join in enumerate(joins):
            left = by_id.get(str(join.get("left_dataset"))); right = by_id.get(str(join.get("right_dataset")))
            if not left or not right: continue
            supported, reason = can_pushdown_join(left, right, join)
            source_type = str(left.get("source_type") or "").lower()
            join_capability_summary.append({"index": index, "source_type": source_type, "native_supported": supported, "reason": reason, "capabilities": join_capabilities(source_type)})
    native_candidates = [item for item in join_capability_summary if item["native_supported"]]
    if joins and native_candidates and len(native_candidates) == len(join_capability_summary) and not cross_source:
        strategy = "native_connector_join_candidate"
    elif cross_source:
        strategy = "application_join"
        warnings.append("JOIN spans multiple source connections or connector types; use the connector-neutral spill-aware JOIN engine internally.")
    elif joins:
        strategy = "application_join"
        warnings.append("At least one JOIN cannot be safely pushed to its connector; use the connector-neutral JOIN engine.")
    else:
        strategy = "none"

    # Connector-neutral per-source planning. This is descriptive only: no
    # source rows are fetched and credentials are never copied into the plan.
    source_plans: list[dict[str, Any]] = []
    by_id = {str(item.get("id")): item for item in datasets}
    for dataset in datasets:
        dataset_id = str(dataset.get("id"))
        source_type = str(dataset.get("source_type") or "").strip().lower() or "generic"
        local_filters = [
            item for item in filters
            if "." not in str(item.get("field", ""))
            or str(item.get("field", "")).split(".", 1)[0] == dataset_id
        ]
        local_sorts = [
            item for item in sorts
            if "." not in str(item.get("field", ""))
            or str(item.get("field", "")).split(".", 1)[0] == dataset_id
        ]
        local_plan = build_plan(
            columns=columns,
            filters=local_filters,
            group_by=[],
            aggregations=[],
            sort=local_sorts,
            datasets=[dataset],
            limit=query.limit if len(datasets) == 1 and not joins else 0,
            allow_limit_pushdown=(len(datasets) == 1 and not joins),
        ).summary()
        source_plans.append({
            "dataset_id": dataset_id,
            "source_type": source_type,
            "pushdown": local_plan,
            "join_pushdown_candidates": [],
        })

    for item in join_capability_summary:
        join = joins[item["index"]]
        candidate = {
            "join_index": item["index"],
            "right_dataset": str(join.get("right_dataset")),
            "eligible": bool(item["native_supported"]),
            "reason": item["reason"],
        }
        for source_plan in source_plans:
            if source_plan["dataset_id"] == str(join.get("left_dataset")):
                source_plan["join_pushdown_candidates"].append(candidate)

    if len(datasets) == 0:
        warnings.append("Query has no datasets.")
    if len(datasets) > 1 and not joins:
        warnings.append("Multiple datasets are present without a JOIN definition.")
    if graph.disconnected_datasets:
        warnings.append("JOIN graph contains disconnected datasets: " + ", ".join(graph.disconnected_datasets) + ".")
    warnings.extend(graph.invalid_joins)
    warnings.extend(graph.duplicate_edges)

    pushdown_summary = pushdown.summary()
    requires_application_execution = bool(
        (filters and pushdown_summary.get("application_filters", 0))
        or (sorts and pushdown_summary.get("application_sorts", 0))
        or (query.group_by and not pushdown_summary.get("group_by_pushdown", False))
        or (aggregations and not pushdown_summary.get("aggregation_pushdown", False))
        or (joins and (cross_source or any(
            not item.get("native_supported", False)
            for item in join_capability_summary
        )))
    )

    # Multiple independent sources without JOINs remain a supported legacy
    # MULTI_SOURCE classification; the graph constraint applies only when JOINs exist.
    graph_valid = graph.connected if joins else True
    execution_strategy = _execution_strategy(len(datasets), len(joins), cross_source, graph_valid)
    if not graph_valid:
        strategy = "reject"
        warnings.append("JOIN graph is invalid; execution should be rejected before source execution.")

    return ExecutionPlan(
        source_count=len(datasets),
        join_count=len(joins),
        cross_source_join=cross_source,
        join_strategy=strategy,
        execution_strategy=execution_strategy,
        pushdown=pushdown_summary,
        stages=stages,
        source_plans=source_plans,
        requires_application_execution=requires_application_execution,
        warnings=warnings,
        join_graph=graph.summary(),
        join_capabilities=join_capability_summary,
    )
