import time

from execution_manager import ExecutionManager


def wait_for(manager, job_id, status="completed", timeout=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = manager.get(job_id)
        if job and job["status"] == status:
            return job
        time.sleep(0.01)
    return manager.get(job_id)


def test_completed_result_can_be_paged():
    manager = ExecutionManager(max_workers=1, retention_seconds=60)
    try:
        job_id = manager.submit(lambda: {"success": True, "rows": [{"id": i} for i in range(7)], "columns": ["id"], "returned_rows": 7})
        job = wait_for(manager, job_id)
        assert job["status"] == "completed"
        page = manager.result_page(job_id, offset=2, limit=3)
        assert page["ready"] is True
        assert page["rows"] == [{"id": 2}, {"id": 3}, {"id": 4}]
        assert page["has_more"] is True
    finally:
        manager.shutdown()


def test_result_page_reports_running_job_without_rows():
    manager = ExecutionManager(max_workers=1, retention_seconds=60)
    try:
        gate = __import__("threading").Event()
        job_id = manager.submit(lambda: (gate.wait(1), {"rows": []})[1])
        deadline = time.time() + 1
        while time.time() < deadline:
            status = manager.get(job_id)["status"]
            if status == "running":
                break
            time.sleep(0.01)
        page = manager.result_page(job_id, offset=0, limit=10)
        assert page["ready"] is False
        assert page["status"] == "running"
        assert page["rows"] == []
        gate.set()
    finally:
        manager.shutdown()


def test_result_page_does_not_cap_requested_limit():
    manager = ExecutionManager(max_workers=1, retention_seconds=60)
    try:
        job_id = manager.submit(lambda: {"rows": list(range(20)), "returned_rows": 20})
        wait_for(manager, job_id)
        page = manager.result_page(job_id, limit=50000)
        assert page["limit"] == 50000
    finally:
        manager.shutdown()


def test_query_definition_default_is_unbounded():
    from query_model import QueryDefinition
    assert QueryDefinition().limit == 0


def test_large_materialized_result_is_persisted_outside_job_payload():
    manager = ExecutionManager(max_workers=1, retention_seconds=60, inline_result_row_limit=2)
    try:
        rows = [{"id": i} for i in range(6)]
        job_id = manager.submit(lambda: {"success": True, "rows": rows, "columns": ["id"], "total_rows": 6})
        job = wait_for(manager, job_id)
        assert job["status"] == "completed"
        assert job["result_available"] is True
        assert job["result_row_count"] == 6
        page = manager.result_page(job_id, offset=3, limit=2)
        assert page["rows"] == [{"id": 3}, {"id": 4}]
        assert page["total_rows"] == 6
    finally:
        manager.shutdown()


def test_large_result_ingestion_honors_cancellation():
    import threading

    manager = ExecutionManager(max_workers=1, retention_seconds=60, inline_result_row_limit=1)
    try:
        gate = threading.Event()
        rows = ({"id": i} for i in range(10000))

        def produce():
            return {"success": True, "rows": rows, "columns": ["id"], "total_rows": 10000}

        job_id = manager.submit(produce)
        manager.cancel(job_id)
        gate.set()
        job = wait_for(manager, job_id, status="cancelled", timeout=2)
        assert job["status"] in {"cancelled", "completed", "failed"}
    finally:
        manager.shutdown()


def test_streaming_result_page_is_available_before_job_completes():
    import threading

    manager = ExecutionManager(max_workers=1, retention_seconds=60)
    try:
        gate = threading.Event()

        def produce():
            def rows():
                for i in range(1000):
                    yield {"id": i}
                gate.wait(2)
                for i in range(1000, 2000):
                    yield {"id": i}
            return {"streaming_rows": rows(), "columns": ["id"]}

        job_id = manager.submit(produce)
        deadline = time.time() + 2
        page = None
        while time.time() < deadline:
            page = manager.result_page(job_id, offset=0, limit=25)
            if page and page.get("returned_rows", 0) > 0:
                break
            time.sleep(0.01)
        assert page is not None
        assert page["status"] == "running"
        assert page["ready"] is True
        assert page["streaming"] is True
        assert page["rows"][0] == {"id": 0}
        assert page["total_rows"] >= 1000
        gate.set()
        job = wait_for(manager, job_id)
        assert job["status"] == "completed"
    finally:
        gate.set()
        manager.shutdown()


def test_wide_materialized_result_is_persisted_by_byte_budget():
    manager = ExecutionManager(
        max_workers=1,
        retention_seconds=60,
        inline_result_row_limit=1000,
        inline_result_byte_limit=1024,
    )
    try:
        rows = [{"id": i, "payload": "x" * 200} for i in range(10)]
        job_id = manager.submit(lambda: {"success": True, "rows": rows, "columns": ["id", "payload"], "total_rows": 10})
        job = wait_for(manager, job_id)
        assert job["status"] == "completed"
        assert job["result_available"] is True
        assert "result" not in job
        assert manager.result_page(job_id, offset=9, limit=1)["rows"] == [rows[9]]
    finally:
        manager.shutdown()


def test_materialized_result_persistence_does_not_hold_manager_lock(monkeypatch):
    import threading

    manager = ExecutionManager(max_workers=1, retention_seconds=60, inline_result_row_limit=1)
    entered = threading.Event()
    release = threading.Event()
    original_replace = manager.result_store.replace_result

    def blocking_replace(*args, **kwargs):
        entered.set()
        assert release.wait(2), "test timed out waiting for result persistence release"
        return original_replace(*args, **kwargs)

    monkeypatch.setattr(manager.result_store, "replace_result", blocking_replace)
    try:
        job_id = manager.submit(lambda: {"rows": [{"id": i} for i in range(10)], "columns": ["id"], "total_rows": 10})
        assert entered.wait(2), "result persistence did not start"

        observed = []
        getter = threading.Thread(target=lambda: observed.append(manager.get(job_id)))
        getter.start()
        getter.join(0.5)
        assert not getter.is_alive(), "manager.get remained blocked by result persistence"
        assert observed and observed[0]["status"] in {"running", "completed"}
    finally:
        release.set()
        manager.shutdown(wait=True)
