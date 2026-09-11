from query_model import QueryDefinition
from query_planner import ExecutionStrategy, plan_query


def dataset(dataset_id, connection_id):
    return {
        "id": dataset_id,
        "connection_id": connection_id,
        "source_type": "mysql",
        "database": "db",
        "table": dataset_id,
    }


def join(left, right):
    return {
        "left_dataset": left,
        "right_dataset": right,
        "left_column": "id",
        "right_column": "id",
        "join_type": "INNER",
    }


def test_single_dataset_strategy():
    plan = plan_query(QueryDefinition(datasets=[dataset("a", "c1")]))
    assert plan.execution_strategy == ExecutionStrategy.SINGLE_SOURCE


def test_multiple_sources_without_join_strategy():
    plan = plan_query(QueryDefinition(datasets=[dataset("a", "c1"), dataset("b", "c2")]))
    assert plan.execution_strategy == ExecutionStrategy.MULTI_SOURCE
    assert any("without a JOIN" in warning for warning in plan.warnings)


def test_same_source_join_strategy():
    plan = plan_query(
        QueryDefinition(
            datasets=[dataset("a", "c1"), dataset("b", "c1")],
            joins=[join("a", "b")],
        )
    )
    assert plan.execution_strategy == ExecutionStrategy.SOURCE_JOIN
    assert plan.cross_source_join is False


def test_cross_source_join_strategy():
    plan = plan_query(
        QueryDefinition(
            datasets=[dataset("a", "c1"), dataset("b", "c2")],
            joins=[join("a", "b")],
        )
    )
    assert plan.execution_strategy == ExecutionStrategy.CROSS_SOURCE_JOIN
    assert plan.cross_source_join is True


def test_empty_query_is_rejected_by_strategy_classification():
    plan = plan_query(QueryDefinition())
    assert plan.execution_strategy == ExecutionStrategy.REJECT
    assert any("no datasets" in warning for warning in plan.warnings)


def test_strategy_is_exposed_in_plan_summary():
    plan = plan_query(QueryDefinition(datasets=[dataset("a", "c1")]))
    summary = plan.summary()
    assert summary["execution_strategy"] == ExecutionStrategy.SINGLE_SOURCE
