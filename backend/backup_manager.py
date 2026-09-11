from __future__ import annotations

import argparse
import json
import shutil
import tarfile
import sqlite3
import tempfile

from config import DATA_DIR, BACKUP_EXTERNAL_DIR, BACKUP_RETENTION_COUNT, METADATA_BACKEND, METADATA_DB_FILE, BACKUP_DIR
from api_security import sanitize_error_message
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Files that contain application state. The encryption key itself is deliberately
# NOT copied into backups; it must remain in the deployment environment.
# JSON files remain relevant only when METADATA_BACKEND=json.
JSON_STATE_FILES = [
    DATA_DIR / "users.json",
    DATA_DIR / "connections.json",
    DATA_DIR / "saved_reports.json",
    DATA_DIR / "datasets.json",
    DATA_DIR / "connection_access.json",
]

SQLITE_STATE_FILE = Path(METADATA_DB_FILE).resolve()

def _metadata_state_source() -> str:
    return "sqlite" if str(METADATA_BACKEND).lower() == "sqlite" else "json"

def _safe_existing_files():
    if _metadata_state_source() == "sqlite":
        return [SQLITE_STATE_FILE] if SQLITE_STATE_FILE.exists() and SQLITE_STATE_FILE.is_file() else []
    return [p for p in JSON_STATE_FILES if p.exists() and p.is_file()]

def _sqlite_snapshot() -> tuple[Path | None, Path | None]:
    """Create a consistent SQLite snapshot before archiving.

    SQLite WAL/SHM sidecars are not archived independently. The backup API
    produces a self-contained database image, safe to restore later.
    Returns (temporary snapshot, directory).
    """
    if _metadata_state_source() != "sqlite" or not SQLITE_STATE_FILE.exists():
        return None, None
    temp_dir = Path(tempfile.mkdtemp(prefix="reporting_tool_backup_"))
    snapshot = temp_dir / SQLITE_STATE_FILE.name
    source = sqlite3.connect(str(SQLITE_STATE_FILE))
    target = sqlite3.connect(str(snapshot))
    try:
        source.backup(target)
        target.execute("PRAGMA integrity_check")
        target.commit()
    finally:
        target.close()
        source.close()
    return snapshot, temp_dir



def create_backup() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = BACKUP_DIR / f"reporting_tool_backup_{stamp}.tar.gz"

    snapshot, temp_dir = _sqlite_snapshot()
    try:
        files = [snapshot] if snapshot else _safe_existing_files()
        if snapshot:
            archive_files = [(snapshot, Path("data") / snapshot.name)]
        else:
            archive_files = [(path, path.relative_to(BASE_DIR)) for path in files]

        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "format": "tar.gz",
            "metadata_backend": _metadata_state_source(),
            "files": [arcname.as_posix() for _, arcname in archive_files],
            "note": "Encryption keys are not stored in backups. Restore the same deployment secret separately.",
        }

        with tarfile.open(archive, "w:gz") as tar:
            for path, arcname in archive_files:
                tar.add(path, arcname=arcname.as_posix())
            info = json.dumps(manifest, indent=2).encode("utf-8")
            import io
            tarinfo = tarfile.TarInfo("backup_manifest.json")
            tarinfo.size = len(info)
            tarinfo.mtime = int(datetime.now().timestamp())
            tar.addfile(tarinfo, io.BytesIO(info))
    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    apply_retention()
    try:
        copy_to_external(archive)
    except Exception:
        pass

    return archive


def apply_retention(retention_count: int | None = None) -> list[str]:
    count = BACKUP_RETENTION_COUNT if retention_count is None else int(retention_count)
    if count < 1:
        raise ValueError("Backup retention count must be at least 1.")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    archives = sorted(
        BACKUP_DIR.glob("reporting_tool_backup_*.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removed = []
    for path in archives[count:]:
        path.unlink(missing_ok=True)
        removed.append(path.name)
    return removed


def copy_to_external(archive: Path) -> dict:
    destination = str(BACKUP_EXTERNAL_DIR or "").strip()
    if not destination:
        return {
            "configured": False,
            "copied": False,
            "message": "BACKUP_EXTERNAL_DIR is not configured.",
        }
    target_dir = Path(destination).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    if target_dir.resolve() == BACKUP_DIR.resolve():
        raise ValueError("BACKUP_EXTERNAL_DIR must be different from the local backup directory.")
    target = target_dir / archive.name
    shutil.copy2(archive, target)
    return {
        "configured": True,
        "copied": True,
        "destination": str(target),
        "size_bytes": target.stat().st_size,
    }



def list_backups() -> list[dict]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for path in sorted(BACKUP_DIR.glob("reporting_tool_backup_*.tar.gz"), reverse=True):
        result.append({
            "file": path.name,
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "modified_at": datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
        })
    return result


def validate_backup(archive: Path) -> dict:
    if not archive.exists() or not archive.is_file():
        raise FileNotFoundError(str(archive))
    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
        manifest = {}
        if "backup_manifest.json" in names:
            member = tar.extractfile("backup_manifest.json")
            if member:
                manifest = json.loads(member.read().decode("utf-8"))
        return {
            "valid": True,
            "file": archive.name,
            "members": names,
            "manifest": manifest,
        }


def validate_and_stage_backup(archive: Path) -> dict:
    """Validate a backup and safely extract it into backups/_recovery_check."""
    validation = validate_backup(archive)
    stage_root = BACKUP_DIR / "_recovery_check"
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True, exist_ok=True)

    allowed = {
        "data/users.json",
        "data/connections.json",
        "data/saved_reports.json",
        "data/datasets.json",
        "data/connection_access.json",
        f"data/{SQLITE_STATE_FILE.name}",
    }

    restored = []
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            if member.name == "backup_manifest.json":
                continue
            if member.name not in allowed:
                raise ValueError(f"Backup contains an unexpected file: {member.name}")
            if member.isdir():
                continue

            target = stage_root / member.name
            target.parent.mkdir(parents=True, exist_ok=True)

            extracted = tar.extractfile(member)
            if extracted is None:
                raise ValueError(f"Unable to read {member.name}")

            with target.open("wb") as out:
                shutil.copyfileobj(extracted, out)

            restored.append({
                "file": member.name,
                "size_bytes": target.stat().st_size,
            })

    # Validate the staged metadata according to the archive's storage mode.
    json_checks = []
    sqlite_checks = []
    for item in restored:
        path = stage_root / item["file"]
        if path.suffix.lower() == ".db":
            try:
                with sqlite3.connect(str(path)) as conn:
                    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
                sqlite_checks.append({"file": item["file"], "integrity_check": result})
            except sqlite3.Error as exc:
                sqlite_checks.append({"file": item["file"], "integrity_check": "failed", "error": sanitize_error_message(exc, "Validation failed.")})
            continue
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            json_checks.append({
                "file": item["file"],
                "valid_json": True,
                "type": type(parsed).__name__,
                "entries": len(parsed) if isinstance(parsed, (list, dict)) else None,
            })
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            json_checks.append({"file": item["file"], "valid_json": False, "error": sanitize_error_message(exc, "Validation failed.")})

    valid = all(x["valid_json"] for x in json_checks) and all(
        x["integrity_check"] == "ok" for x in sqlite_checks
    )
    return {
        "valid": bool(validation["valid"] and valid),
        "archive": archive.name,
        "staged_in": str(stage_root),
        "files": restored,
        "json_checks": json_checks,
        "sqlite_checks": sqlite_checks,
        "live_data_changed": False,
    }


def restore_backup(archive: Path, overwrite: bool = False) -> dict:
    validation = validate_backup(archive)
    allowed = {
        "data/users.json",
        "data/connections.json",
        "data/saved_reports.json",
        "data/datasets.json",
        "data/connection_access.json",
        f"data/{SQLITE_STATE_FILE.name}",
    }

    with tarfile.open(archive, "r:gz") as tar:
        members = []
        for member in tar.getmembers():
            if member.name == "backup_manifest.json":
                continue
            if member.name not in allowed:
                raise ValueError(f"Backup contains an unexpected file: {member.name}")
            if member.isdir():
                continue
            target = BASE_DIR / member.name
            if target.exists() and not overwrite:
                raise FileExistsError(
                    f"{target} already exists. Use overwrite=True only after making a current backup."
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            extracted = tar.extractfile(member)
            if extracted is None:
                raise ValueError(f"Unable to extract {member.name}")
            with target.open("wb") as out:
                shutil.copyfileobj(extracted, out)
            members.append(member.name)

    return {"restored": members, "backup": str(archive)}


def main():
    parser = argparse.ArgumentParser(description="Reporting Tool backup manager")
    parser.add_argument("command", choices=["create", "list", "validate", "recover-test", "retention", "external-copy", "restore"])
    parser.add_argument("archive", nargs="?")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.command == "create":
        print(create_backup())
    elif args.command == "list":
        print(json.dumps(list_backups(), indent=2))
    elif args.command == "validate":
        if not args.archive:
            raise SystemExit("archive path required")
        print(json.dumps(validate_backup(Path(args.archive)), indent=2))
    elif args.command == "recover-test":
        if not args.archive:
            raise SystemExit("archive path required")
        print(json.dumps(
            validate_and_stage_backup(Path(args.archive)),
            indent=2
        ))
    elif args.command == "retention":
        print(json.dumps({"removed": apply_retention()}, indent=2))
    elif args.command == "external-copy":
        if not args.archive:
            raise SystemExit("archive path required")
        print(json.dumps(copy_to_external(Path(args.archive)), indent=2))
    elif args.command == "restore":
        if not args.archive:
            raise SystemExit("archive path required")
        print(json.dumps(
            restore_backup(Path(args.archive), overwrite=args.overwrite),
            indent=2
        ))


if __name__ == "__main__":
    main()
