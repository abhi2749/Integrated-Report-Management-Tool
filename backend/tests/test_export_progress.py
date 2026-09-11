from pathlib import Path
from export_manager import ExportJobManager


def test_export_progress_updates_before_completion(tmp_path: Path):
    manager = ExportJobManager(tmp_path, max_workers=1, retention_seconds=60)
    export_id = manager.submit(
        source_job_id="job-1", owner_user_id="u1", fmt="csv", filename="report.csv",
        columns=["id"], row_iterator_factory=lambda: iter({"id": i} for i in range(250)), total_rows=250,
    )
    import time
    deadline = time.time() + 5
    seen = False
    while time.time() < deadline:
        job = manager.get(export_id)
        if job and job["processed_rows"] >= 100:
            seen = True
            break
        time.sleep(0.01)
    assert seen
