from __future__ import annotations

from typing import Any


SAFE_OPERATORS = {
    "=",
    "!=",
    ">",
    "<",
    ">=",
    "<=",
    "CONTAINS",
    "STARTS_WITH",
    "ENDS_WITH",
    "NOT_CONTAINS",
    "IS_NULL",
    "IS_NOT_NULL",
    "IN",
    "NOT_IN",
    "BETWEEN",
}


def field_name(value: str) -> str:
    text = str(value or "").strip()
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    if not text or "\x00" in text:
        raise ValueError("Invalid MongoDB field name")
    return text


def _condition(field: str, operator: str, value: Any) -> dict[str, Any]:
    op = operator.upper().strip()
    field = field_name(field)

    if op not in SAFE_OPERATORS:
        raise ValueError(f"Unsupported MongoDB filter operator: {op}")

    if op == "IS_NULL":
        return {field: None}
    if op == "IS_NOT_NULL":
        return {field: {"$ne": None}}

    if op == "CONTAINS":
        return {field: {"$regex": str(value), "$options": "i"}}
    if op == "STARTS_WITH":
        return {field: {"$regex": "^" + str(value), "$options": "i"}}
    if op == "ENDS_WITH":
        return {field: {"$regex": str(value) + "$", "$options": "i"}}
    if op == "NOT_CONTAINS":
        return {field: {"$not": {"$regex": str(value), "$options": "i"}}}

    if op == "IN":
        values = list(value) if isinstance(value, (list, tuple, set)) else [
            item.strip() for item in str(value).split(",")
        ]
        return {field: {"$in": values}}

    if op == "NOT_IN":
        values = list(value) if isinstance(value, (list, tuple, set)) else [
            item.strip() for item in str(value).split(",")
        ]
        return {field: {"$nin": values}}

    if op == "BETWEEN":
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            parts = [item.strip() for item in str(value).split(",", 1)]
            if len(parts) != 2:
                raise ValueError("BETWEEN requires two values")
            value = parts
        return {field: {"$gte": value[0], "$lte": value[1]}}

    mongo_op = {
        "=": "$eq",
        "!=": "$ne",
        ">": "$gt",
        "<": "$lt",
        ">=": "$gte",
        "<=": "$lte",
    }[op]
    return {field: {mongo_op: value}}


def build_match(filters: list[dict[str, Any]]) -> dict[str, Any]:
    conditions = []
    for item in filters:
        conditions.append(
            _condition(
                item.get("field"),
                str(item.get("operator", "")),
                item.get("value"),
            )
        )
    if not conditions:
        return {}
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def build_project(columns: list[str]) -> dict[str, int]:
    projection = {}
    for column in columns:
        projection[field_name(column)] = 1
    return projection


def build_pipeline(
    *,
    filters: list[dict[str, Any]] | None = None,
    columns: list[str] | None = None,
    sort: list[dict[str, str]] | None = None,
    limit: int | None = None,
    group_by: list[str] | None = None,
    aggregations: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    pipeline: list[dict[str, Any]] = []

    match = build_match(filters or [])
    if match:
        pipeline.append({"$match": match})

    if group_by or aggregations:
        group_fields = [field_name(field) for field in (group_by or [])]
        group_id = {field: f"${field}" for field in group_fields}
        group_stage = {"_id": group_id if group_id else None}
        for item in aggregations or []:
            function = str(item.get("function", "")).upper().strip()
            field = field_name(item.get("field")) if str(item.get("field", "")).strip() != "*" else None
            alias = str(item.get("alias") or f"{function}_{field or 'all'}").strip()
            if function == "COUNT":
                group_stage[alias] = {"$sum": 1} if field is None else {"$sum": {"$cond": [{"$ne": [f"${field}", None]}, 1, 0]}}
            elif function in {"SUM", "AVG", "MIN", "MAX"} and field:
                group_stage[alias] = {"$" + function.lower(): f"${field}"}
            else:
                raise ValueError(f"Unsupported MongoDB aggregation: {function}")
        pipeline.append({"$group": group_stage})
        project = {}
        for field in group_fields:
            project[field] = f"$_id.{field}"
        project.pop("_id", None)
        if project:
            pipeline.append({"$project": {**project, **{str(item.get("alias") or f"{str(item.get('function','')).upper()}_{field_name(item.get('field')) if str(item.get('field','')).strip() != '*' else 'all'}"): 1 for item in aggregations or []}}})
    else:
        projection = build_project(columns or [])
        if projection:
            pipeline.append({"$project": projection})

    if sort:
        sort_stage = {}
        for item in sort:
            field = field_name(item.get("field"))
            direction = str(item.get("direction", "ASC")).upper()
            sort_stage[field] = -1 if direction == "DESC" else 1
        if sort_stage:
            pipeline.append({"$sort": sort_stage})

    if limit is not None and int(limit) > 0:
        pipeline.append({"$limit": int(limit)})

    return pipeline
