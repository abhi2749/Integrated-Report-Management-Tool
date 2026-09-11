import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from export_manager import ExportJobManager


def test_csv_export_consumes_iterator_incrementally(tmp_path):
    manager = ExportJobManager(tmp_path, max_workers=1, progress_interval=10)
    consumed = []

    def rows():
        for value in range(250):
            consumed.append(value)
            yield {"value": value}

    export_id = manager.submit(
        source_job_id="job-1",
        owner_user_id="user-1",
        fmt="csv",
        filename="large-report.csv",
        columns=["value"],
        row_iterator_factory=lambda: rows(),
        total_rows=250,
    )
    manager._executor.shutdown(wait=True)
    status = manager.get(export_id)
    assert status["status"] == "completed"
    assert status["processed_rows"] == 250
    assert len(consumed) == 250
    path = manager.path_for_completed(export_id)[1]
    assert path.read_text(encoding="utf-8").splitlines()[:2] == ["value", "0"]


def test_json_export_does_not_require_result_list(tmp_path):
    manager = ExportJobManager(tmp_path, max_workers=1, progress_interval=7)

    def rows():
        for value in range(100):
            yield {"value": value}

    export_id = manager.submit(
        source_job_id="job-2",
        owner_user_id="user-2",
        fmt="json",
        filename="large-report.json",
        columns=["value"],
        row_iterator_factory=rows,
        total_rows=100,
    )
    manager._executor.shutdown(wait=True)
    status = manager.get(export_id)
    assert status["status"] == "completed"
    assert status["processed_rows"] == 100
    payload = manager.path_for_completed(export_id)[1].read_text(encoding="utf-8")
    assert '"value":0' in payload
    assert '"value":99' in payload


def test_export_cancellation_stops_generator_and_removes_partial_file(tmp_path):
    manager = ExportJobManager(tmp_path, max_workers=1, progress_interval=1)
    started = []

    def rows():
        for value in range(100000):
            started.append(value)
            yield {"value": value}
            if value == 20:
                manager.cancel(export_id)

    export_id = manager.submit(
        source_job_id="job-3",
        owner_user_id="user-3",
        fmt="csv",
        filename="cancelled.csv",
        columns=["value"],
        row_iterator_factory=rows,
        total_rows=100000,
    )
    manager._executor.shutdown(wait=True)
    status = manager.get(export_id)
    assert status["status"] == "cancelled"
    assert not any(tmp_path.glob(f"{export_id}.*"))
