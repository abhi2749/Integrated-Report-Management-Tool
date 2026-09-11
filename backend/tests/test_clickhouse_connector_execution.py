from connectors.clickhouse import ClickHouseConnector


def test_clickhouse_limit_is_not_artificially_bounded(monkeypatch):
    captured = {}

    class Result:
        column_names = ["x"]
        result_rows = [(1,)]

    class Client:
        def query(self, query, parameters=None):
            captured["query"] = query
            return Result()

        def close(self):
            pass

    monkeypatch.setattr(
        ClickHouseConnector,
        "_client",
        lambda self, database=None: Client(),
    )

    ClickHouseConnector("localhost", 8123).execute_dataset(
        {"id": "d", "database": "db", "table": "t"},
        pushdown_limit=999999,
    )

    assert captured["query"].endswith(" LIMIT 999999")


def test_clickhouse_zero_limit_is_unbounded(monkeypatch):
    captured = {}

    class Result:
        column_names = ["x"]
        result_rows = [(1,)]

    class Client:
        def query(self, query, parameters=None):
            captured["query"] = query
            return Result()

        def close(self):
            pass

    monkeypatch.setattr(
        ClickHouseConnector,
        "_client",
        lambda self, database=None: Client(),
    )

    ClickHouseConnector("localhost", 8123).execute_dataset(
        {"id": "d", "database": "db", "table": "t"},
        pushdown_limit=0,
    )

    assert " LIMIT " not in captured["query"]


def test_clickhouse_stream_uses_row_block_stream(monkeypatch):
    captured = {}

    class Stream:
        source = type("Source", (), {"column_names": ["x"]})()

        def __enter__(self):
            return self

        def __iter__(self):
            return iter([[(1,)], [(2,)]])

        def __exit__(self, *args):
            return False

    class Client:
        def query_row_block_stream(self, query, parameters=None):
            captured["query"] = query
            return Stream()

        def close(self):
            pass

    monkeypatch.setattr(ClickHouseConnector, "_client", lambda self, database=None: Client())

    rows = list(ClickHouseConnector("localhost", 8123).execute_dataset_stream(
        {"id": "d", "database": "db", "table": "t"},
    ))

    assert rows == [{"d.x": 1}, {"d.x": 2}]
    assert "SELECT * FROM `t`" in captured["query"]
