from pathlib import Path

from dashboard_export import build_dashboard_pdf, build_dashboard_xlsx, build_dashboard_package

ROOT = Path(__file__).resolve().parents[2]


def _sample():
    item = {
        "id": "dash_test",
        "name": "Operations Dashboard",
        "owner_username": "admin",
        "version": 1,
        "definition": {
            "execution_job_id": "job_test",
            "filters": [],
            "widgets": [
                {"id": "k1", "type": "kpi", "title": "Total", "y": "value", "span": 6},
                {"id": "b1", "type": "bar", "title": "By Category", "x": "category", "y": "value", "span": 6},
                {"id": "l1", "type": "line", "title": "Trend", "x": "category", "y": "value", "span": 6},
                {"id": "p1", "type": "pie", "title": "Mix", "x": "category", "y": "value", "span": 6},
                {"id": "t1", "type": "table", "title": "Data Table", "span": 12},
            ],
        },
    }
    job = {
        "status": "completed",
        "result": {
            "columns": ["category", "value"],
            "rows": [
                {"category": "A", "value": 10},
                {"category": "B", "value": 20},
                {"category": "C", "value": 30},
            ],
        },
    }
    return item, job


def test_dashboard_excel_export_contains_workbook_bytes():
    payload = build_dashboard_xlsx(*_sample())
    assert payload.startswith(b"PK")
    assert len(payload) > 1000


def test_dashboard_package_contains_all_exports():
    import zipfile
    import io
    payload = build_dashboard_package(*_sample())
    assert payload.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = set(archive.namelist())
    assert names == {"dashboard-dash_test.json", "dashboard-dash_test.csv", "dashboard-dash_test.xlsx", "dashboard-dash_test.pdf"}


def test_dashboard_pdf_export_contains_pdf_bytes():
    payload = build_dashboard_pdf(*_sample())
    assert payload.startswith(b"%PDF")
    assert len(payload) > 1000


def test_dashboard_exports_are_exposed_by_backend_and_ui():
    backend = (ROOT / "backend" / "main.py").read_text()
    dashboard = (ROOT / "frontend-ui" / "src" / "Dashboard.jsx").read_text()
    saved = (ROOT / "frontend-ui" / "src" / "SavedDashboards.jsx").read_text()
    assert '/dashboards/{dashboard_id}/export/xlsx' in backend
    assert '/dashboards/{dashboard_id}/export/pdf' in backend
    assert '/dashboards/{dashboard_id}/export/package' in backend
    assert 'Export Excel' in dashboard
    assert 'Export PDF' in dashboard
    assert 'Grant Access' in dashboard
    assert 'Shares' not in dashboard
    assert 'Download Package' in dashboard
    assert 'Export Excel' in saved
    assert 'Export PDF' in saved


def test_dashboard_large_result_uses_result_store_iterator(monkeypatch):
    import dashboard_export
    import zipfile
    import io

    class FakeManager:
        def get(self, job_id):
            return {
                "id": job_id,
                "status": "completed",
                "result_total_rows": 3,
                "result_returned_rows": 0,
                "result_columns": ["category", "value"],
                "result_available": True,
            }

        def iter_result_rows(self, job_id):
            return iter([
                {"category": "A", "value": 10},
                {"category": "B", "value": 20},
                {"category": "C", "value": 30},
            ])

    monkeypatch.setattr(dashboard_export, "EXECUTION_MANAGER", FakeManager())
    item, _ = _sample()
    job = {"id": "job_disk", "status": "completed"}

    payload = dashboard_export.build_dashboard_xlsx(item, job)
    assert payload.startswith(b"PK")
    assert len(payload) > 1000

    package = dashboard_export.build_dashboard_package(item, job)
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        csv_text = archive.read("dashboard-dash_test.csv").decode("utf-8-sig")
    assert "category,value" in csv_text
    assert "A,10" in csv_text
    assert "C,30" in csv_text


def test_dashboard_result_metadata_survives_without_inline_rows(monkeypatch):
    import dashboard_export

    class FakeManager:
        def get(self, job_id):
            return {
                "id": job_id,
                "status": "completed",
                "result_total_rows": 911603,
                "result_columns": [f"c{i}" for i in range(123)],
                "result_available": True,
            }

        def iter_result_rows(self, job_id):
            return iter(())

    monkeypatch.setattr(dashboard_export, "EXECUTION_MANAGER", FakeManager())
    result = dashboard_export._result_from_job({"id": "job_large", "status": "completed"})
    assert result["total_rows"] == 911603
    assert len(result["columns"]) == 123
