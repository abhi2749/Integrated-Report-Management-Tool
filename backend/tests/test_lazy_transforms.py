import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import database


def test_calculate_row_preserves_existing_row_and_adds_value():
    source = {"sales": 10, "tax": 2}
    result = database._calculate_row(
        source,
        [{"alias": "total", "left_field": "sales", "operation": "ADD", "right_field": "tax"}],
    )
    assert source == {"sales": 10, "tax": 2}
    assert result["total"] == 12.0


def test_calculate_iterator_is_lazy():
    consumed = []

    def rows():
        for value in range(1000000):
            consumed.append(value)
            yield {"value": value}

    iterator = database._iter_calculate_rows(
        rows(),
        [{"alias": "double", "left_field": "value", "operation": "MULTIPLY", "right_value": 2}],
    )
    first = next(iterator)
    assert first["double"] == 0.0
    assert len(consumed) == 1


def test_execution_engine_allows_single_source_calculation_streaming():
    execution_engine = importlib.import_module("execution_engine")

    class Plan:
        execution_strategy = "SINGLE_SOURCE"
        join_count = 0

    class Query:
        datasets = []
        joins = []
        columns = []
        filters = []
        sorts = []
        group_by = []
        aggregations = []
        calculations = [{"alias": "x"}]
        limit = 0

    class Prepared:
        plan = Plan()
        query = Query()

    original = database.execute_report_query
    seen = {}

    def fake_execute_report_query(**kwargs):
        seen.update(kwargs)
        return {"success": True}

    database.execute_report_query = fake_execute_report_query
    sys.modules["database"] = database
    try:
        execution_engine.execute_prepared_execution(Prepared())
    finally:
        database.execute_report_query = original
        sys.modules["database"] = database

    assert seen["stream"] is True
