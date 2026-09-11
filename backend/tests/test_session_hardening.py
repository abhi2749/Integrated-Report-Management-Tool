import os
from pathlib import Path

import pytest

os.environ.setdefault("SECRET_KEY", "step7c-test-secret-" + "x" * 40)
os.environ.setdefault("ENCRYPTION_KEY", "9T7M5x5vR1p0w8c6y2n4z7a9s3d5f8g0h1j4k6m8p0r2t4v6x8z0=")

import auth_session_registry as registry
from auth import create_access_token, verify_access_token


@pytest.fixture
def isolated_session_db(tmp_path: Path):
    old_data_dir = registry.DATA_DIR
    old_session_db = registry.SESSION_DB
    registry.DATA_DIR = tmp_path
    registry.SESSION_DB = tmp_path / "auth_sessions.db"
    try:
        yield
    finally:
        registry.DATA_DIR = old_data_dir
        registry.SESSION_DB = old_session_db


def test_new_tokens_include_unique_session_identifier():
    first = create_access_token("user-1", "alice")
    second = create_access_token("user-1", "alice")

    assert first != second
    first_claims = verify_access_token(first)
    second_claims = verify_access_token(second)
    assert first_claims["user_id"] == "user-1"
    assert second_claims["user_id"] == "user-1"


def test_user_session_revocation_revokes_all_registered_sessions(isolated_session_db):
    first = create_access_token("user-1", "alice")
    second = create_access_token("user-1", "alice")
    other = create_access_token("user-2", "bob")

    first_expiry = verify_access_token(first)["expires_at"]
    second_expiry = verify_access_token(second)["expires_at"]
    other_expiry = verify_access_token(other)["expires_at"]

    registry.register_token(first, "user-1", first_expiry)
    registry.register_token(second, "user-1", second_expiry)
    registry.register_token(other, "user-2", other_expiry)

    assert registry.revoke_user_tokens("user-1") == 2
    assert registry.is_token_revoked(first) is True
    assert registry.is_token_revoked(second) is True
    assert registry.is_token_revoked(other) is False


def test_logout_removes_active_session_and_revokes_token(isolated_session_db):
    token = create_access_token("user-1", "alice")
    expiry = verify_access_token(token)["expires_at"]

    registry.register_token(token, "user-1", expiry)
    registry.revoke_token(token, expiry)

    assert registry.is_token_revoked(token) is True
    connection = registry._connect()
    try:
        count = connection.execute(
            "SELECT COUNT(*) FROM active_sessions WHERE token_hash = ?",
            (registry._hash_token(token),),
        ).fetchone()[0]
    finally:
        connection.close()
    assert count == 0


def test_expired_sessions_are_purged(isolated_session_db):
    token = create_access_token("user-1", "alice")
    registry.register_token(token, "user-1", 1)

    registry.purge_expired_tokens()

    connection = registry._connect()
    try:
        count = connection.execute("SELECT COUNT(*) FROM active_sessions").fetchone()[0]
    finally:
        connection.close()
    assert count == 0
