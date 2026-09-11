from __future__ import annotations

from result_store import ExecutionResultStore


def test_result_store_persists_and_pages(tmp_path):
    store = ExecutionResultStore(tmp_path / "results.sqlite3")
    result = {
        "success": True,
        "columns": ["id", "name"],
        "rows": [{"id": i, "name": f"row-{i}"} for i in range(23)],
        "total_rows": 23,
    }

    meta = store.replace_result("job_test", result)
    assert meta["total_rows"] == 23

    page = store.get_page("job_test", offset=10, limit=5)
    assert page is not None
    assert page["rows"][0]["id"] == 10
    assert len(page["rows"]) == 5
    assert page["has_more"] is True
    assert page["materialized_rows"] == 23

    last = store.get_page("job_test", offset=20, limit=10)
    assert last["rows"][0]["id"] == 20
    assert len(last["rows"]) == 3
    assert last["has_more"] is False
