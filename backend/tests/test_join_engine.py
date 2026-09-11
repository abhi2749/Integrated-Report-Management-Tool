from join_engine import (
    choose_build_side,
    estimate_join_memory,
    hash_join,
    join_rows,
    normalize_join_key,
)


def rows(items):
    return [dict(item) for item in items]


def test_inner_join_preserves_duplicate_matches_and_normalizes_numeric_types():
    left = rows([
        {"id": 1, "name": "A"},
        {"id": 2, "name": "B"},
    ])
    right = rows([
        {"meter_id": "1", "reading": 10},
        {"meter_id": 1, "reading": 11},
        {"meter_id": "3", "reading": 30},
    ])

    result = join_rows(left, right, "id", "meter_id", join_type="INNER")

    assert [(r["id"], r["reading"]) for r in result] == [(1, 10), (1, 11)]


def test_left_join_preserves_unmatched_left_with_null_right_schema():
    left = rows([{"id": 1, "left_value": "A"}, {"id": 2, "left_value": "B"}])
    right = rows([{"meter_id": 1, "reading": 10}])

    result = join_rows(left, right, "id", "meter_id", join_type="LEFT")

    assert len(result) == 2
    unmatched = next(r for r in result if r["id"] == 2)
    assert unmatched["meter_id"] is None
    assert unmatched["reading"] is None


def test_right_join_preserves_unmatched_right_with_null_left_schema():
    left = rows([{"id": 1, "left_value": "A"}])
    right = rows([{"meter_id": 1, "reading": 10}, {"meter_id": 3, "reading": 30}])

    result = join_rows(left, right, "id", "meter_id", join_type="RIGHT")

    assert len(result) == 2
    unmatched = next(r for r in result if r["meter_id"] == 3)
    assert unmatched["id"] is None
    assert unmatched["left_value"] is None


def test_full_join_preserves_both_unmatched_sides():
    left = rows([{"id": 1, "left_value": "A"}, {"id": 2, "left_value": "B"}])
    right = rows([{"meter_id": 1, "reading": 10}, {"meter_id": 3, "reading": 30}])

    result = join_rows(left, right, "id", "meter_id", join_type="FULL")

    assert len(result) == 3
    left_unmatched = next(r for r in result if r["id"] == 2)
    right_unmatched = next(r for r in result if r["meter_id"] == 3)
    assert left_unmatched["reading"] is None
    assert right_unmatched["left_value"] is None


def test_null_keys_do_not_match():
    left = rows([{"id": None, "left_value": "A"}])
    right = rows([{"meter_id": None, "reading": 10}])

    assert join_rows(left, right, "id", "meter_id", join_type="INNER") == []
    result = join_rows(left, right, "id", "meter_id", join_type="FULL")
    assert len(result) == 2


def test_build_side_and_memory_estimate_are_available():
    assert choose_build_side(2, 10) == "left"
    assert choose_build_side(10, 2) == "right"
    estimate = estimate_join_memory([{"id": 1}, {"id": 2}])
    assert estimate["row_count"] == 2
    assert estimate["estimated_bytes"] > 0


def test_leading_zero_identifier_is_not_coerced_to_number():
    assert normalize_join_key("00123") != normalize_join_key(123)


def test_invalid_join_type_is_rejected():
    left = [{"id": 1}]
    right = [{"id": 1}]
    try:
        list(hash_join(left, right, "id", "id", join_type="CROSS"))
    except ValueError as exc:
        assert "Unsupported join type" in str(exc)
    else:
        raise AssertionError("Expected unsupported JOIN type to fail")
