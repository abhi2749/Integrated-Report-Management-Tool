"""Metadata persistence abstraction with JSON and SQLite backends.

Change #7 activates SQLite as the default metadata store while preserving the
existing JSON files as a migration source and emergency fallback.

The repository stores each metadata item as JSON payload inside SQLite. This
keeps the existing registry object shapes and IDs intact while giving the
application transactional, single-file metadata persistence.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json
import os
import shutil
import sqlite3


class MetadataRepository(ABC):
    @abstractmethod
    def read(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def write(self, items: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def ensure(self) -> None:
        raise NotImplementedError


class JsonMetadataRepository(MetadataRepository):
    """Atomic JSON-file implementation retained for fallback compatibility."""
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path).resolve()

    def ensure(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def read(self) -> list[dict[str, Any]]:
        self.ensure()
        try:
            value = json.loads(self.file_path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def write(self, items: list[dict[str, Any]]) -> None:
        self.ensure()
        temp = self.file_path.with_suffix(self.file_path.suffix + ".tmp")
        temp.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.file_path)


class SqliteMetadataRepository(MetadataRepository):
    """SQLite implementation using one transactional metadata database."""
    def __init__(self, db_path: str | Path, collection: str, legacy_file: str | Path | None = None):
        self.db_path = Path(db_path).resolve()
        self.collection = str(collection).strip()
        self.legacy_file = Path(legacy_file).resolve() if legacy_file else None
        if not self.collection:
            raise ValueError("Metadata collection is required.")

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.db_path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def ensure(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata_records (
                    collection TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (collection, item_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_metadata_records_collection "
                "ON metadata_records(collection)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata_migrations (
                    collection TEXT PRIMARY KEY,
                    legacy_file TEXT,
                    migrated_at TEXT NOT NULL,
                    item_count INTEGER NOT NULL
                )
                """
            )

    def _legacy_items(self) -> list[dict[str, Any]]:
        if not self.legacy_file or not self.legacy_file.exists():
            return []
        try:
            value = json.loads(self.legacy_file.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Unable to read legacy metadata file: {self.legacy_file}"
            ) from exc

    def _migrate_if_needed(self) -> None:
        self.ensure()
        with self._connect() as conn:
            migration = conn.execute(
                "SELECT 1 FROM metadata_migrations WHERE collection = ?",
                (self.collection,),
            ).fetchone()
            count = conn.execute(
                "SELECT COUNT(*) AS count FROM metadata_records WHERE collection = ?",
                (self.collection,),
            ).fetchone()["count"]

            if migration or count:
                return

            items = self._legacy_items()
            if not items:
                conn.execute(
                    "INSERT OR REPLACE INTO metadata_migrations "
                    "(collection, legacy_file, migrated_at, item_count) VALUES (?, ?, ?, ?)",
                    (
                        self.collection,
                        str(self.legacy_file) if self.legacy_file else None,
                        datetime.now(timezone.utc).isoformat(),
                        0,
                    ),
                )
                return

            backup_path = self.legacy_file.with_suffix(
                self.legacy_file.suffix + ".pre_sqlite.bak"
            ) if self.legacy_file else None
            if backup_path and not backup_path.exists():
                try:
                    shutil.copy2(self.legacy_file, backup_path)
                except OSError as exc:
                    raise RuntimeError(
                        f"Unable to create SQLite migration backup: {backup_path}"
                    ) from exc

            now = datetime.now(timezone.utc).isoformat()
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    raise RuntimeError(
                        f"Legacy metadata collection '{self.collection}' contains a non-object at index {index}."
                    )
                item_id = item.get("id")
                if item_id is None:
                    item_id = item.get("connection_id")
                if item_id is None:
                    raise RuntimeError(
                        f"Legacy metadata collection '{self.collection}' contains an item without an id."
                    )
                item_id = str(item_id)
                payload = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
                conn.execute(
                    """
                    INSERT INTO metadata_records
                    (collection, item_id, payload, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self.collection,
                        item_id,
                        payload,
                        item.get("created_at") or now,
                        item.get("updated_at") or now,
                    ),
                )

            conn.execute(
                "INSERT OR REPLACE INTO metadata_migrations "
                "(collection, legacy_file, migrated_at, item_count) VALUES (?, ?, ?, ?)",
                (
                    self.collection,
                    str(self.legacy_file) if self.legacy_file else None,
                    now,
                    len(items),
                ),
            )

    def read(self) -> list[dict[str, Any]]:
        self._migrate_if_needed()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM metadata_records WHERE collection = ? "
                "ORDER BY rowid ASC",
                (self.collection,),
            ).fetchall()
        result = []
        for row in rows:
            try:
                value = json.loads(row["payload"])
                if isinstance(value, dict):
                    result.append(value)
            except json.JSONDecodeError:
                continue
        return result

    def write(self, items: list[dict[str, Any]]) -> None:
        self._migrate_if_needed()
        now = datetime.now(timezone.utc).isoformat()
        normalized: list[tuple[str, str, str | None, str | None]] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"Metadata item at index {index} must be an object.")
            item_id = item.get("id")
            if item_id is None:
                item_id = item.get("connection_id")
            if item_id is None:
                raise ValueError(
                    f"Metadata collection '{self.collection}' requires an id or connection_id."
                )
            normalized.append(
                (
                    str(item_id),
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                    item.get("created_at") or now,
                    item.get("updated_at") or now,
                )
            )

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "DELETE FROM metadata_records WHERE collection = ?",
                (self.collection,),
            )
            conn.executemany(
                """
                INSERT INTO metadata_records
                (collection, item_id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [(self.collection, *item) for item in normalized],
            )


def create_metadata_repository(
    file_path: str | Path,
    *,
    backend: str | None = None,
    collection: str | None = None,
    db_path: str | Path | None = None,
) -> MetadataRepository:
    """Create the configured metadata repository.

    SQLite is the default in Change #7. Set METADATA_BACKEND=json to return to
    the previous JSON persistence behavior without changing registry callers.
    """
    selected = (backend or os.getenv("METADATA_BACKEND", "sqlite")).strip().lower()
    if selected == "json":
        return JsonMetadataRepository(file_path)
    if selected == "sqlite":
        if not collection:
            raise ValueError("SQLite metadata repositories require a collection name.")
        selected_db = db_path or os.getenv("METADATA_DB_FILE")
        if not selected_db:
            selected_db = Path(file_path).resolve().parent / "metadata.db"
        return SqliteMetadataRepository(selected_db, collection, file_path)
    raise RuntimeError(
        f"Unsupported METADATA_BACKEND '{selected}'. Supported values: sqlite, json."
    )
