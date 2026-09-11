from pathlib import Path


def test_report_query_defaults_to_unlimited_execution_window():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    assert "class ReportQueryRequest(BaseModel):" in source
    block = source.split("class ReportQueryRequest(BaseModel):", 1)[1].split("\ndef _report_datasets_for_execution", 1)[0]
    assert "limit: int = 0" in block


def test_execution_api_uses_job_id_as_public_result_handle():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    block = source[source.index('@app.post("/execution/jobs"'):source.index('@app.get("/execution/jobs"')]
    assert '"job_id": job_id' in block


def test_export_api_exposes_canonical_export_id():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    start = source.index('@app.post("/execution/jobs/{job_id}/export"')
    end = source.index('@app.get("/execution/exports/{export_id}"', start)
    block = source[start:end]
    assert '"export_id": export_id' in block
