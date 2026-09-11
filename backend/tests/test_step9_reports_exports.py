from __future__ import annotations

import json
import zipfile
from pathlib import Path

from export_manager import ExportJobManager
from report_export_service import write_csv, write_json, write_xlsx, write_pdf, write_package


def _rows(count=25):
    for i in range(count):
        yield {"id": i, "name": f"row-{i}"}


def test_step9_streaming_export_formats_are_supported(tmp_path: Path):
    manager = ExportJobManager(tmp_path, max_workers=1, retention_seconds=60)
    try:
        for fmt in ("csv", "json", "xlsx", "pdf", "package"):
            writer = {
                "xlsx": lambda p, c, f, j, x: write_xlsx(p, c, f(), x),
                "pdf": lambda p, c, f, j, x: write_pdf(p, "Test Report", c, f(), x),
                "package": lambda p, c, f, j, x: write_package(p, "Test Report", c, f, 25, x),
            }.get(fmt)
            export_id = manager.submit(
                source_job_id="job-1", owner_user_id="u1", fmt=fmt, filename=f"report.{fmt if fmt != 'package' else 'zip'}",
                columns=["id", "name"], row_iterator_factory=lambda: _rows(), total_rows=25, writer=writer,
            )
            import time
            deadline = time.time() + 10
            while time.time() < deadline:
                job = manager.get(export_id)
                if job and job["status"] in {"completed", "failed", "cancelled"}:
                    break
                time.sleep(0.01)
            assert job["status"] == "completed", job
            assert manager.path_for_completed(export_id) is not None
    finally:
        manager.shutdown()


def test_step9_xlsx_is_write_only_and_preserves_all_rows(tmp_path: Path):
    path = tmp_path / "report.xlsx"
    processed = write_xlsx(path, ["id", "name"], _rows(100), lambda: False)
    assert processed == 100
    assert path.stat().st_size > 1000


def test_step9_package_contains_all_four_formats(tmp_path: Path):
    path = tmp_path / "report.zip"
    processed = write_package(path, "Test Report", ["id", "name"], lambda: _rows(10), 10, lambda: False)
    assert processed == 10
    with zipfile.ZipFile(path) as archive:
        assert set(archive.namelist()) == {"report.csv", "report.json", "report.xlsx", "report.pdf"}
        payload = json.loads(archive.read("report.json"))
        assert payload["total_rows"] == 10
        assert len(payload["rows"]) == 10


def test_step9_cancellation_leaves_no_partial_artifact(tmp_path: Path):
    manager = ExportJobManager(tmp_path, max_workers=1, retention_seconds=60)
    try:
        export_id = manager.submit(
            source_job_id="job-1", owner_user_id="u1", fmt="xlsx", filename="cancel.xlsx",
            columns=["id"], row_iterator_factory=lambda: _rows(100000), total_rows=100000,
            writer=lambda p, c, f, j, x: write_xlsx(p, c, f(), x),
        )
        manager.cancel(export_id)
        import time
        deadline = time.time() + 10
        while time.time() < deadline:
            job = manager.get(export_id)
            if job and job["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.01)
        assert job["status"] == "cancelled"
        assert not list(tmp_path.glob("*.xlsx"))
        assert not list(tmp_path.glob(".*.xlsx.part"))
    finally:
        manager.shutdown()


def test_step9_saved_report_export_route_and_format_contract():
    source = Path(__file__).resolve().parents[1] / "main.py"
    text = source.read_text(encoding="utf-8")
    assert '@app.post("/reports/{report_id}/export/{format}"' in text
    assert '"xlsx", "pdf", "package"' in text
    assert '_require_job_access(str(execution_job_id), user)' in text


def test_step9_frontend_exposes_full_report_export_set():
    root = Path(__file__).resolve().parents[2]
    client = (root / "frontend-ui/src/executionClient.js").read_text(encoding="utf-8")
    builder = (root / "frontend-ui/src/ReportBuilder.jsx").read_text(encoding="utf-8")
    saved = (root / "frontend-ui/src/SavedReports.jsx").read_text(encoding="utf-8")
    for fmt in ("csv", "json", "xlsx", "pdf", "package"):
        assert fmt in client
    for label in ("Export CSV", "Export JSON", "Export Excel", "Export PDF", "Download Package"):
        assert label in builder
    for label in ("CSV", "JSON", "Excel", "PDF", "Package"):
        assert label in saved
    assert "cancelExecutionExportJob" in client
    assert "AbortError" in client
