from query_contract import canonical_query_from_payload, canonical_query_payload


def _base():
    return {
        "datasets": [{"id": "d1", "connection_id": "c1", "database": "db", "table": "t"}],
        "columns": [{"field": "d1.id", "alias": "id"}],
        "limit": 100,
    }


def test_legacy_calculated_columns_normalize_to_canonical_calculations():
    payload = _base() | {"calculated_columns": [{"alias": "x", "left_field": "a", "operation": "+", "right_value": 1}]}
    q = canonical_query_from_payload(payload)
    assert len(q.calculations) == 1
    assert q.calculations[0].alias == "x"
    assert "calculations" not in q.normalized()
    assert "calculated_columns" in q.normalized()


def test_canonical_calculations_are_preserved():
    payload = _base() | {"calculations": [{"alias": "x", "left_field": "a", "operation": "+", "right_value": 1}]}
    q = canonical_query_from_payload(payload)
    assert q.calculations[0].alias == "x"


def test_canonical_payload_has_stable_execution_shape():
    result = canonical_query_payload(_base())
    assert set(result) >= {"datasets", "joins", "columns", "filters", "group_by", "aggregations", "sorts", "limit", "calculated_columns"}
    assert "calculations" not in result
    assert result["calculated_columns"] == []


def test_invalid_payload_is_rejected_at_boundary():
    payload = _base() | {"limit": -1}
    try:
        canonical_query_from_payload(payload)
    except ValueError as exc:
        assert "negative" in str(exc).lower()
    else:
        raise AssertionError("Expected invalid limit to be rejected")
