from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


def _default_path() -> Path:
    from config import EXECUTION_JOB_DB_PATH
    return EXECUTION_JOB_DB_PATH


class PersistentJobStore:
    """Small SQLite metadata store for execution/export jobs.

    Result rows and export files remain in their existing durable stores. This
    database only makes job identity, ownership, state and recovery metadata
    survive a backend process/container restart without adding another service.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path).expanduser().resolve() if path else _default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    rows INTEGER NOT NULL DEFAULT 0,
                    result_total_rows INTEGER NOT NULL DEFAULT 0,
                    result_returned_rows INTEGER NOT NULL DEFAULT 0,
                    result_columns_json TEXT NOT NULL DEFAULT '[]',
                    result_json TEXT,
                    error TEXT,
                    owner_user_id TEXT,
                    owner_username TEXT,
                    query_payload_json TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS export_jobs (
                    id TEXT PRIMARY KEY,
                    source_job_id TEXT NOT NULL,
                    owner_user_id TEXT,
                    owner_username TEXT,
                    format TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    total_rows INTEGER NOT NULL DEFAULT 0,
                    processed_rows INTEGER NOT NULL DEFAULT 0,
                    progress INTEGER,
                    file_size INTEGER NOT NULL DEFAULT 0,
                    file_path TEXT NOT NULL,
                    error TEXT
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_execution_jobs_owner ON execution_jobs(owner_user_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_execution_jobs_finished ON execution_jobs(finished_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_export_jobs_owner ON export_jobs(owner_user_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_export_jobs_finished ON export_jobs(finished_at)")
            connection.commit()

    @staticmethod
    def _json(value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))

    @staticmethod
    def _load_json(value: str | None, default: Any):
        if not value:
            return default
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default

    def save_execution(self, job: dict[str, Any]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO execution_jobs(
                    id,status,created_at,started_at,finished_at,rows,result_total_rows,
                    result_returned_rows,result_columns_json,result_json,error,owner_user_id,
                    owner_username,query_payload_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status, started_at=excluded.started_at,
                    finished_at=excluded.finished_at, rows=excluded.rows,
                    result_total_rows=excluded.result_total_rows,
                    result_returned_rows=excluded.result_returned_rows,
                    result_columns_json=excluded.result_columns_json,
                    result_json=excluded.result_json, error=excluded.error,
                    owner_user_id=excluded.owner_user_id, owner_username=excluded.owner_username,
                    query_payload_json=excluded.query_payload_json
                """,
                (
                    job["id"], job.get("status", "queued"), job["created_at"], job.get("started_at"),
                    job.get("finished_at"), int(job.get("rows") or 0), int(job.get("result_total_rows") or 0),
                    int(job.get("result_returned_rows") or 0), self._json(job.get("result_columns") or []),
                    self._json(job.get("result")), job.get("error"), job.get("owner_user_id"),
                    job.get("owner_username"), self._json(job.get("query_payload")),
                ),
            )
            connection.commit()

    def load_executions(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT * FROM execution_jobs ORDER BY created_at").fetchall()
        return [
            {
                "id": row["id"], "status": row["status"], "created_at": row["created_at"],
                "started_at": row["started_at"], "finished_at": row["finished_at"], "rows": row["rows"],
                "result_total_rows": row["result_total_rows"], "result_returned_rows": row["result_returned_rows"],
                "result_columns": self._load_json(row["result_columns_json"], []),
                "result": self._load_json(row["result_json"], None), "error": row["error"],
                "owner_user_id": row["owner_user_id"], "owner_username": row["owner_username"],
                "query_payload": self._load_json(row["query_payload_json"], None),
            }
            for row in rows
        ]

    def delete_execution(self, job_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM execution_jobs WHERE id = ?", (job_id,))
            connection.commit()

    def save_export(self, job: dict[str, Any]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO export_jobs(
                    id,source_job_id,owner_user_id,owner_username,format,filename,status,
                    created_at,started_at,finished_at,total_rows,processed_rows,progress,
                    file_size,file_path,error
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    source_job_id=excluded.source_job_id, owner_user_id=excluded.owner_user_id,
                    owner_username=excluded.owner_username, format=excluded.format,
                    filename=excluded.filename, status=excluded.status, started_at=excluded.started_at,
                    finished_at=excluded.finished_at, total_rows=excluded.total_rows,
                    processed_rows=excluded.processed_rows, progress=excluded.progress,
                    file_size=excluded.file_size, file_path=excluded.file_path, error=excluded.error
                """,
                (
                    job["id"], job["source_job_id"], job.get("owner_user_id"), job.get("owner_username", ""),
                    job["format"], job["filename"], job["status"], job["created_at"], job.get("started_at"),
                    job.get("finished_at"), int(job.get("total_rows") or 0), int(job.get("processed_rows") or 0),
                    job.get("progress"), int(job.get("file_size") or 0), job["file_path"], job.get("error"),
                ),
            )
            connection.commit()

    def load_exports(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT * FROM export_jobs ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]

    def delete_export(self, export_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM export_jobs WHERE id = ?", (export_id,))
            connection.commit()
