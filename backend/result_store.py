from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

DEFAULT_PAGE_SIZE = 5000
# Compatibility symbol: there is intentionally no application maximum page size.
MAX_PAGE_SIZE = None


def _default_db_path() -> Path:
    from config import EXECUTION_RESULT_DB_PATH
    return EXECUTION_RESULT_DB_PATH


def _json_default(value: Any) -> str:
    return str(value)


class ExecutionResultStore:
    """Disk-backed, page-addressable execution result store.

    Results are kept outside the ExecutionManager process heap once persisted.
    SQLite is used deliberately because it is already part of the deployment
    contract and requires no additional service, driver, or license.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path).expanduser().resolve() if path else _default_db_path()
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
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_results (
                    result_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL UNIQUE,
                    columns_json TEXT NOT NULL,
                    total_rows INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_result_rows (
                    result_id TEXT NOT NULL,
                    row_number INTEGER NOT NULL,
                    row_json TEXT NOT NULL,
                    PRIMARY KEY (result_id, row_number),
                    FOREIGN KEY (result_id) REFERENCES execution_results(result_id)
                        ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_execution_result_rows_lookup "
                "ON execution_result_rows(result_id, row_number)"
            )
            connection.commit()

    def replace_result(self, job_id: str, result: dict[str, Any]) -> dict[str, Any]:
        rows = result.get("rows") if isinstance(result.get("rows"), list) else []
        columns = result.get("columns") if isinstance(result.get("columns"), list) else []
        result_id = uuid.uuid4().hex
        total_rows = result.get("total_rows")
        try:
            total_rows = max(0, int(total_rows)) if total_rows is not None else len(rows)
        except (TypeError, ValueError):
            total_rows = len(rows)

        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("DELETE FROM execution_results WHERE job_id = ?", (job_id,))
            connection.execute(
                "INSERT INTO execution_results(result_id, job_id, columns_json, total_rows) VALUES (?, ?, ?, ?)",
                (result_id, job_id, json.dumps(columns, ensure_ascii=False, default=_json_default), total_rows),
            )
            batch: list[tuple[str, int, str]] = []
            for row_number, row in enumerate(rows):
                payload = row if isinstance(row, dict) else {}
                batch.append((result_id, row_number, json.dumps(payload, ensure_ascii=False, default=_json_default, separators=(",", ":"))))
                if len(batch) >= 1000:
                    connection.executemany(
                        "INSERT INTO execution_result_rows(result_id, row_number, row_json) VALUES (?, ?, ?)",
                        batch,
                    )
                    batch.clear()
            if batch:
                connection.executemany(
                    "INSERT INTO execution_result_rows(result_id, row_number, row_json) VALUES (?, ?, ?)",
                    batch,
                )
            connection.commit()

        return {
            "result_id": result_id,
            "total_rows": total_rows,
            "columns": columns,
        }

    def ingest(self, job_id: str, rows, columns: list[str] | None = None, total_rows: int | None = None, cancel_event=None) -> dict[str, Any]:
        """Persist a row stream incrementally so pages become readable early.

        A single SQLite connection is reused for the whole ingest. Each bounded
        batch is committed while the store lock is held only for that short
        write window, preserving WAL reader concurrency without repeatedly
        opening connections for every batch.
        """
        result_id = uuid.uuid4().hex
        columns_list = [str(c) for c in (columns or [])]
        count = 0
        connection = self._connect()
        try:
            with self._lock:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("DELETE FROM execution_results WHERE job_id = ?", (job_id,))
                connection.execute(
                    "INSERT INTO execution_results(result_id, job_id, columns_json, total_rows) VALUES (?, ?, ?, ?)",
                    (result_id, job_id, json.dumps(columns_list, ensure_ascii=False), 0),
                )
                connection.commit()

            batch: list[tuple[str, int, str]] = []

            def flush() -> None:
                nonlocal batch
                if not batch:
                    return
                with self._lock:
                    connection.executemany(
                        "INSERT INTO execution_result_rows(result_id, row_number, row_json) VALUES (?, ?, ?)",
                        batch,
                    )
                    connection.execute(
                        "UPDATE execution_results SET columns_json = ?, total_rows = ? WHERE result_id = ?",
                        (json.dumps(columns_list, ensure_ascii=False), count, result_id),
                    )
                    connection.commit()
                batch = []

            for row in rows:
                if cancel_event is not None and cancel_event.is_set():
                    raise InterruptedError("Execution cancelled")
                payload = row if isinstance(row, dict) else {}
                if not columns_list:
                    columns_list = [str(k) for k in payload.keys()]
                batch.append(
                    (
                        result_id,
                        count,
                        json.dumps(payload, ensure_ascii=False, default=_json_default, separators=(",", ":")),
                    )
                )
                count += 1
                if len(batch) >= 1000:
                    flush()

            flush()
            final_total = count if total_rows is None else max(count, int(total_rows))
            with self._lock:
                connection.execute(
                    "UPDATE execution_results SET columns_json = ?, total_rows = ? WHERE result_id = ?",
                    (json.dumps(columns_list, ensure_ascii=False), final_total, result_id),
                )
                connection.commit()

            return {
                "result_id": result_id,
                "total_rows": final_total,
                "returned_rows": 0,
                "columns": columns_list,
            }
        finally:
            connection.close()

    def get_metadata(self, job_id: str) -> dict[str, Any] | None:
        """Return lightweight result metadata without reading result rows."""
        with self._lock, self._connect() as connection:
            meta = connection.execute(
                "SELECT result_id, columns_json, total_rows FROM execution_results WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if meta is None:
                return None
            return {
                "result_id": meta["result_id"],
                "columns": json.loads(meta["columns_json"] or "[]"),
                "total_rows": int(meta["total_rows"] or 0),
            }

    def get_page(self, job_id: str, offset: int = 0, limit: int = DEFAULT_PAGE_SIZE) -> dict[str, Any] | None:
        offset = max(0, int(offset))
        limit = max(1, int(limit))
        with self._lock, self._connect() as connection:
            meta = connection.execute(
                "SELECT result_id, columns_json, total_rows FROM execution_results WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if meta is None:
                return None
            columns = json.loads(meta["columns_json"] or "[]")
            records = connection.execute(
                "SELECT row_json FROM execution_result_rows WHERE result_id = ? "
                "AND row_number >= ? ORDER BY row_number LIMIT ?",
                (meta["result_id"], offset, limit),
            ).fetchall()
            rows = [json.loads(record["row_json"]) for record in records]
            total_rows = int(meta["total_rows"])
            return {
                "ready": True,
                "status": "completed",
                "rows": rows,
                "columns": columns,
                "total_rows": total_rows,
                "returned_rows": len(rows),
                "materialized_rows": total_rows,
                "offset": offset,
                "limit": limit,
                "has_more": offset + len(rows) < total_rows,
            }

    def iter_rows(self, job_id: str):
        """Yield stored rows with bounded fetches and no store-wide lock held."""
        with self._lock:
            connection = self._connect()
            meta = connection.execute(
                "SELECT result_id FROM execution_results WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if meta is None:
            connection.close()
            return

        try:
            cursor = connection.execute(
                "SELECT row_json FROM execution_result_rows "
                "WHERE result_id = ? ORDER BY row_number",
                (meta["result_id"],),
            )
            while True:
                records = cursor.fetchmany(1000)
                if not records:
                    break
                for record in records:
                    yield json.loads(record["row_json"])
        finally:
            connection.close()

    def delete(self, job_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("DELETE FROM execution_results WHERE job_id = ?", (job_id,))
            connection.commit()

    def cleanup_jobs(self, job_ids: list[str]) -> None:
        if not job_ids:
            return
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.executemany("DELETE FROM execution_results WHERE job_id = ?", ((job_id,) for job_id in job_ids))
            connection.commit()


EXECUTION_RESULT_STORE = ExecutionResultStore()
