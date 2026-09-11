from pathlib import Path

import config

ROOT = Path(__file__).resolve().parents[1]


def test_911k_plus_is_not_an_application_ceiling():
    assert config.MAX_PREVIEW_ROWS == 0
    assert config.MAX_QUERY_ROWS == 0
    assert config.QUERY_TIMEOUT_SECONDS == 0


def test_report_and_preview_limits_do_not_encode_911k_or_excel_row_ceiling():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "limit: int = 0  # 0 = no application row ceiling" in main
    assert "1048576" not in main
    assert "911603" not in main


def test_streaming_result_boundary_remains_disk_backed():
    source = (ROOT / "execution_manager.py").read_text(encoding="utf-8")
    assert "result.get(\"streaming_rows\") is not None" in source
    assert "self.result_pipeline.ingest(" in source


def test_join_stream_has_spill_and_cancellation_controls():
    join = (ROOT / "join_engine.py").read_text(encoding="utf-8")
    database = (ROOT / "database.py").read_text(encoding="utf-8")
    assert "TemporaryDirectory(prefix=\"reportingtool_join_\")" in join
    assert "max_memory_bytes: int | None = None" in join
    assert "cancel_event=cancel_event" in database


def test_clickhouse_stream_cancellation_is_propagated():
    source = (ROOT / "database.py").read_text(encoding="utf-8")
    assert "pushdown_aggregations=aggregations or [], cancel_event=cancel_event" in source


def test_application_name_is_integrated_report_management_tool():
    config_source = (ROOT / "config.py").read_text(encoding="utf-8")
    app_source = (ROOT.parent / "frontend-ui" / "src" / "App.jsx").read_text(encoding="utf-8")
    html_source = (ROOT.parent / "frontend-ui" / "index.html").read_text(encoding="utf-8")
    expected = "Integrated Report Management Tool"
    assert expected in config_source
    assert expected in app_source
    assert expected in html_source
