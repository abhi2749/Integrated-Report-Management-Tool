"""
Custom Reporting Tool
Security Phase - Step 3D: Authentication Session Registry

SQLite-backed session tracking and token revocation so logout, password changes,
and account deactivation can invalidate active sessions across Uvicorn reloads
and multiple worker processes on the same host.

The database is local to the backend deployment. For a horizontally
distributed deployment, use a shared database/session store in a later
infrastructure phase.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path


from config import DATA_DIR

BASE_DIR = Path(__file__).resolve().parent
SESSION_DB = DATA_DIR / "auth_sessions.db"

_LOCK = threading.Lock()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        SESSION_DB,
        timeout=10,
    )
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS revoked_tokens (
            token_hash TEXT PRIMARY KEY,
            expires_at INTEGER NOT NULL,
            revoked_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS active_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        );
        """
    )
    connection.commit()
    return connection


def _hash_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register_token(token: str, user_id: str, expires_at: int) -> None:
    if not token or not user_id:
        return

    now = int(time.time())

    with _LOCK:
        connection = _connect()
        try:
            connection.execute(
                """
                INSERT OR REPLACE INTO active_sessions
                (token_hash, user_id, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (_hash_token(token), str(user_id), int(expires_at), now),
            )
            connection.commit()
        finally:
            connection.close()


def revoke_token(token: str, expires_at: int) -> None:
    if not token:
        return

    now = int(time.time())

    with _LOCK:
        connection = _connect()
        try:
            connection.execute("DELETE FROM active_sessions WHERE token_hash = ?", (_hash_token(token),))
            connection.execute(
                """
                INSERT OR REPLACE INTO revoked_tokens
                (token_hash, expires_at, revoked_at)
                VALUES (?, ?, ?)
                """,
                (
                    _hash_token(token),
                    int(expires_at),
                    now,
                ),
            )
            connection.commit()
        finally:
            connection.close()


def is_token_revoked(token: str) -> bool:
    if not token:
        return False

    now = int(time.time())

    with _LOCK:
        connection = _connect()
        try:
            row = connection.execute(
                """
                SELECT 1
                FROM revoked_tokens
                WHERE token_hash = ?
                  AND expires_at > ?
                LIMIT 1
                """,
                (
                    _hash_token(token),
                    now,
                ),
            ).fetchone()

            return row is not None
        finally:
            connection.close()


def revoke_user_tokens(user_id: str) -> int:
    if not user_id:
        return 0

    with _LOCK:
        connection = _connect()
        try:
            rows = connection.execute(
                "SELECT token_hash, expires_at FROM active_sessions WHERE user_id = ?",
                (str(user_id),),
            ).fetchall()
            now = int(time.time())
            for token_hash, expires_at in rows:
                connection.execute(
                    "INSERT OR REPLACE INTO revoked_tokens (token_hash, expires_at, revoked_at) VALUES (?, ?, ?)",
                    (token_hash, int(expires_at), now),
                )
            connection.execute("DELETE FROM active_sessions WHERE user_id = ?", (str(user_id),))
            connection.commit()
            return len(rows)
        finally:
            connection.close()


def purge_expired_tokens() -> None:
    now = int(time.time())

    with _LOCK:
        connection = _connect()
        try:
            connection.execute(
                "DELETE FROM revoked_tokens WHERE expires_at <= ?",
                (now,),
            )
            connection.execute(
                "DELETE FROM active_sessions WHERE expires_at <= ?",
                (now,),
            )
            connection.commit()
        finally:
            connection.close()
