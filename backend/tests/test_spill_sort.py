import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import _sort_rows


def test_spill_sort_accepts_lazy_iterable_and_preserves_order():
    rows = ({"group": "A", "value": value} for value in range(500, -1, -1))
    result = _sort_rows(rows, [{"field": "value", "direction": "ASC"}], spill_memory_bytes=128)
    assert [row["value"] for row in result] == list(range(501))


def test_spill_sort_preserves_multiple_sort_directions_and_none_semantics():
    rows = [
        {"group": "B", "value": 2},
        {"group": "A", "value": None},
        {"group": "A", "value": 3},
        {"group": "A", "value": 1},
        {"group": "B", "value": 1},
    ]
    result = _sort_rows(
        iter(rows),
        [
            {"field": "group", "direction": "ASC"},
            {"field": "value", "direction": "DESC"},
        ],
        spill_memory_bytes=64,
    )
    assert result == [
        {"group": "A", "value": None},
        {"group": "A", "value": 3},
        {"group": "A", "value": 1},
        {"group": "B", "value": 2},
        {"group": "B", "value": 1},
    ]


def test_spill_sort_handles_mixed_comparable_types_like_legacy_sort():
    result = _sort_rows(
        iter([{"value": 10}, {"value": "2"}, {"value": 1}]),
        [{"field": "value", "direction": "ASC"}],
        spill_memory_bytes=32,
    )
    assert [row["value"] for row in result] == [1, 10, "2"]


def test_no_sort_still_returns_rows_without_spill_behavior_change():
    rows = ({"value": i} for i in range(3))
    assert _sort_rows(rows, []) == [{"value": 0}, {"value": 1}, {"value": 2}]
