from database import _join_stream, _project_join_stream


def test_join_stream_does_not_materialize_join_result():
    left = ({"a.id": i} for i in range(3))
    right = ({"b.id": i, "b.value": i * 10} for i in range(3))
    rows = _join_stream(
        left,
        right,
        {"left_dataset": "a", "left_column": "id", "right_dataset": "b", "right_column": "id"},
    )
    assert not isinstance(rows, list)
    assert list(rows) == [
        {"a.id": 0, "b.id": 0, "b.value": 0},
        {"a.id": 1, "b.id": 1, "b.value": 10},
        {"a.id": 2, "b.id": 2, "b.value": 20},
    ]


def test_join_projection_stays_lazy_and_respects_limit():
    rows = ({"a.id": i, "b.value": i * 2} for i in range(100))
    projected, columns = _project_join_stream(
        rows,
        [
            {"field": "a.id"},
            {"field": "b.value", "alias": "value"},
        ],
        limit=2,
    )
    assert columns == ["a.id", "b.value"]
    assert not isinstance(projected, list)
    assert list(projected) == [
        {"a.id": 0, "value": 0},
        {"a.id": 1, "value": 2},
    ]


def test_non_stream_join_preserves_materialized_result_contract(monkeypatch):
    import database

    datasets = [
        {"id": "a", "source_type": "imported"},
        {"id": "b", "source_type": "imported"},
    ]
    rows = {
        "a": [{"a.id": 1, "a.zone": "A"}],
        "b": [{"b.id": 1, "b.label": "one"}],
    }

    monkeypatch.setattr(database, "_resolve_report_dataset", lambda dataset: dataset)
    monkeypatch.setattr(
        database,
        "_stream_dataset",
        lambda dataset, **_: iter(rows[dataset["id"]]),
    )

    result = database._execute_report_query_unbounded(
        datasets,
        [{
            "left_dataset": "a",
            "right_dataset": "b",
            "left_column": "id",
            "right_column": "id",
            "join_type": "INNER",
        }],
        [{"field": "a.zone", "alias": "zone"}, {"field": "b.label", "alias": "label"}],
        [], [], [], [], [], 100,
    )

    assert result["success"] is True
    assert result["rows"] == [{"zone": "A", "label": "one"}]
    assert "streaming_rows" not in result
