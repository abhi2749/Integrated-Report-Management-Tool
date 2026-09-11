import os

from export_manager import ExportJobManager


def test_export_workers_adapt_when_unconfigured(monkeypatch, tmp_path):
    monkeypatch.setenv("EXECUTION_WORKERS", "3")
    manager = ExportJobManager(tmp_path)
    try:
        assert manager.max_workers == 3
    finally:
        manager._executor.shutdown(wait=True)


def test_explicit_export_workers_remain_authoritative(tmp_path):
    manager = ExportJobManager(tmp_path, max_workers=2)
    try:
        assert manager.max_workers == 2
    finally:
        manager._executor.shutdown(wait=True)


def test_adaptive_export_workers_are_positive(monkeypatch, tmp_path):
    monkeypatch.setenv("EXECUTION_WORKERS", "0")
    manager = ExportJobManager(tmp_path)
    try:
        assert manager.max_workers >= 1
    finally:
        manager._executor.shutdown(wait=True)
