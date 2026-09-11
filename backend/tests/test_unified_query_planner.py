from query_model import QueryDefinition
from query_planner import ExecutionStrategy, plan_query


def _dataset(dataset_id, source_type, connection_id="c1", database="db", table="t"):
    return {
        "id": dataset_id,
        "source_type": source_type,
        "connection_id": connection_id,
        "database": database,
        "table": table,
    }


def test_unified_planner_exposes_all_first_class_connectors_without_credentials():
    query = QueryDefinition.model_validate({
        "datasets": [
            _dataset("mysql_ds", "mysql"),
            _dataset("mongo_ds", "mongodb", "c2"),
            _dataset("ch_ds", "clickhouse", "c3"),
        ],
        "columns": [{"field": "id"}],
    })
    plan = plan_query(query)
    sources = {item["source_type"] for item in plan.source_plans}
    assert sources == {"mysql", "mongodb", "clickhouse"}
    for item in plan.source_plans:
        assert "password" not in item
        assert "username" not in item


def test_same_connection_mysql_join_is_planned_as_native_candidate():
    query = QueryDefinition.model_validate({
        "datasets": [_dataset("a", "mysql"), _dataset("b", "mysql")],
        "joins": [{
            "left_dataset": "a", "right_dataset": "b",
            "left_column": "id", "right_column": "id", "join_type": "INNER",
        }],
    })
    plan = plan_query(query)
    assert plan.execution_strategy == ExecutionStrategy.SOURCE_JOIN
    candidates = plan.source_plans[0]["join_pushdown_candidates"]
    assert candidates[0]["eligible"] is True
    assert candidates[0]["reason"] == "native_join_candidate"


def test_cross_source_join_is_application_execution_and_not_native_pushdown():
    query = QueryDefinition.model_validate({
        "datasets": [
            _dataset("m", "mysql", "mysql1"),
            _dataset("g", "mongodb", "mongo1"),
        ],
        "joins": [{
            "left_dataset": "m", "right_dataset": "g",
            "left_column": "id", "right_column": "id", "join_type": "INNER",
        }],
    })
    plan = plan_query(query)
    assert plan.join_strategy == "application_join"
    assert plan.requires_application_execution is True
    assert plan.source_plans[0]["join_pushdown_candidates"][0]["eligible"] is False
    assert plan.source_plans[0]["join_pushdown_candidates"][0]["reason"] == "different_connector_types"
