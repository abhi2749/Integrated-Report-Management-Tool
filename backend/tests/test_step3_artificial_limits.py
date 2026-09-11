from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_unbounded_defaults():
    import config
    assert config.MAX_QUERY_ROWS == 0
    assert config.MAX_EXPORT_FILE_MB == 0
    assert config.MAX_IMPORT_FILE_MB == 0
    assert config.MAX_REQUEST_BODY_MB == 0
    assert config.MAX_JOIN_OPERATIONS == 0
    assert config.MAX_JOIN_DATASETS == 0
    assert config.MAX_VISUALIZATION_ROWS == 0
    assert config.MAX_PREVIEW_ROWS == 0
    assert config.QUERY_TIMEOUT_SECONDS == 0


def test_legacy_report_execution_fallback_is_unbounded():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'data.get("limit", 0)' in source
    assert 'data.get("limit", 5000)' not in source


def test_join_designer_does_not_use_excel_as_application_limit():
    source = (ROOT.parent / "frontend-ui" / "src" / "JoinDesigner.jsx").read_text(encoding="utf-8")
    assert "MAX_WORKSHEET_ROWS" not in source
    assert "max={MAX_WORKSHEET_ROWS}" not in source
    assert "0 = full result" in source


def test_worksheet_limits_are_format_limits_only():
    source = (ROOT.parent / "frontend-ui" / "src" / "worksheetLimits.js").read_text(encoding="utf-8")
    assert "EXCEL_MAX_ROWS" in source
    assert "EXCEL_MAX_COLUMNS" in source
    assert "MAX_WORKSHEET_ROWS" not in source
