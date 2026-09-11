from __future__ import annotations

from typing import Any


FILTER_OPERATORS = {
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


def quote_identifier(value: str) -> str:
    text = str(value)
    if not text or "\x00" in text:
        raise ValueError("Invalid MySQL identifier")
    return "`" + text.replace("`", "``") + "`"


def normalize_column(value: str) -> str:
    text = str(value or "").strip()
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    if not text:
        raise ValueError("Empty MySQL column name")
    return text


def build_projection(dataset_id: str, columns: list[str]) -> str:
    if not columns:
        return "*"

    expressions = []
    for column in columns:
        clean = normalize_column(column)
        expressions.append(
            f"{quote_identifier(clean)} AS "
            f"{quote_identifier(f'{dataset_id}.{clean}')}"
        )
    return ", ".join(expressions)


def _parameter_values(operator: str, value: Any) -> tuple[str, list[Any]]:
    op = operator.upper().strip()

    if op not in FILTER_OPERATORS:
        raise ValueError(f"Unsupported MySQL filter operator: {op}")

    if op == "IS_NULL":
        return "IS NULL", []
    if op == "IS_NOT_NULL":
        return "IS NOT NULL", []

    if op in {"IN", "NOT_IN"}:
        if isinstance(value, (list, tuple, set)):
            values = list(value)
        elif isinstance(value, str):
            values = [item.strip() for item in value.split(",")]
        else:
            values = [value]

        if not values:
            # Empty IN has a deterministic result and avoids invalid SQL.
            return ("1 = 0" if op == "IN" else "1 = 1"), []

        placeholders = ", ".join(["%s"] * len(values))
        return (
            f"{'NOT IN' if op == 'NOT_IN' else 'IN'} ({placeholders})",
            values,
        )

    if op == "BETWEEN":
        if isinstance(value, (list, tuple)) and len(value) == 2:
            low, high = value
        elif isinstance(value, str):
            parts = [item.strip() for item in value.split(",", 1)]
            if len(parts) != 2:
                raise ValueError("BETWEEN requires two values")
            low, high = parts
        else:
            raise ValueError("BETWEEN requires two values")
        return "BETWEEN %s AND %s", [low, high]

    if op == "CONTAINS":
        return "LIKE %s", [f"%{value}%"]
    if op == "STARTS_WITH":
        return "LIKE %s", [f"{value}%"]
    if op == "ENDS_WITH":
        return "LIKE %s", [f"%{value}"]
    if op == "NOT_CONTAINS":
        return "NOT LIKE %s", [f"%{value}%"]

    return f"{op} %s", [value]


def build_filter_clause(filters: list[dict[str, Any]]) -> tuple[str, list[Any], int]:
    clauses = []
    params: list[Any] = []
    pushed = 0

    for item in filters:
        field = normalize_column(item.get("field"))
        expression, values = _parameter_values(
            str(item.get("operator", "")).upper(),
            item.get("value"),
        )
        clauses.append(f"{quote_identifier(field)} {expression}")
        params.extend(values)
        pushed += 1

    if not clauses:
        return "", [], 0

    return " WHERE " + " AND ".join(f"({c})" for c in clauses), params, pushed


def build_qualified_filter_clause(filters: list[dict[str, Any]], qualifier: str) -> tuple[str, list[Any], int]:
    """Build a parameterized WHERE clause with an explicit table alias."""
    clauses = []
    params: list[Any] = []
    pushed = 0
    safe_qualifier = quote_identifier(qualifier)
    for item in filters or []:
        field = normalize_column(item.get("field"))
        expression, values = _parameter_values(str(item.get("operator", "")).upper(), item.get("value"))
        clauses.append(f"{safe_qualifier}.{quote_identifier(field)} {expression}")
        params.extend(values)
        pushed += 1
    if not clauses:
        return "", [], 0
    return " WHERE " + " AND ".join(f"({c})" for c in clauses), params, pushed


def build_group_aggregation(dataset_id: str, group_by: list[str] | None, aggregations: list[dict[str, Any]] | None):
    groups = [normalize_column(field) for field in (group_by or []) if str(field).strip()]
    select_parts = [f"{quote_identifier(field)} AS {quote_identifier(f'{dataset_id}.{field}')}" for field in groups]
    aliases = [f"{dataset_id}.{field}" for field in groups]
    allowed = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
    for item in aggregations or []:
        function = str(item.get("function", "")).upper().strip(); raw = str(item.get("field", "")).strip()
        field = normalize_column(raw) if raw and raw != "*" else ""
        if function not in allowed: raise ValueError(f"Unsupported MySQL aggregation: {function}")
        if function == "COUNT": expression = "COUNT(*)" if not field else f"COUNT({quote_identifier(field)})"
        elif field: expression = f"{function}({quote_identifier(field)})"
        else: raise ValueError(f"{function} requires a field")
        alias = str(item.get("alias") or f"{function}_{field or 'all'}").strip()
        select_parts.append(f"{expression} AS {quote_identifier(alias)}"); aliases.append(alias)
    return ", ".join(select_parts) or "*", groups, aliases
