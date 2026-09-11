from query_model import QueryDefinition
from query_planner import ExecutionStrategy, plan_query


def ds(name, connection):
    return {"id": name, "connection_id": connection, "database": "db", "table": name}


def join(left, right, lc="id", rc="id", jt="INNER"):
    return {"left_dataset": left, "right_dataset": right, "left_column": lc, "right_column": rc, "join_type": jt}


def query(datasets, joins):
    return QueryDefinition.model_validate({"datasets": datasets, "joins": joins, "columns": [], "limit": 100})


def test_linear_graph_has_deterministic_execution_order():
    p = plan_query(query([ds("A", "c1"), ds("B", "c1"), ds("C", "c1")], [join("A", "B"), join("B", "C")]))
    assert p.join_graph["connected"] is True
    assert p.join_graph["execution_order"] == ["A", "B", "C"]
    assert p.execution_strategy == ExecutionStrategy.SOURCE_JOIN


def test_branching_graph_is_supported():
    p = plan_query(query([ds("A", "c1"), ds("B", "c1"), ds("C", "c1"), ds("D", "c1")], [join("A", "B"), join("A", "C"), join("C", "D")]))
    assert p.join_graph["connected"] is True
    assert p.join_graph["execution_order"] == ["A", "B", "C", "D"]


def test_disconnected_dataset_rejects_execution_strategy():
    p = plan_query(query([ds("A", "c1"), ds("B", "c1"), ds("C", "c1")], [join("A", "B")]))
    assert p.join_graph["disconnected_datasets"] == ["C"]
    assert p.execution_strategy == ExecutionStrategy.REJECT
    assert any("disconnected" in w.lower() for w in p.warnings)


def test_unknown_dataset_reference_is_rejected():
    p = plan_query(query([ds("A", "c1"), ds("B", "c1")], [join("A", "Z")]))
    assert p.execution_strategy == ExecutionStrategy.REJECT
    assert p.join_graph["invalid_joins"]


def test_duplicate_relationship_is_rejected():
    p = plan_query(query([ds("A", "c1"), ds("B", "c1")], [join("A", "B"), join("B", "A")]))
    assert p.execution_strategy == ExecutionStrategy.REJECT
    assert p.join_graph["duplicate_edges"]


def test_cross_source_branch_remains_cross_source_strategy():
    p = plan_query(query([ds("A", "mysql"), ds("B", "mongo"), ds("C", "click")], [join("A", "B"), join("A", "C")]))
    assert p.cross_source_join is True
    assert p.execution_strategy == ExecutionStrategy.CROSS_SOURCE_JOIN
    assert p.join_graph["connected"] is True


def test_single_source_query_remains_compatible():
    p = plan_query(query([ds("A", "c1")], []))
    assert p.execution_strategy == ExecutionStrategy.SINGLE_SOURCE
    assert p.join_graph["execution_order"] == ["A"]


def test_join_graph_is_exposed_in_summary():
    p = plan_query(query([ds("A", "c1"), ds("B", "c1")], [join("A", "B", "customer_id", "id", "LEFT")]))
    s = p.summary()
    assert s["join_graph"]["edges"][0]["join_type"] == "LEFT"
    assert s["join_graph"]["execution_order"] == ["A", "B"]
