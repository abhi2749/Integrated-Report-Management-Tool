import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import _aggregate_rows


def test_grouped_aggregation_accepts_lazy_iterables_without_row_retention():
    class TrackingRows:
        def __init__(self, rows):
            self.rows = iter(rows)
            self.consumed = 0

        def __iter__(self):
            for row in self.rows:
                self.consumed += 1
                yield row

    source = TrackingRows({"group": "A", "value": i} for i in range(1000))
    result = _aggregate_rows(
        source,
        ["group"],
        [
            {"function": "COUNT", "field": "value", "alias": "count"},
            {"function": "SUM", "field": "value", "alias": "sum"},
            {"function": "AVG", "field": "value", "alias": "avg"},
            {"function": "MIN", "field": "value", "alias": "min"},
            {"function": "MAX", "field": "value", "alias": "max"},
        ],
    )

    assert source.consumed == 1000
    assert result == [{
        "group": "A", "count": 1000, "sum": 499500,
        "avg": 499.5, "min": 0, "max": 999,
    }]


def test_global_aggregation_keeps_constant_input_state():
    rows = ({"value": i} for i in range(10_000))
    result = _aggregate_rows(
        rows,
        [],
        [
            {"function": "COUNT", "field": "value", "alias": "count"},
            {"function": "SUM", "field": "value", "alias": "sum"},
        ],
    )
    assert result == [{"count": 10_000, "sum": 49_995_000}]


def test_mixed_min_max_preserve_legacy_string_fallback():
    result = _aggregate_rows(
        [{"group": "A", "value": 10}, {"group": "A", "value": "2"}],
        ["group"],
        [
            {"function": "MIN", "field": "value", "alias": "min"},
            {"function": "MAX", "field": "value", "alias": "max"},
        ],
    )
    assert result == [{"group": "A", "min": "10", "max": "2"}]


def test_empty_global_aggregate_preserves_one_result_row():
    result = _aggregate_rows(
        iter(()),
        [],
        [
            {"function": "COUNT", "field": "value", "alias": "count"},
            {"function": "SUM", "field": "value", "alias": "sum"},
            {"function": "AVG", "field": "value", "alias": "avg"},
            {"function": "MIN", "field": "value", "alias": "min"},
            {"function": "MAX", "field": "value", "alias": "max"},
        ],
    )
    assert result == [{"count": 0, "sum": 0, "avg": None, "min": None, "max": None}]
