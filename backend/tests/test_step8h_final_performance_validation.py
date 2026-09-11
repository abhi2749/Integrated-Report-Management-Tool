from pathlib import Path


def _read(name: str) -> str:
    return (Path(__file__).resolve().parents[1] / name).read_text(encoding="utf-8")


def test_step8h_no_artificial_runtime_data_caps_are_introduced():
    """Validate the effective runtime configuration, not source formatting."""
    import config

    expected_unbounded = (
        "MAX_QUERY_ROWS",
        "MAX_EXPORT_FILE_MB",
        "MAX_REQUEST_BODY_MB",
        "MAX_JOIN_OPERATIONS",
        "MAX_VISUALIZATION_ROWS",
        "MAX_JOIN_DATASETS",
    )
    for setting in expected_unbounded:
        assert getattr(config, setting) == 0, (
            f"Artificial cap introduced or setting changed: {setting}"
        )
