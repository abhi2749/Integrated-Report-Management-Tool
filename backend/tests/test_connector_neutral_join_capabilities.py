from query_planner import plan_query
from query_pushdown import can_pushdown_join, join_capabilities
from query_model import QueryDefinition


def ds(source, ident, connection="c1", database="db"):
    return {"id": ident, "source_type": source, "connection_id": connection, "host": "host", "port": 1, "database": database, "table": ident}


def test_only_implemented_connector_advertises_native_join_capability():
    assert join_capabilities("mysql")["native"] is True
    assert "INNER" in join_capabilities("mysql")["join_types"]
    for source in ("mongodb", "clickhouse"):
        caps = join_capabilities(source)
        assert caps["native"] is False
        assert caps["join_types"] == []


def test_native_join_capability_matches_implemented_execution_path():
    ok, reason = can_pushdown_join(ds("mysql", "a"), ds("mysql", "b"), {"left_column": "id", "right_column": "id", "join_type": "INNER"})
    assert ok is True
    assert reason == "native_join_candidate"
    for source in ("mongodb", "clickhouse"):
        ok, reason = can_pushdown_join(ds(source, "a"), ds(source, "b"), {"left_column": "id", "right_column": "id", "join_type": "INNER"})
        assert ok is False
        assert reason == "connector_join_not_supported"


def test_cross_connector_join_uses_application_spill_strategy():
    query = QueryDefinition.model_validate({
        "datasets": [ds("mysql", "a"), ds("mongodb", "b", connection="c2")],
        "joins": [{"left_dataset": "a", "right_dataset": "b", "left_column": "id", "right_column": "id", "join_type": "INNER"}],
        "columns": [{"field": "a.id"}, {"field": "b.id"}],
    })
    plan = plan_query(query)
    assert plan.execution_strategy == "CROSS_SOURCE_JOIN"
    assert plan.join_strategy == "application_join"
    assert plan.join_capabilities[0]["native_supported"] is False


def test_mongodb_cross_database_join_is_not_claimed_as_native():
    ok, reason = can_pushdown_join(ds("mongodb", "a", database="db1"), ds("mongodb", "b", database="db2"), {"left_column": "id", "right_column": "id", "join_type": "INNER"})
    assert ok is False
    assert reason == "connector_join_not_supported"


def test_mongodb_right_join_is_not_claimed_as_native():
    ok, reason = can_pushdown_join(ds("mongodb", "a"), ds("mongodb", "b"), {"left_column": "id", "right_column": "id", "join_type": "RIGHT"})
    assert ok is False
    assert reason == "connector_join_not_supported"
