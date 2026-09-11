"""
Basic project smoke tests.

These tests deliberately avoid starting FastAPI or opening database
connections. They are intended to catch broken imports/configuration before
a developer moves on to functional testing.
"""

import os

os.environ.setdefault("SECRET_KEY", "regression-test-secret-key-only")
os.environ.setdefault("ENCRYPTION_KEY", "9T7M5x5vR1p0w8c6y2n4z7a9s3d5f8g0h1j4k6m8p0r2t4v6x8z0=")


def test_main_module_imports():
    import main  # noqa: F401


def test_security_module_imports():
    import security  # noqa: F401


def test_database_module_imports():
    import database  # noqa: F401


def test_execution_manager_imports():
    import execution_manager  # noqa: F401
