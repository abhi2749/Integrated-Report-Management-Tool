from result_store import ExecutionResultStore


def test_ingest_reuses_one_sqlite_connection_for_all_batches(tmp_path, monkeypatch):
    store = ExecutionResultStore(tmp_path / "results.sqlite3")
    calls = 0
    original_connect = store._connect

    def counted_connect():
        nonlocal calls
        calls += 1
        return original_connect()

    monkeypatch.setattr(store, "_connect", counted_connect)
    store.ingest("job-connection-reuse", ({"id": i} for i in range(2505)), columns=["id"])

    assert calls == 1
    page = store.get_page("job-connection-reuse", offset=2500, limit=10)
    assert page["rows"] == [{"id": 2500}, {"id": 2501}, {"id": 2502}, {"id": 2503}, {"id": 2504}]
    assert page["total_rows"] == 2505


def test_ingest_keeps_reader_accessible_between_committed_batches(tmp_path):
    store = ExecutionResultStore(tmp_path / "results.sqlite3")
    rows = ({"id": i} for i in range(1005))

    result = store.ingest("job-reader", rows, columns=["id"])
    assert result["total_rows"] == 1005

    page = store.get_page("job-reader", offset=1000, limit=10)
    assert page["rows"] == [
        {"id": 1000},
        {"id": 1001},
        {"id": 1002},
        {"id": 1003},
        {"id": 1004},
    ]
