"""Regression coverage for the single-dataset Report Builder workflow."""


def test_single_dataset_report_execution(monkeypatch):
    import database

    dataset = {
        "id": "dataset_a",
        "source_type": "mysql",
        "host": "localhost",
        "port": 3306,
        "username": "tester",
        "password": "secret",
        "database": "amisp",
        "table": "feeder_data_monthly_log",
    }

    monkeypatch.setattr(database, "_resolve_report_dataset", lambda item: dict(item))
    monkeypatch.setattr(
        database,
        "execute_dataset",
        lambda item, **kwargs: [
            {"dataset_a.id": "1", "dataset_a.name": "A"},
            {"dataset_a.id": "2", "dataset_a.name": "B"},
        ],
    )

    result = database._execute_report_query_unbounded(
        datasets=[dataset],
        joins=[],
        columns=[
            {"field": "dataset_a.id", "alias": "dataset_a.id"},
            {"field": "dataset_a.name", "alias": "dataset_a.name"},
        ],
        filters=[],
        sorts=[],
        group_by=[],
        aggregations=[],
        calculated_columns=[],
        limit=1_048_576,
    )

    assert result["success"] is True
    assert result["dataset_count"] == 1
    assert result["join_count"] == 0
    assert result["total_rows"] == 2
    assert result["returned_rows"] == 2
    assert result["columns"] == ["dataset_a.id", "dataset_a.name"]


def test_aggregate_rows_is_one_pass_and_preserves_semantics():
    import database

    rows = iter([
        {"d.zone": "WEST", "d.value": 10},
        {"d.zone": "WEST", "d.value": 20},
        {"d.zone": "EAST", "d.value": None},
        {"d.zone": "EAST", "d.value": 5},
    ])
    result = database._aggregate_rows(
        rows,
        ["d.zone"],
        [
            {"function": "COUNT", "field": "d.value", "alias": "count_value"},
            {"function": "SUM", "field": "d.value", "alias": "sum_value"},
            {"function": "AVG", "field": "d.value", "alias": "avg_value"},
        ],
    )
    by_zone = {row["d.zone"]: row for row in result}
    assert by_zone["WEST"] == {"d.zone": "WEST", "count_value": 2, "sum_value": 30, "avg_value": 15}
    assert by_zone["EAST"] == {"d.zone": "EAST", "count_value": 1, "sum_value": 5, "avg_value": 5}
