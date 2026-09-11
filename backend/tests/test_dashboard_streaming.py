from services.visualization_service import build_visualization_from_row_stream


def test_dashboard_bar_aggregates_stream_without_materializing_rows():
    rows = (row for row in [
        {"category": "A", "value": 10},
        {"category": "B", "value": 20},
        {"category": "A", "value": 5},
    ])
    result = build_visualization_from_row_stream(
        rows,
        ["category", "value"],
        visualization="bar",
        category_field="category",
        value_field="value",
        aggregation="SUM",
        limit=10,
    )
    assert result["streamed"] is True
    assert result["row_count"] == 3
    assert result["group_count"] == 2
    assert {item["label"]: item["value"] for item in result["data"]} == {"A": 15, "B": 20}


def test_dashboard_kpi_aggregates_stream():
    rows = ({"value": value} for value in [2, 4, None])
    result = build_visualization_from_row_stream(
        rows,
        ["value"],
        visualization="kpi",
        value_field="value",
        aggregation="AVG",
    )
    assert result["streamed"] is True
    assert result["row_count"] == 3
    assert result["value"] == 3


def test_dashboard_histogram_aggregates_stream():
    rows = ({"value": value} for value in [1, 2, 3, 4])
    result = build_visualization_from_row_stream(
        rows, ["value"], visualization="histogram", value_field="value", bins=2, limit=0
    )
    assert result["streamed"] is True
    assert result["row_count"] == 4
    assert result["numeric_value_count"] == 4
    assert sum(item["value"] for item in result["data"]) == 4


def test_dashboard_stream_limit_zero_is_unlimited():
    rows = ({"category": str(i), "value": i} for i in range(25))
    result = build_visualization_from_row_stream(
        rows, ["category", "value"], visualization="bar", category_field="category", value_field="value", limit=0
    )
    assert result["returned_groups"] == 25
    assert result["limit"] == 25
