from query_pushdown import build_plan, connector_capabilities


def dataset(source_type, dataset_id="d1"):
    return {
        "id": dataset_id,
        "source_type": source_type,
        "database": "db",
        "table": "table",
    }


def test_database_connectors_advertise_only_implemented_pushdown():
    for source_type in ("mysql", "mongodb", "clickhouse"):
        caps = connector_capabilities(source_type)
        assert caps["projection"] is True
        assert caps["sort"] is True
        assert caps["limit"] is True
        assert caps["group_by"] is True
        assert caps["aggregations"] is True


def test_imported_dataset_does_not_claim_database_pushdown():
    plan = build_plan(
        datasets=[dataset("imported")],
        columns=["d1.zone"],
        filters=[{"field": "d1.zone", "operator": "=", "value": "WEST"}],
        sort=[{"field": "d1.zone", "direction": "ASC"}],
        group_by=["d1.zone"],
        aggregations=[{"function": "COUNT", "field": "d1.zone"}],
        limit=100,
    )
    summary = plan.summary()
    assert summary["pushed_filters"] == 0
    assert summary["pushed_sorts"] == 0
    assert summary["projection_pushdown"] is False
    assert summary["limit_pushdown"] is False
    assert summary["group_by_pushdown"] is False
    assert summary["aggregation_pushdown"] is False
    assert summary["mode"] == "application_execution"


def test_group_and_aggregation_use_database_pushdown_for_database_connectors():
    plan = build_plan(
        datasets=[dataset("mysql")],
        group_by=["d1.zone"],
        aggregations=[{"function": "COUNT", "field": "d1.id"}],
    )
    summary = plan.summary()
    assert summary["group_by_pushdown"] is True
    assert summary["aggregation_pushdown"] is True
    assert "group_by" not in summary["application_operations"]
    assert "aggregations" not in summary["application_operations"]
    assert summary["mode"] == "database_pushdown"


def test_mysql_filter_sort_and_limit_are_reported_as_pushdown_capabilities():
    plan = build_plan(
        datasets=[dataset("mysql")],
        filters=[{"field": "d1.zone", "operator": "=", "value": "WEST"}],
        sort=[{"field": "d1.zone", "direction": "DESC"}],
        columns=["d1.zone"],
        limit=25,
    )
    summary = plan.summary()
    assert summary["pushed_filters"] == 1
    assert summary["pushed_sorts"] == 1
    assert summary["projection_pushdown"] is True
    assert summary["limit_pushdown"] is True
    assert summary["mode"] == "database_pushdown"
