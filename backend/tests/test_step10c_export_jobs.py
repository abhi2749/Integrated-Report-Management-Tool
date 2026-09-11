from __future__ import annotations

import time
from pathlib import Path

from export_manager import ExportJobManager


def wait_for(manager, export_id, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = manager.get(export_id)
        if job and job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.01)
    raise AssertionError("export job did not finish")


def test_csv_export_job_writes_complete_file(tmp_path: Path):
    manager = ExportJobManager(tmp_path, max_workers=1, retention_seconds=60)
    export_id = manager.submit(
        source_job_id="job-1",
        owner_user_id="u1",
        fmt="csv",
        filename="report.csv",
        columns=["id", "name"],
        row_iterator_factory=lambda: iter(
            [{"id": i, "name": f"row-{i}"} for i in range(25)]
        ),
        total_rows=25,
    )
    job = wait_for(manager, export_id)
    assert job["status"] == "completed"
    assert job["processed_rows"] == 25
    assert job["progress"] == 100
    meta_path = manager.path_for_completed(export_id)
    assert meta_path is not None
    _, path = meta_path
    text = path.read_text(encoding="utf-8")
    assert text.count("\n") == 26
    assert "row-24" in text


def test_json_export_job_writes_complete_file(tmp_path: Path):
    manager = ExportJobManager(tmp_path, max_workers=1, retention_seconds=60)
    export_id = manager.submit(
        source_job_id="job-1",
        owner_user_id="u1",
        fmt="json",
        filename="report.json",
        columns=["id"],
        row_iterator_factory=lambda: iter([{"id": i} for i in range(12)]),
        total_rows=12,
    )
    job = wait_for(manager, export_id)
    assert job["status"] == "completed"
    _, path = manager.path_for_completed(export_id)
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["rows"]) == 12
    assert data["total_rows"] == 12


def test_export_job_cancellation(tmp_path: Path):
    manager = ExportJobManager(tmp_path, max_workers=1, retention_seconds=60)

    def rows():
        for i in range(100000):
            yield {"id": i}

    export_id = manager.submit(
        source_job_id="job-1",
        owner_user_id="u1",
        fmt="csv",
        filename="report.csv",
        columns=["id"],
        row_iterator_factory=rows,
        total_rows=100000,
    )
    manager.cancel(export_id)
    job = wait_for(manager, export_id)
    assert job["status"] == "cancelled"
