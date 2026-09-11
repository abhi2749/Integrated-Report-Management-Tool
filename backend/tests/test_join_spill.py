from join_engine import hash_join


def test_spill_inner_join_matches_in_memory_result():
    left = [{"id": i, "left": i} for i in range(8)]
    right = [{"id": i, "right": i * 10} for i in range(4, 12)]

    normal = list(hash_join(left, right, "id", "id", join_type="INNER", max_memory_bytes=10_000_000))
    spilled = list(hash_join(left, right, "id", "id", join_type="INNER", max_memory_bytes=1, spill_partitions=4))

    assert {tuple(sorted(row.items())) for row in spilled} == {tuple(sorted(row.items())) for row in normal}


def test_spill_left_join_preserves_unmatched_rows():
    left = [{"id": i, "left": i} for i in range(5)]
    right = [{"id": 2, "right": "match"}]

    result = list(hash_join(left, right, "id", "id", join_type="LEFT", max_memory_bytes=1, spill_partitions=3))
    assert len(result) == 5
    assert sum(row.get("right") is None for row in result) == 4


def test_spill_full_join_preserves_unmatched_rows_and_null_keys():
    left = [{"id": None, "left": "null-left"}, {"id": 1, "left": "one"}]
    right = [{"id": None, "right": "null-right"}, {"id": 2, "right": "two"}]

    result = list(hash_join(left, right, "id", "id", join_type="FULL", max_memory_bytes=1, spill_partitions=2))
    assert len(result) == 4
    assert not any(row.get("left") == "null-left" and row.get("right") == "null-right" for row in result)
    assert any(row.get("left") == "null-left" and row.get("right") is None for row in result)
    assert any(row.get("right") == "null-right" and row.get("left") is None for row in result)
    assert any(row.get("left") == "one" and row.get("right") is None for row in result)
    assert any(row.get("right") == "two" and row.get("left") is None for row in result)


def test_spill_accepts_generator_probe_side():
    left = ({"id": i} for i in range(10))
    right = [{"id": i} for i in range(10)]
    result = list(hash_join(left, right, "id", "id", join_type="INNER", max_memory_bytes=1, spill_partitions=4))
    assert len(result) == 10
