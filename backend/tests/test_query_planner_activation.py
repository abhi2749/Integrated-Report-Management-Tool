import main
from query_model import QueryDefinition


def _payload(join_count=0):
    datasets = [{"id": f"d{i}", "connection_id": f"c{i}", "database": "db"} for i in range(max(1, join_count + 1))]
    joins = [{"left_dataset": f"d{i}", "right_dataset": f"d{i+1}", "left_column": "id", "right_column": "id", "join_type": "INNER"} for i in range(join_count)]
    return {"datasets": datasets, "joins": joins, "columns": [], "limit": 10}


def test_prepare_report_query_returns_canonical_query():
    assert isinstance(main._prepare_report_query(_payload()), QueryDefinition)


def test_planner_is_invoked_before_execution_preparation(monkeypatch):
    called = {"value": False}
    original = main.plan_query
    def spy(query):
        called["value"] = True
        return original(query)
    monkeypatch.setattr(main, "plan_query", spy)
    main._prepare_report_query(_payload())
    assert called["value"] is True


def test_planner_activation_enforces_configured_join_operation_limit(monkeypatch):
    monkeypatch.setattr(main, "MAX_JOIN_OPERATIONS", 1)
    try:
        main._prepare_report_query(_payload(join_count=2))
    except ValueError as exc:
        assert "maximum allowed is 1" in str(exc)
    else:
        raise AssertionError("Expected JOIN limit validation to fail")


def test_planner_activation_allows_queries_at_limit(monkeypatch):
    monkeypatch.setattr(main, "MAX_JOIN_OPERATIONS", 1)
    assert len(main._prepare_report_query(_payload(join_count=1)).joins) == 1


def test_planner_activation_allows_unlimited_join_operations_when_configured_zero(monkeypatch):
    monkeypatch.setattr(main, "MAX_JOIN_OPERATIONS", 0)
    assert len(main._prepare_report_query(_payload(join_count=26)).joins) == 26
