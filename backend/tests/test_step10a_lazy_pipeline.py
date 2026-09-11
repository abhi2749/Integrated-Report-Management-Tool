import database


def test_complex_stream_pipeline_is_lazy(monkeypatch):
    left_rows = ({"a.id": i, "a.value": i % 3} for i in range(100_000))
    right_rows = ({"b.id": i, "b.label": f"row-{i}"} for i in range(100_000))
    rows_by_id = {"a": left_rows, "b": right_rows}
    monkeypatch.setattr(database, "_resolve_report_dataset", lambda item: dict(item))
    monkeypatch.setattr(
        database,
        "_stream_dataset",
        lambda dataset, **kwargs: rows_by_id[dataset["id"]],
    )

    result = database._execute_report_query_unbounded(
        datasets=[
            {"id": "a", "source_type": "imported"},
            {"id": "b", "source_type": "imported"},
        ],
        joins=[{
            "left_dataset": "a",
            "right_dataset": "b",
            "left_column": "id",
            "right_column": "id",
            "join_type": "INNER",
        }],
        columns=[{"field": "a.id"}, {"field": "b.label"}],
        filters=[{"field": "a.value", "operator": "=", "value": 1}],
        sorts=[{"field": "a.id", "direction": "DESC"}],
        group_by=[],
        aggregations=[],
        calculated_columns=[],
        limit=25,
        stream=True,
    )

    assert result["rows"] == []
    assert not isinstance(result["streaming_rows"], list)
    output = list(result["streaming_rows"])
    assert len(output) == 25
    assert output[0]["a.id"] == 99_997
    assert output[-1]["a.id"] == 99_925


def test_imported_dataset_has_streaming_reader():
    import import_service

    assert hasattr(import_service, "iter_import_rows")
