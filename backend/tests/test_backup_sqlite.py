from __future__ import annotations

import json
import sqlite3
import tarfile
from pathlib import Path


def _load_module(tmp_path, monkeypatch):
    monkeypatch.setenv("METADATA_BACKEND", "sqlite")
    db = tmp_path / "data" / "metadata.db"
    db.parent.mkdir(parents=True)
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE metadata_records (collection TEXT, item_id TEXT, payload TEXT, created_at TEXT, updated_at TEXT)")
        conn.execute("INSERT INTO metadata_records VALUES ('users','u1','{}','now','now')")
        conn.commit()
    monkeypatch.setenv("METADATA_DB_FILE", str(db))
    import importlib
    import sys
    sys.modules.pop("config", None)
    sys.modules.pop("backup_manager", None)
    sys.path.insert(0, "/mnt/data/final_audit/backend")
    sys.path.insert(0, str(Path(__file__).parents[1]))
    return importlib.import_module("backup_manager")


def test_sqlite_backup_contains_database_and_manifest(tmp_path, monkeypatch):
    mod = _load_module(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "BASE_DIR", tmp_path)
    monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(mod, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(mod, "SQLITE_STATE_FILE", tmp_path / "data" / "metadata.db")
    archive = mod.create_backup()
    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
        assert "data/metadata.db" in names
        manifest = json.loads(tar.extractfile("backup_manifest.json").read())
        assert manifest["metadata_backend"] == "sqlite"
        assert manifest["files"] == ["data/metadata.db"]


def test_sqlite_backup_recovery_validates_integrity(tmp_path, monkeypatch):
    mod = _load_module(tmp_path, monkeypatch)
    monkeypatch.setattr(mod, "BASE_DIR", tmp_path)
    monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(mod, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(mod, "SQLITE_STATE_FILE", tmp_path / "data" / "metadata.db")
    archive = mod.create_backup()
    result = mod.validate_and_stage_backup(archive)
    assert result["valid"] is True
    assert result["sqlite_checks"][0]["integrity_check"] == "ok"


def test_json_backend_backup_behavior_remains_available(tmp_path, monkeypatch):
    monkeypatch.setenv("METADATA_BACKEND", "json")
    monkeypatch.setenv("METADATA_DB_FILE", str(tmp_path / "data" / "metadata.db"))
    import importlib, sys
    sys.modules.pop("config", None)
    sys.modules.pop("backup_manager", None)
    sys.path.insert(0, "/mnt/data/final_audit/backend")
    sys.path.insert(0, str(Path(__file__).parents[1]))
    mod = importlib.import_module("backup_manager")
    monkeypatch.setattr(mod, "BASE_DIR", tmp_path)
    monkeypatch.setattr(mod, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(mod, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(mod, "JSON_STATE_FILES", [tmp_path / "data" / "users.json"])
    mod.DATA_DIR.mkdir(parents=True)
    (mod.DATA_DIR / "users.json").write_text("[]", encoding="utf-8")
    archive = mod.create_backup()
    with tarfile.open(archive, "r:gz") as tar:
        assert "data/users.json" in tar.getnames()
        assert "data/metadata.db" not in tar.getnames()
