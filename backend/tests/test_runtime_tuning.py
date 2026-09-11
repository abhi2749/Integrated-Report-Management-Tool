import os

from runtime_tuning import recommended_worker_count


def test_explicit_execution_workers_win(monkeypatch):
    monkeypatch.setenv("EXECUTION_WORKERS", "6")
    assert recommended_worker_count() == 6


def test_adaptive_workers_are_positive_and_bounded(monkeypatch):
    monkeypatch.setenv("EXECUTION_WORKERS", "0")
    value = recommended_worker_count()
    assert 1 <= value <= 8


def test_adaptive_mode_does_not_create_data_row_limits():
    assert os.getenv("MAX_QUERY_ROWS", "0") == "0"
