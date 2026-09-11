from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "main.py"


def test_legacy_csv_export_uses_execution_job_pipeline():
    source = MAIN.read_text(encoding="utf-8")
    block = source[source.index('@app.post("/report/export/csv"'):source.index('@app.post("/datasource/mysql/test"')]
    assert "EXECUTION_MANAGER.submit(" in block
    assert "execute_report_query(" not in block
    assert "_stream_job_export(job_id, \"csv\"" in block


def test_job_csv_json_exports_use_result_iterator():
    source = MAIN.read_text(encoding="utf-8")
    start = source.index('def _stream_job_export(')
    end = source.index('@app.post("/execution/jobs/{job_id}/export"', start)
    helper = source[start:end]
    assert "EXECUTION_MANAGER.iter_result_rows(job_id)" in helper
    assert "csv_stream_rows" in helper
    assert "json_stream_rows" in helper


def test_legacy_job_exports_do_not_reexecute_full_result():
    source = MAIN.read_text(encoding="utf-8")
    start = source.index('@app.get("/execution/jobs/{job_id}/export/csv"')
    end = source.index('def _build_report_pdf', start)
    block = source[start:end]
    assert "_execute_full_export(" not in block
    assert "_stream_job_export(" in block
