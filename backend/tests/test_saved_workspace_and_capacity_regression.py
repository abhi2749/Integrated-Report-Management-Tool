from pathlib import Path
from config import MAX_PREVIEW_ROWS

ROOT = Path(__file__).resolve().parents[2]

def test_preview_capacity_has_no_application_ceiling():
    assert MAX_PREVIEW_ROWS == 0

def test_saved_reports_has_explicit_management_controls():
    source = (ROOT / "frontend-ui" / "src" / "SavedReports.jsx").read_text()
    assert "selectedReportId" in source
    assert "Configure / Modify" in source
    assert "onOpenReportBuilder?.(selectedReportId)" in source

def test_saved_dashboard_is_a_separate_library():
    app = (ROOT / "frontend-ui" / "src" / "App.jsx").read_text()
    source = (ROOT / "frontend-ui" / "src" / "SavedDashboards.jsx").read_text()
    assert "saved-dashboards" in app
    assert "SavedDashboards" in app
    assert "DASHBOARD LIBRARY" in source

def test_mongodb_schema_discovery_not_hard_capped_at_100_documents():
    source = (ROOT / "backend" / "connectors" / "mongodb.py").read_text()
    assert "find().limit(MAX_PREVIEW_ROWS)" in source
