import time

from execution_manager import ExecutionManager
from export_manager import ExportJobManager


def wait_for(manager, job_id, timeout=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = manager.get(job_id)
        if job and job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.01)
    return manager.get(job_id)


def test_execution_job_survives_manager_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("EXECUTION_JOB_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setenv("EXECUTION_RESULT_DB_PATH", str(tmp_path / "results.sqlite3"))
    first = ExecutionManager(max_workers=1, retention_seconds=60)
    job_id = first.submit(
        lambda: {"success": True, "rows": [{"id": 1}], "columns": ["id"], "total_rows": 1},
        owner_user_id="u1", owner_username="alice", query_payload={"datasets": [], "limit": 0},
    )
    assert wait_for(first, job_id)["status"] == "completed"
    first.shutdown()

    second = ExecutionManager(max_workers=1, retention_seconds=60)
    try:
        restored = second.get(job_id)
        assert restored["status"] == "completed"
        assert restored["owner_user_id"] == "u1"
        assert restored["owner_username"] == "alice"
        assert second.get_query_payload(job_id) == {"datasets": [], "limit": 0}
        assert second.result_page(job_id, limit=10)["rows"] == [{"id": 1}]
    finally:
        second.shutdown()


def test_inflight_execution_is_recovered_as_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("EXECUTION_JOB_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setenv("EXECUTION_RESULT_DB_PATH", str(tmp_path / "results.sqlite3"))
    first = ExecutionManager(max_workers=1, retention_seconds=60)
    try:
        gate = __import__("threading").Event()
        job_id = first.submit(lambda: gate.wait(30), owner_user_id="u2")
        deadline = time.time() + 2
        while time.time() < deadline and first.get(job_id)["status"] != "running":
            time.sleep(0.01)
        second = ExecutionManager(max_workers=1, retention_seconds=60)
        try:
            restored = second.get(job_id)
            assert restored["status"] == "failed"
            assert "restarted" in restored["error"].lower()
        finally:
            second.shutdown()
        gate.set()
    finally:
        first.shutdown(wait=False)


def test_export_job_survives_manager_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("EXECUTION_JOB_DB_PATH", str(tmp_path / "jobs.sqlite3"))
    export_dir = tmp_path / "exports"
    first = ExportJobManager(export_dir, max_workers=1, retention_seconds=60)
    export_id = first.submit(
        source_job_id="job_123", owner_user_id="u1", owner_username="alice",
        fmt="csv", filename="report.csv", columns=["id"],
        row_iterator_factory=lambda: iter([{"id": 1}, {"id": 2}]), total_rows=2,
    )
    deadline = time.time() + 3
    while time.time() < deadline:
        job = first.get(export_id)
        if job and job["status"] == "completed":
            break
        time.sleep(0.01)
    assert first.get(export_id)["status"] == "completed"
    first.shutdown(wait=True)

    second = ExportJobManager(export_dir, max_workers=1, retention_seconds=60)
    try:
        restored = second.get(export_id)
        assert restored["status"] == "completed"
        assert restored["owner_user_id"] == "u1"
        completed = second.path_for_completed(export_id)
        assert completed is not None
        assert completed[1].read_text(encoding="utf-8") == "id\n1\n2\n"
    finally:
        second.shutdown(wait=True)
