import time

from execution_manager import ExecutionManager


def wait_for(manager, job_id, timeout=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = manager.get(job_id)
        if job and job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def make_result(count):
    return {
        "success": True,
        "columns": ["id"],
        "rows": [{"id": i} for i in range(count)],
        "total_rows": count,
        "returned_rows": count,
    }


def test_small_results_remain_inline_for_compatibility():
    manager = ExecutionManager(max_workers=1, retention_seconds=60, inline_result_row_limit=3)
    try:
        job_id = manager.submit(lambda: make_result(3), owner_user_id="u1", owner_username="user")
        job = wait_for(manager, job_id)
        assert job["status"] == "completed"
        assert len(job["result"]["rows"]) == 3
        assert job["owner_user_id"] == "u1"
    finally:
        manager.shutdown()


def test_large_results_are_not_inlined_in_status():
    manager = ExecutionManager(max_workers=1, retention_seconds=60, inline_result_row_limit=3)
    try:
        job_id = manager.submit(lambda: make_result(4), owner_user_id="u2", owner_username="user2")
        job = wait_for(manager, job_id)
        assert job["status"] == "completed"
        assert "result" not in job
        assert job["result_available"] is True
        assert job["result_row_count"] == 4
        assert job["columns"] == ["id"]
    finally:
        manager.shutdown()


def test_large_results_remain_available_through_bounded_pages():
    manager = ExecutionManager(max_workers=1, retention_seconds=60, inline_result_row_limit=3)
    try:
        job_id = manager.submit(lambda: make_result(7))
        wait_for(manager, job_id)
        first = manager.result_page(job_id, offset=0, limit=3)
        second = manager.result_page(job_id, offset=3, limit=3)
        third = manager.result_page(job_id, offset=6, limit=3)
        assert first["rows"] == [{"id": 0}, {"id": 1}, {"id": 2}]
        assert first["has_more"] is True
        assert second["rows"] == [{"id": 3}, {"id": 4}, {"id": 5}]
        assert second["has_more"] is True
        assert third["rows"] == [{"id": 6}]
        assert third["has_more"] is False
    finally:
        manager.shutdown()
