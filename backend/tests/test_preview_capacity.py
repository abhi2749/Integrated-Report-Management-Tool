from pathlib import Path


def test_connector_previews_have_no_application_row_ceiling():
    root = Path(__file__).parents[1]
    for name in ("mysql.py", "clickhouse.py", "mongodb.py"):
        source = (root / "connectors" / name).read_text(encoding="utf-8")
        assert "min(int(sample_limit), MAX_PREVIEW_ROWS)" not in source
        assert "min(int(sample_limit), 100)" not in source


def test_capacity_endpoint_advertises_unbounded_preview_policy():
    source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
    assert '"preview_rows": MAX_PREVIEW_ROWS' in source


def test_import_preview_has_no_fixed_100_row_ceiling():
    source = (Path(__file__).parents[1] / "import_service.py").read_text(encoding="utf-8")
    assert "min(limit, 100)" not in source
