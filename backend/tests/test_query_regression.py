"""
Regression smoke tests for the query-related modules that actually exist
in the current Reporting Tool baseline.

IMPORTANT:
This file intentionally does NOT import `query_engine`.
The current baseline does not contain query_engine.py, so requiring that
module would make the test suite fail even when the application is fine.
"""

import importlib.util
import os

os.environ.setdefault("SECRET_KEY", "regression-test-secret-key-only")
os.environ.setdefault(
    "ENCRYPTION_KEY",
    "9T7M5x5vR1p0w8c6y2n4z7a9s3d5f8g0h1j4k6m8p0r2t4v6x8z0=",
)


def test_join_engine_imports():
    """The existing JOIN engine module must remain importable."""
    import join_engine  # noqa: F401


def test_query_pushdown_imports():
    """The existing query pushdown module must remain importable."""
    import query_pushdown  # noqa: F401


def test_existing_query_modules_are_available():
    """Verify the actual baseline query modules are available."""
    assert importlib.util.find_spec("join_engine") is not None
    assert importlib.util.find_spec("query_pushdown") is not None
