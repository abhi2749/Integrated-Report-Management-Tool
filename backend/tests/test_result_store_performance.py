from result_store import ExecutionResultStore

def test_result_store_accepts_large_page_size_without_application_cap(tmp_path):
    store = ExecutionResultStore(tmp_path / "results.sqlite3")
    store.replace_result("job-1", {"columns": ["id"], "rows": [{"id": i} for i in range(25)]})
    page = store.get_page("job-1", limit=50000)
    assert page["limit"] == 50000
    assert page["returned_rows"] == 25

def test_result_store_iter_rows_streams_all_rows(tmp_path):
    store = ExecutionResultStore(tmp_path / "results.sqlite3")
    store.ingest("job-2", ({"id": i} for i in range(5000)), columns=["id"])
    rows = store.iter_rows("job-2")
    assert next(rows)["id"] == 0
    assert sum(1 for _ in rows) == 4999
