"""Unified execution boundary for planned report queries.

The engine deliberately keeps connector implementations behind the existing
report executor. It owns only orchestration concerns: consuming one prepared
canonical query/plan, selecting the large-data streaming mode when safe, and
propagating cancellation into the execution layer.
"""
from __future__ import annotations

from typing import Any

from execution_contract import PreparedExecution


def _dump_model(item: Any, *, exclude_none: bool = False) -> dict[str, Any]:
    """Normalize Pydantic models and lightweight test/dict payloads."""
    if isinstance(item, dict):
        if exclude_none:
            return {key: value for key, value in item.items() if value is not None}
        return dict(item)
    model_dump = getattr(item, "model_dump", None)
    if callable(model_dump):
        return model_dump(exclude_none=exclude_none)
    dict_method = getattr(item, "dict", None)
    if callable(dict_method):
        return dict_method(exclude_none=exclude_none)
    raise TypeError("execution query items must be mappings or model objects")


def execute_prepared_execution(
    prepared: PreparedExecution,
    *,
    cancel_event: Any = None,
) -> dict[str, Any]:
    """Execute one already-prepared query without re-planning it.

    The underlying database layer remains connector-neutral and handles
    MySQL, MongoDB, ClickHouse, imported datasets, and cross-source JOINs.
    The execution boundary requests a lazy result for every query so the
    ExecutionManager can persist rows incrementally in ResultStore. Stateful
    operations such as aggregation may retain bounded group state, while joins
    and sorting use their spill-aware iterators.
    """
    # Accept the prepared-execution contract structurally.  This keeps the
    # execution boundary safe across test doubles and module reloads while
    # still rejecting arbitrary objects that cannot supply the canonical
    # query/plan pair required by the engine.
    if prepared is None or not hasattr(prepared, "plan") or not hasattr(prepared, "query"):
        raise TypeError("prepared must provide plan and query")

    from database import execute_report_query

    plan = prepared.plan
    query = prepared.query
    datasets = query.datasets
    # ResultStore is the result boundary for both simple and relational
    # executions. Keeping this flag unconditional prevents a query shape from
    # silently switching back to a full Python-list result.
    stream_result = True

    return execute_report_query(
        datasets=[_dump_model(item, exclude_none=True) for item in datasets],
        joins=[_dump_model(item) for item in query.joins],
        columns=[_dump_model(item) for item in query.columns],
        filters=[_dump_model(item) for item in query.filters],
        sorts=[_dump_model(item) for item in query.sorts],
        group_by=list(query.group_by),
        aggregations=[_dump_model(item) for item in query.aggregations],
        calculated_columns=[_dump_model(item) for item in query.calculations],
        limit=query.limit,
        stream=stream_result,
        cancel_event=cancel_event,
        execution_plan=plan,
    )
