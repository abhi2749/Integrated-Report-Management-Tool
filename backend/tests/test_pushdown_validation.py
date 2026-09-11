"""A10.10 connector pushdown validation tests.

These tests target the current connector execution boundaries rather than the
legacy database-level connection helpers. They validate that the existing
MySQL/MongoDB pushdown plans actually reach the connector execution paths.
"""

import database
from mysql_pushdown import build_filter_clause, build_projection
from mongodb_pushdown import build_pipeline
from connectors.mysql import MySQLConnector
from connectors.mongodb import MongoDBConnector


def mysql_dataset():
    return {
        "id": "mysql-test",
        "source_type": "mysql",
        "host": "db.example",
        "port": 3306,
        "username": "user",
        "password": "password",
        "database": "pspcl",
        "table": "master_meter_data",
    }


def mongo_dataset():
    return {
        "id": "mongo-test",
        "source_type": "mongodb",
        "host": "mongo.example",
        "port": 27017,
        "username": "user",
        "password": "password",
        "database": "PSPCL_DATA",
        "table": "Master_Data",
    }


def test_mysql_filter_pushdown_is_parameterized():
    sql, params, pushed = build_filter_clause(
        [{"field": "zone", "operator": "=", "value": "WEST"}]
    )

    assert "`zone` = %s" in sql
    assert params == ["WEST"]
    assert pushed == 1
    assert "WEST" not in sql


def test_mysql_projection_contains_only_required_columns():
    projection = build_projection("mysql_a", ["id", "zone"])

    assert "`id`" in projection
    assert "`zone`" in projection
    assert "*" not in projection


def test_mysql_database_boundary_executes_parameterized_pushdown(monkeypatch):
    captured = {}

    class FakeCursor:
        def __init__(self):
            self.batches = [
                [{"id": 1, "zone": "WEST"}],
                [{"id": 2, "zone": "WEST"}],
                [],
            ]
            self.query = None
            self.params = None

        def execute(self, query, params=None):
            self.query = query
            self.params = params
            captured["cursor"] = self

        def fetchmany(self, size):
            return self.batches.pop(0)

        def close(self):
            captured["cursor_closed"] = True

    cursor = FakeCursor()

    class FakeConnection:
        def cursor(self, **kwargs):
            assert kwargs["dictionary"] is True
            assert kwargs["buffered"] is False
            return cursor

        def is_connected(self):
            return True

        def close(self):
            captured["connection_closed"] = True

    # Current database._fetch_mysql() delegates to the MySQL connector.
    # Patch the connector's actual connection boundary so no network call occurs.
    monkeypatch.setattr(
        MySQLConnector,
        "_connect",
        lambda self, database_name: FakeConnection(),
    )

    rows = database._fetch_mysql(
        mysql_dataset(),
        pushdown_filters=[
            {"field": "zone", "operator": "=", "value": "WEST"},
        ],
        required_columns=["id", "zone"],
    )

    assert rows == [
        {"id": 1, "zone": "WEST"},
        {"id": 2, "zone": "WEST"},
    ]
    assert "`zone` = %s" in cursor.query
    assert cursor.params == ["WEST"]
    assert "WEST" not in cursor.query
    assert "`id`" in cursor.query
    assert "`zone`" in cursor.query
    assert "*" not in cursor.query
    assert captured["cursor_closed"] is True
    assert captured["connection_closed"] is True


def test_mongodb_pipeline_pushes_match_projection_sort_and_limit():
    pipeline = build_pipeline(
        filters=[
            {"field": "zone", "operator": "=", "value": "WEST"},
        ],
        columns=["id", "zone"],
        sort=[{"field": "id", "direction": "ASC"}],
        limit=100,
    )

    assert any("$match" in stage for stage in pipeline)
    assert any("$project" in stage for stage in pipeline)
    assert any("$sort" in stage for stage in pipeline)
    assert any("$limit" in stage for stage in pipeline)

    match_stage = next(stage["$match"] for stage in pipeline if "$match" in stage)
    assert match_stage["zone"] == {"$eq": "WEST"}

    project_stage = next(
        stage["$project"] for stage in pipeline if "$project" in stage
    )
    assert project_stage["id"] == 1
    assert project_stage["zone"] == 1


def test_mongodb_database_boundary_executes_pipeline_with_batching(monkeypatch):
    captured = {}

    class FakeCollection:
        def aggregate(self, pipeline, **kwargs):
            captured["pipeline"] = pipeline
            captured["kwargs"] = kwargs
            return iter(
                [
                    {"id": 1, "zone": "WEST"},
                    {"id": 2, "zone": "WEST"},
                ]
            )

    class FakeDB:
        def __getitem__(self, name):
            assert name == "Master_Data"
            return FakeCollection()

    class FakeClient:
        def __getitem__(self, name):
            assert name == "PSPCL_DATA"
            return FakeDB()

        def close(self):
            captured["closed"] = True

    # Current database._fetch_mongodb() delegates to MongoDBConnector, whose
    # actual network boundary is _client().
    monkeypatch.setattr(
        MongoDBConnector,
        "_client",
        lambda self: FakeClient(),
    )

    rows = database._fetch_mongodb(
        mongo_dataset(),
        pushdown_filters=[
            {"field": "zone", "operator": "=", "value": "WEST"},
        ],
        required_columns=["id", "zone"],
        pushdown_sorts=[{"field": "id", "direction": "ASC"}],
        pushdown_limit=100,
    )

    assert rows == [
        {"mongo-test.id": 1, "mongo-test.zone": "WEST"},
        {"mongo-test.id": 2, "mongo-test.zone": "WEST"},
    ]

    pipeline = captured["pipeline"]
    assert any("$match" in stage for stage in pipeline)
    assert any("$project" in stage for stage in pipeline)
    assert any("$sort" in stage for stage in pipeline)
    assert any("$limit" in stage for stage in pipeline)

    assert captured["kwargs"]["allowDiskUse"] is True
    assert captured["kwargs"]["batchSize"] == 5000
    assert captured["closed"] is True


def test_unsupported_mysql_operator_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="Unsupported MySQL filter operator"):
        build_filter_clause(
            [{"field": "zone", "operator": "UNSUPPORTED_OPERATOR", "value": "WEST"}]
        )


def test_mysql_same_source_join_stream_pushes_join_and_source_filters(monkeypatch):
    captured = {}

    left = mysql_dataset() | {"id": "left", "table": "meters"}
    right = mysql_dataset() | {"id": "right", "table": "zones"}
    join_def = {
        "left_dataset": "left",
        "right_dataset": "right",
        "left_column": "zone_id",
        "right_column": "id",
        "join_type": "INNER",
    }

    class FakeCursor:
        def execute(self, query, params=None):
            captured["query"] = query
            captured["params"] = params
        def close(self):
            captured["cursor_closed"] = True
        def fetchmany(self, size):
            return []

    class FakeConnection:
        def cursor(self, **kwargs):
            assert kwargs == {"dictionary": True, "buffered": False}
            return FakeCursor()
        def is_connected(self):
            return True
        def close(self):
            captured["connection_closed"] = True

    monkeypatch.setattr(MySQLConnector, "_connect", lambda self, database: FakeConnection())

    rows = list(MySQLConnector(
        host="db.example", port=3306, username="user", password="password"
    ).execute_join_stream(
        left,
        right,
        join_def,
        required_by_dataset={"left": {"zone_id", "value"}, "right": {"id", "name"}},
        filters_by_dataset={
            "left": [{"field": "value", "operator": ">", "value": 10}],
            "right": [{"field": "name", "operator": "=", "value": "WEST"}],
        },
    ))

    assert rows == []
    assert "INNER JOIN" in captured["query"]
    assert "`l`.`zone_id` = `r`.`id`" in captured["query"]
    assert "`l`.`value` > %s" in captured["query"]
    assert "`r`.`name` = %s" in captured["query"]
    assert captured["params"] == [10, "WEST"]
    assert "WEST" not in captured["query"]
    assert "`left.zone_id`" in captured["query"]
    assert "`right.name`" in captured["query"]
