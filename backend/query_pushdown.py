from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# This is the execution capability contract for the current connector paths.
# It deliberately describes what the connectors actually implement today;
# capabilities must not be inferred merely because an operation exists in the
# canonical query model.
CONNECTOR_CAPABILITIES: dict[str, dict[str, Any]] = {
    "mysql": {
        "filter_operators": {
            "=", "!=", ">", "<", ">=", "<=", "CONTAINS", "STARTS_WITH",
            "ENDS_WITH", "NOT_CONTAINS", "IS_NULL", "IS_NOT_NULL", "IN",
            "NOT_IN", "BETWEEN",
        },
        "projection": True,
        "sort": True,
        "limit": True,
        "group_by": True,
        "aggregations": True,
        "streaming": True,
    },
    "mongodb": {
        "filter_operators": {
            "=", "!=", ">", "<", ">=", "<=", "CONTAINS", "STARTS_WITH",
            "ENDS_WITH", "NOT_CONTAINS", "IS_NULL", "IS_NOT_NULL", "IN",
            "NOT_IN", "BETWEEN",
        },
        "projection": True,
        "sort": True,
        "limit": True,
        "group_by": True,
        "aggregations": True,
        "streaming": True,
    },
    "clickhouse": {
        "filter_operators": {
            "=", "!=", ">", "<", ">=", "<=", "CONTAINS", "STARTS_WITH",
            "ENDS_WITH", "NOT_CONTAINS", "IS_NULL", "IS_NOT_NULL", "IN",
            "NOT_IN", "BETWEEN",
        },
        "projection": True,
        "sort": True,
        "limit": True,
        "group_by": True,
        "aggregations": True,
        "streaming": True,
    },
    # Imported datasets are executed by the application, not a database
    # connector, so no database pushdown is claimed for them.
    "imported": {
        "filter_operators": set(),
        "projection": False,
        "sort": False,
        "limit": False,
        "group_by": False,
        "aggregations": False,
        "streaming": True,
    },
}

_GENERIC_CAPABILITIES = {
    "filter_operators": {
        "=", "!=", ">", "<", ">=", "<=", "CONTAINS", "STARTS_WITH",
        "ENDS_WITH", "NOT_CONTAINS", "IS_NULL", "IS_NOT_NULL", "IN",
        "NOT_IN", "BETWEEN",
    },
    "projection": True,
    "sort": True,
    "limit": True,
    "group_by": True,
    "aggregations": True,
    "streaming": True,
}


@dataclass
class PushdownPlan:
    """Connector-aware, descriptive pushdown plan.

    The planner does not execute arbitrary SQL. It records which operations
    the current connector execution paths can actually push down and which
    operations remain application-side. It never imposes a data-size ceiling.
    """
    filters: list[dict[str, Any]] = field(default_factory=list)
    selected_columns: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    aggregations: list[dict[str, Any]] = field(default_factory=list)
    sort: list[dict[str, str]] = field(default_factory=list)
    pushed_filters: int = 0
    application_filters: int = 0
    pushed_sorts: int = 0
    application_sorts: int = 0
    projection_pushdown: bool = False
    limit_pushdown: bool = False
    group_by_pushdown: bool = False
    aggregation_pushdown: bool = False
    connector_capabilities: dict[str, dict[str, Any]] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        database_pushdown = (
            self.pushed_filters > 0
            or self.pushed_sorts > 0
            or self.projection_pushdown
            or self.limit_pushdown
            or self.group_by_pushdown
            or self.aggregation_pushdown
        )
        application_operations: list[str] = []
        if self.application_filters:
            application_operations.append("filters")
        if self.application_sorts:
            application_operations.append("sort")
        if self.group_by and not self.group_by_pushdown:
            application_operations.append("group_by")
        if self.aggregations and not self.aggregation_pushdown:
            application_operations.append("aggregations")

        return {
            "selected_columns": self.selected_columns,
            "filters": len(self.filters),
            "pushed_filters": self.pushed_filters,
            "application_filters": self.application_filters,
            "sort_fields": len(self.sort),
            "pushed_sorts": self.pushed_sorts,
            "application_sorts": self.application_sorts,
            "group_by": len(self.group_by),
            "aggregations": len(self.aggregations),
            "projection_pushdown": self.projection_pushdown,
            "limit_pushdown": self.limit_pushdown,
            "group_by_pushdown": self.group_by_pushdown,
            "aggregation_pushdown": self.aggregation_pushdown,
            "connector_capabilities": self.connector_capabilities,
            "application_operations": application_operations,
            "mode": "database_pushdown" if database_pushdown else "application_execution",
        }


SAFE_OPERATORS = set(_GENERIC_CAPABILITIES["filter_operators"])

JOIN_CAPABILITIES: dict[str, dict[str, Any]] = {
    "mysql": {"native": True, "join_types": {"INNER", "LEFT", "RIGHT", "FULL"}, "cross_database": True},
    "mongodb": {"native": False, "join_types": set(), "cross_database": False},
    "clickhouse": {"native": False, "join_types": set(), "cross_database": False},
    "imported": {"native": False, "join_types": set(), "cross_database": False},
}

def join_capabilities(source_type: str | None = None) -> dict[str, Any]:
    key = str(source_type or "").strip().lower(); caps = JOIN_CAPABILITIES.get(key, {"native": False, "join_types": set(), "cross_database": False})
    return {"native": bool(caps["native"]), "join_types": sorted(caps["join_types"]), "cross_database": bool(caps["cross_database"])}

def can_pushdown_join(left: dict[str, Any], right: dict[str, Any], join: dict[str, Any]) -> tuple[bool, str]:
    lt=str(left.get("source_type") or "").strip().lower(); rt=str(right.get("source_type") or "").strip().lower()
    if lt != rt: return False, "different_connector_types"
    caps=JOIN_CAPABILITIES.get(lt)
    if not caps or not caps["native"]: return False, "connector_join_not_supported"
    jt=str(join.get("join_type","INNER")).strip().upper()
    if jt not in caps["join_types"]: return False, "join_type_not_supported"
    lc,rc=left.get("connection_id"),right.get("connection_id")
    if lc and rc:
        if lc != rc: return False, "different_connections"
    else:
        li=(lt,str(left.get("host") or "").lower(),int(left.get("port") or 0)); ri=(rt,str(right.get("host") or "").lower(),int(right.get("port") or 0))
        if li != ri: return False, "different_connections"
    if lt == "mongodb" and str(left.get("database") or "") != str(right.get("database") or ""): return False, "mongodb_cross_database_lookup_not_supported"
    if not left.get("table") or not right.get("table"): return False, "missing_join_table"
    if not join.get("left_column") or not join.get("right_column"): return False, "missing_join_column"
    return True, "native_join_candidate"



def _capabilities(source_type: str | None) -> dict[str, Any]:
    key = str(source_type or "").strip().lower()
    return CONNECTOR_CAPABILITIES.get(key, _GENERIC_CAPABILITIES)


def connector_capabilities(source_type: str | None = None) -> dict[str, Any]:
    """Return a serializable snapshot of the current connector contract."""
    caps = _capabilities(source_type)
    return {
        "filter_operators": sorted(caps["filter_operators"]),
        "projection": bool(caps["projection"]),
        "sort": bool(caps["sort"]),
        "limit": bool(caps["limit"]),
        "group_by": bool(caps["group_by"]),
        "aggregations": bool(caps["aggregations"]),
        "streaming": bool(caps["streaming"]),
    }


def build_plan(
    *,
    columns: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    group_by: list[str] | None = None,
    aggregations: list[dict[str, Any]] | None = None,
    sort: list[dict[str, str]] | None = None,
    datasets: list[dict[str, Any]] | None = None,
    limit: int = 0,
    allow_limit_pushdown: bool = True,
) -> PushdownPlan:
    dataset_list = list(datasets or [])
    plan = PushdownPlan(
        selected_columns=list(columns or []),
        filters=list(filters or []),
        group_by=list(group_by or []),
        aggregations=list(aggregations or []),
        sort=list(sort or []),
    )

    source_types = sorted({str(item.get("source_type") or "").strip().lower() for item in dataset_list if item.get("source_type")})
    if source_types:
        plan.connector_capabilities = {source: connector_capabilities(source) for source in source_types}
    else:
        plan.connector_capabilities = {"generic": connector_capabilities(None)}

    # Filter pushdown is counted per operation only when the target source can
    # execute that operator. Unqualified filters retain the generic contract.
    for item in plan.filters:
        operator = str(item.get("operator", "")).upper()
        field = str(item.get("field", "")).strip()
        if operator not in SAFE_OPERATORS or not field:
            plan.application_filters += 1
            continue
        source = None
        if "." in field and dataset_list:
            dataset_id, _ = field.rsplit(".", 1)
            match = next((d for d in dataset_list if str(d.get("id")) == dataset_id), None)
            source = match.get("source_type") if match else None
        caps = _capabilities(source) if source is not None else _capabilities(None)
        if operator in caps["filter_operators"]:
            plan.pushed_filters += 1
        else:
            plan.application_filters += 1

    # Sorts are source-side operations on the current MySQL/MongoDB/ClickHouse
    # streaming paths. A sort spanning multiple datasets remains application-side.
    for item in plan.sort:
        field = str(item.get("field", "")).strip()
        direction = str(item.get("direction", "ASC")).upper()
        if not field or direction not in {"ASC", "DESC"}:
            plan.application_sorts += 1
            continue
        source = None
        if "." in field and dataset_list:
            dataset_id, _ = field.rsplit(".", 1)
            match = next((d for d in dataset_list if str(d.get("id")) == dataset_id), None)
            source = match.get("source_type") if match else None
        caps = _capabilities(source) if source is not None else _capabilities(None)
        if caps["sort"]:
            plan.pushed_sorts += 1
        else:
            plan.application_sorts += 1

    plan.projection_pushdown = bool(plan.selected_columns) and all(
        _capabilities(item.get("source_type"))["projection"] for item in dataset_list
    ) if dataset_list else bool(plan.selected_columns)

    plan.limit_pushdown = bool(limit and int(limit) > 0 and allow_limit_pushdown and dataset_list and all(
        _capabilities(item.get("source_type"))["limit"] for item in dataset_list
    ))

    # MySQL, MongoDB and ClickHouse all have native grouping/aggregation
    # primitives. The planner advertises these capabilities for the connector
    # contract; execution paths may still fall back to the application engine
    # when a particular query shape cannot be safely translated.
    single_source = len(dataset_list) == 1
    plan.group_by_pushdown = bool(plan.group_by) and single_source and _capabilities(dataset_list[0].get("source_type"))["group_by"]
    plan.aggregation_pushdown = bool(plan.aggregations) and single_source and _capabilities(dataset_list[0].get("source_type"))["aggregations"]

    return plan
