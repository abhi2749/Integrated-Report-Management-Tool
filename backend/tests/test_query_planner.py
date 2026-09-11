from query_model import QueryDefinition
from query_planner import plan_query


def test_single_source_plan_has_expected_stages():
    query = QueryDefinition.model_validate({
        "datasets": [{"id": "d1", "connection_id": "c1", "database": "pspcl"}],
        "columns": [{"field": "zone"}],
        "filters": [{"field": "zone", "operator": "=", "value": "WEST"}],
        "sorts": [{"field": "zone", "direction": "ASC"}],
    })
    plan = plan_query(query)
    assert plan.source_count == 1
    assert plan.join_strategy == "none"
    assert plan.stages == ["source", "filter", "sort", "limit"]
    assert plan.pushdown["pushed_filters"] == 1


def test_multi_source_join_is_marked_application_join():
    query = QueryDefinition.model_validate({
        "datasets": [
            {"id": "d1", "connection_id": "mysql-1", "database": "a"},
            {"id": "d2", "connection_id": "mongo-1", "database": "b"},
        ],
        "joins": [{
            "left_dataset": "d1",
            "right_dataset": "d2",
            "left_column": "meter_id",
            "right_column": "meter_id",
            "join_type": "INNER",
        }],
    })
    plan = plan_query(query)
    assert plan.cross_source_join is True
    assert plan.join_strategy == "application_join"
    assert "multiple source connections" in plan.warnings[0]



def test_group_and_aggregation_are_database_pushdown_capabilities_in_plan_summary():
    query = QueryDefinition.model_validate({
        "datasets": [{"id": "d1", "connection_id": "c1", "source_type": "mysql", "database": "db"}],
        "columns": [{"field": "d1.zone"}],
        "group_by": ["d1.zone"],
        "aggregations": [{"function": "COUNT", "field": "d1.id", "alias": "count_id"}],
    })
    summary = plan_query(query).summary()["pushdown"]
    assert summary["group_by_pushdown"] is True
    assert summary["aggregation_pushdown"] is True
    assert summary["mode"] == "database_pushdown"
    assert "group_by" not in summary["application_operations"]
    assert "aggregations" not in summary["application_operations"]


def test_mysql_filter_sort_and_limit_are_planner_pushdown_capabilities():
    query = QueryDefinition.model_validate({
        "datasets": [{"id": "d1", "connection_id": "c1", "source_type": "mysql", "database": "db"}],
        "columns": [{"field": "d1.zone"}],
        "filters": [{"field": "d1.zone", "operator": "=", "value": "WEST"}],
        "sorts": [{"field": "d1.zone", "direction": "DESC"}],
        "limit": 25,
    })
    summary = plan_query(query).summary()["pushdown"]
    assert summary["pushed_filters"] == 1
    assert summary["pushed_sorts"] == 1
    assert summary["projection_pushdown"] is True
    assert summary["limit_pushdown"] is True
    assert summary["mode"] == "database_pushdown"
