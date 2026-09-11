from execution_contract import prepare_execution
from query_model import QueryDefinition


def _payload():
    return {
        "datasets": [{"id": "d1", "connection_id": "c1", "database": "db", "table": "t"}],
        "columns": [{"field": "d1.id"}],
        "limit": 0,
    }


def test_prepare_execution_returns_one_canonical_query_and_plan():
    prepared = prepare_execution(_payload())
    assert isinstance(prepared.query, QueryDefinition)
    assert prepared.plan.source_count == 1
    assert prepared.payload["datasets"][0]["id"] == "d1"
    assert len(prepared.fingerprint) == 64


def test_prepare_execution_fingerprint_is_stable_for_same_query():
    first = prepare_execution(_payload())
    second = prepare_execution(_payload())
    assert first.fingerprint == second.fingerprint


def test_prepare_execution_does_not_mutate_query_payload():
    payload = _payload()
    original = dict(payload)
    prepare_execution(payload)
    assert payload == original


def test_prepare_execution_accepts_existing_query_definition():
    query = QueryDefinition.model_validate(_payload())
    prepared = prepare_execution(query)
    assert prepared.query is query


def test_prepare_execution_keeps_all_first_class_connector_types_in_canonical_query():
    payload = {
        "datasets": [
            {"id": "mysql_ds", "connection_id": "m1", "source_type": "mysql", "database": "db", "table": "t"},
            {"id": "mongo_ds", "connection_id": "m2", "source_type": "mongodb", "database": "db", "table": "t"},
            {"id": "ch_ds", "connection_id": "c1", "source_type": "clickhouse", "database": "db", "table": "t"},
        ],
        "columns": [],
        "limit": 0,
    }
    prepared = prepare_execution(payload)
    assert [d.source_type for d in prepared.query.datasets] == ["mysql", "mongodb", "clickhouse"]
    assert prepared.plan.source_count == 3
