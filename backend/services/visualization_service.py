from __future__ import annotations

from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal
from typing import Any
import math

SUPPORTED_VISUALIZATIONS = {
    "table",
    "data-grid",
    "kpi",
    "bar",
    "pie",
    "line",
    "histogram",
}

NUMERIC_TYPES = {
    "int", "integer", "float", "double", "decimal", "number",
    "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64",
    "float32", "float64", "long", "short", "byte",
}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def _number(value: Any) -> float | int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            number = float(text)
        except (TypeError, ValueError):
            return None
    if not math.isfinite(number):
        return None
    return number


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, (float, Decimal)):
        return "number"
    if isinstance(value, (datetime, date)):
        return "datetime"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def _is_numeric_profile(profile: dict[str, Any]) -> bool:
    data_type = str(profile.get("data_type") or "").lower()
    if any(token in data_type for token in NUMERIC_TYPES):
        return True
    return profile.get("inferred_type") in {"integer", "number"}


def profile_fields(
    columns: list[str],
    rows: list[dict[str, Any]],
    supplied_profiles: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    supplied = {
        str(item.get("name")): item
        for item in (supplied_profiles or [])
        if isinstance(item, dict) and item.get("name")
    }
    profiles = []
    for column in columns:
        values = [
            row.get(column)
            for row in rows
            if isinstance(row, dict) and row.get(column) is not None
        ]
        inferred = _type_name(values[0]) if values else "unknown"
        numeric_values = [_number(value) for value in values]
        numeric_values = [value for value in numeric_values if value is not None]
        profile = dict(supplied.get(column) or {})
        profile.update({
            "name": column,
            "inferred_type": inferred,
            "is_numeric": bool(numeric_values)
            and len(numeric_values) >= max(1, min(len(values), 3)),
            "has_values": bool(values),
            "null_count": len(rows) - len(values),
        })
        if numeric_values:
            profile["numeric_min"] = min(numeric_values)
            profile["numeric_max"] = max(numeric_values)
        profile["is_numeric"] = bool(profile.get("is_numeric") or _is_numeric_profile(profile))
        profiles.append(profile)
    return profiles


def visualization_fields(
    columns: list[str],
    rows: list[dict[str, Any]],
    supplied_profiles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profiles = profile_fields(columns, rows, supplied_profiles)
    numeric = [item["name"] for item in profiles if item.get("is_numeric")]
    categorical = [item["name"] for item in profiles if not item.get("is_numeric")]
    return {
        "success": True,
        "columns": columns,
        "profiles": profiles,
        "numeric_fields": numeric,
        "categorical_fields": categorical,
        "chart_fields": {
            "category": columns,
            "value": numeric or columns,
        },
    }


def _aggregate(values: list[Any], function: str) -> float | int | None:
    function = str(function or "SUM").upper()
    if function == "COUNT":
        return sum(1 for value in values if value is not None)
    numbers = [_number(value) for value in values]
    numbers = [value for value in numbers if value is not None]
    if function == "SUM":
        return sum(numbers) if numbers else 0
    if function == "AVG":
        return (sum(numbers) / len(numbers)) if numbers else None
    if function == "MIN":
        return min(numbers) if numbers else None
    if function == "MAX":
        return max(numbers) if numbers else None
    raise ValueError(f"Unsupported visualization aggregation: {function}")


def _parse_ordered_value(value: Any) -> tuple[int, Any]:
    """Return a stable sortable key for line-chart category values.

    Priority:
    1. Native date/datetime values.
    2. Numeric values.
    3. ISO-like date/datetime strings.
    4. General strings using case-insensitive natural text ordering.

    The first element keeps different value types safely comparable.
    """
    if isinstance(value, datetime):
        return (0, value)
    if isinstance(value, date):
        return (0, datetime.combine(value, datetime.min.time()))

    numeric = _number(value)
    if numeric is not None and not isinstance(value, bool):
        text = str(value).strip()
        if text:
            return (1, numeric)

    text = _safe_text(value).strip()
    if text:
        # Handle common ISO date/datetime strings without changing the
        # original label returned to the frontend.
        candidate = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
            return (0, parsed)
        except ValueError:
            try:
                parsed_date = date.fromisoformat(text)
                return (0, datetime.combine(parsed_date, datetime.min.time()))
            except ValueError:
                pass

    return (2, text.casefold())


def _sort_visualization_data(
    data: list[dict[str, Any]],
    visualization: str,
    direction: str,
) -> None:
    """Sort chart-ready data using semantics appropriate to the chart.

    Bar and pie charts are magnitude/category comparisons, so their explicit
    sort direction applies to the aggregated numeric value.

    Line charts represent ordered progression. Their explicit sort direction
    therefore applies to the category/x-axis value, which is essential for
    dates and timestamps. This prevents a line from connecting points in an
    incorrect temporal order merely because their Y values differ.
    """
    reverse = direction == "DESC"

    if visualization == "line":
        data.sort(
            key=lambda item: _parse_ordered_value(item.get("category")),
            reverse=reverse,
        )
        return

    data.sort(
        key=lambda item: (
            _number(item.get("value")) is None,
            _number(item.get("value")) if _number(item.get("value")) is not None else 0,
        ),
        reverse=reverse,
    )


def build_visualization_data(
    rows: list[dict[str, Any]],
    visualization: str,
    category_field: str | None = None,
    value_field: str | None = None,
    aggregation: str = "SUM",
    limit: int = 20,
    bins: int = 6,
    sort_direction: str | None = None,
) -> dict[str, Any]:
    visualization = str(visualization or "table").lower().strip()
    if visualization not in SUPPORTED_VISUALIZATIONS:
        raise ValueError(
            f"Unsupported visualization '{visualization}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_VISUALIZATIONS))}"
        )

    safe_rows = [dict(row) for row in rows if isinstance(row, dict)]
    columns = list(OrderedDict.fromkeys(key for row in safe_rows for key in row.keys()))

    if visualization in {"table", "data-grid"}:
        return {
            "visualization": visualization,
            "columns": columns,
            "data": [{key: _json_safe(row.get(key)) for key in columns} for row in safe_rows],
            "row_count": len(safe_rows),
        }

    if visualization == "histogram":
        if not value_field:
            raise ValueError("Histogram requires value_field.")
        values = []
        row_count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_count += 1
            number = _number(row.get(value_field))
            if number is not None:
                values.append(number)
        bin_count = max(1, min(int(bins), 100))
        if not values:
            return {"visualization": visualization, "value_field": value_field, "data": [], "row_count": row_count, "bins": bin_count, "numeric_value_count": 0, "streamed": True}
        minimum, maximum = min(values), max(values)
        span = maximum - minimum
        step = 1 if span == 0 else span / bin_count
        data = []
        for index in range(bin_count):
            start = minimum + index * step
            end = maximum if index == bin_count - 1 else minimum + (index + 1) * step
            data.append({"label": _safe_text(minimum) if span == 0 else f"{start:.4g}–{end:.4g}", "value": 0, "start": start, "end": end})
        for number in values:
            index = 0 if span == 0 else int((number - minimum) / step)
            index = max(0, min(index, bin_count - 1))
            data[index]["value"] += 1
        return {"visualization": visualization, "value_field": value_field, "data": data, "row_count": row_count, "numeric_value_count": len(values), "bins": bin_count, "streamed": True}

    if visualization == "kpi":
        if not value_field:
            return {
                "visualization": visualization,
                "value_field": None,
                "aggregation": "COUNT",
                "value": len(safe_rows),
                "row_count": len(safe_rows),
            }
        if value_field not in columns:
            raise ValueError(f"Value field not found: {value_field}")
        value = _aggregate([row.get(value_field) for row in safe_rows], aggregation)
        return {
            "visualization": visualization,
            "value_field": value_field,
            "aggregation": str(aggregation or "SUM").upper(),
            "value": _json_safe(value),
            "row_count": len(safe_rows),
        }

    if visualization == "histogram":
        if not value_field:
            raise ValueError("Histogram requires value_field.")
        numbers = [_number(row.get(value_field)) for row in safe_rows]
        numbers = [value for value in numbers if value is not None]
        if not numbers:
            return {
                "visualization": visualization,
                "value_field": value_field,
                "data": [],
                "row_count": len(safe_rows),
                "bins": max(1, min(int(bins), 100)),
            }
        bin_count = max(1, min(int(bins), 100))
        minimum, maximum = min(numbers), max(numbers)
        span = maximum - minimum
        step = 1 if span == 0 else span / bin_count
        result = []
        for index in range(bin_count):
            start = minimum + index * step
            end = maximum if index == bin_count - 1 else minimum + (index + 1) * step
            result.append({
                "label": _safe_text(minimum) if span == 0 else f"{start:.4g}–{end:.4g}",
                "value": 0,
                "start": start,
                "end": end,
            })
        for number in numbers:
            index = 0 if span == 0 else int((number - minimum) / step)
            index = max(0, min(index, bin_count - 1))
            result[index]["value"] += 1
        return {
            "visualization": visualization,
            "value_field": value_field,
            "data": result,
            "row_count": len(safe_rows),
            "numeric_value_count": len(numbers),
            "bins": bin_count,
        }

    if not category_field or not value_field:
        raise ValueError(f"{visualization.title()} chart requires category_field and value_field.")
    if category_field not in columns:
        raise ValueError(f"Category field not found: {category_field}")
    if value_field not in columns:
        raise ValueError(f"Value field not found: {value_field}")

    grouped: OrderedDict[str, list[Any]] = OrderedDict()
    labels: dict[str, Any] = {}
    for row in safe_rows:
        raw_label = row.get(category_field)
        label = _safe_text(raw_label) or "(Blank)"
        grouped.setdefault(label, []).append(row.get(value_field))
        labels.setdefault(label, raw_label)

    data = []
    for key, values in grouped.items():
        value = _aggregate(values, aggregation)
        if value is None:
            continue
        data.append({
            "label": key,
            "category": _json_safe(labels[key]),
            "value": _json_safe(value),
        })

    if sort_direction:
        direction = str(sort_direction).upper()
        if direction not in {"ASC", "DESC"}:
            raise ValueError("sort_direction must be ASC or DESC.")
        _sort_visualization_data(data, visualization, direction)

    requested_limit = int(limit)
    max_items = len(data) if requested_limit <= 0 else max(1, requested_limit)
    data = data[:max_items]
    return {
        "visualization": visualization,
        "category_field": category_field,
        "value_field": value_field,
        "aggregation": str(aggregation or "SUM").upper(),
        "data": data,
        "row_count": len(safe_rows),
        "group_count": len(grouped),
        "returned_groups": len(data),
        "limit": max_items,
    }


def build_visualization_from_row_stream(
    rows,
    columns: list[str],
    visualization: str,
    category_field: str | None = None,
    value_field: str | None = None,
    aggregation: str = "SUM",
    limit: int = 20,
    sort_direction: str | None = None,
    bins: int = 6,
) -> dict[str, Any]:
    """Build dashboard aggregates from an iterator without loading all rows."""
    visualization = str(visualization or "table").lower().strip()
    columns = [str(column) for column in (columns or [])]
    if visualization in {"table", "data-grid"}:
        raise ValueError("This visualization requires a bounded result page.")
    if visualization == "kpi":
        count = 0
        non_null = 0
        total = 0.0
        minimum = None
        maximum = None
        function = str(aggregation or "COUNT").upper() if value_field else "COUNT"
        if function not in {"COUNT", "SUM", "AVG", "MIN", "MAX"}:
            raise ValueError(f"Unsupported visualization aggregation: {function}")
        for row in rows:
            if not isinstance(row, dict):
                continue
            count += 1
            value = row.get(value_field) if value_field else None
            number = _number(value)
            if value is not None:
                non_null += 1
            if number is not None:
                total += number
                minimum = number if minimum is None else min(minimum, number)
                maximum = number if maximum is None else max(maximum, number)
        if not value_field:
            value = count
        elif function == "COUNT":
            value = non_null
        elif function == "SUM":
            value = total if non_null else 0
        elif function == "AVG":
            value = total / non_null if non_null else None
        elif function == "MIN":
            value = minimum
        else:
            value = maximum
        return {
            "visualization": visualization,
            "value_field": value_field,
            "aggregation": function,
            "value": _json_safe(value),
            "row_count": count,
            "streamed": True,
        }

    if visualization == "histogram":
        if not value_field:
            raise ValueError("Histogram requires value_field.")
        if value_field not in columns:
            raise ValueError(f"Value field not found: {value_field}")
        values = []
        row_count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_count += 1
            number = _number(row.get(value_field))
            if number is not None:
                values.append(number)
        bin_count = max(1, min(int(bins), 100))
        if not values:
            return {"visualization": visualization, "value_field": value_field, "data": [], "row_count": row_count, "bins": bin_count, "numeric_value_count": 0, "streamed": True}
        minimum, maximum = min(values), max(values)
        span = maximum - minimum
        step = 1 if span == 0 else span / bin_count
        data = []
        for index in range(bin_count):
            start = minimum + index * step
            end = maximum if index == bin_count - 1 else minimum + (index + 1) * step
            data.append({"label": _safe_text(minimum) if span == 0 else f"{start:.4g}–{end:.4g}", "value": 0, "start": start, "end": end})
        for number in values:
            index = 0 if span == 0 else int((number - minimum) / step)
            index = max(0, min(index, bin_count - 1))
            data[index]["value"] += 1
        return {"visualization": visualization, "value_field": value_field, "data": data, "row_count": row_count, "numeric_value_count": len(values), "bins": bin_count, "streamed": True}

    if not category_field or not value_field:
        raise ValueError(f"{visualization.title()} chart requires category_field and value_field.")
    if category_field not in columns:
        raise ValueError(f"Category field not found: {category_field}")
    if value_field not in columns:
        raise ValueError(f"Value field not found: {value_field}")
    function = str(aggregation or "SUM").upper()
    if function not in {"COUNT", "SUM", "AVG", "MIN", "MAX"}:
        raise ValueError(f"Unsupported visualization aggregation: {function}")
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    row_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_count += 1
        raw_label = row.get(category_field)
        label = _safe_text(raw_label) or "(Blank)"
        state = grouped.setdefault(label, {"category": raw_label, "count": 0, "sum": 0.0, "min": None, "max": None, "non_null": 0})
        state["count"] += 1
        value = row.get(value_field)
        number = _number(value)
        if number is not None:
            state["non_null"] += 1
            state["sum"] += number
            state["min"] = number if state["min"] is None else min(state["min"], number)
            state["max"] = number if state["max"] is None else max(state["max"], number)
    data = []
    for label, state in grouped.items():
        if function == "COUNT":
            value = state["non_null"]
        elif function == "SUM":
            value = state["sum"] if state["non_null"] else 0
        elif function == "AVG":
            value = state["sum"] / state["non_null"] if state["non_null"] else None
        elif function == "MIN":
            value = state["min"]
        else:
            value = state["max"]
        if value is None:
            continue
        data.append({"label": label, "category": _json_safe(state["category"]), "value": _json_safe(value)})
    if sort_direction:
        direction = str(sort_direction).upper()
        if direction not in {"ASC", "DESC"}:
            raise ValueError("sort_direction must be ASC or DESC.")
        _sort_visualization_data(data, visualization, direction)
    requested_limit = int(limit)
    max_items = len(data) if requested_limit <= 0 else max(1, requested_limit)
    data = data[:max_items]
    return {
        "visualization": visualization,
        "category_field": category_field,
        "value_field": value_field,
        "aggregation": function,
        "data": data,
        "row_count": row_count,
        "group_count": len(grouped),
        "returned_groups": len(data),
        "limit": max_items,
        "streamed": True,
    }


def build_visualization_response(
    result: dict[str, Any],
    visualization: str,
    category_field: str | None = None,
    value_field: str | None = None,
    aggregation: str = "SUM",
    limit: int = 20,
    bins: int = 6,
    sort_direction: str | None = None,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("result must be an object returned by /report/query.")
    if result.get("success") is False:
        return {"success": False, "message": result.get("message", "Report query failed.")}
    rows = result.get("rows") or []
    columns = result.get("columns") or list(
        OrderedDict.fromkeys(
            key for row in rows if isinstance(row, dict) for key in row.keys()
        )
    )
    data = build_visualization_data(
        rows=rows,
        visualization=visualization,
        category_field=category_field,
        value_field=value_field,
        aggregation=aggregation,
        limit=limit,
        bins=bins,
        sort_direction=sort_direction,
    )
    return {
        "success": True,
        "source_result": {
            "dataset_count": result.get("dataset_count"),
            "join_count": result.get("join_count"),
            "total_rows": result.get("total_rows"),
            "returned_rows": result.get("returned_rows", len(rows)),
        },
        "columns": columns,
        **data,
    }
