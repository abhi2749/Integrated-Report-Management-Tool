"""Data import and ingestion foundation.

Stores the original uploaded file plus a normalized JSONL representation and
metadata in the existing SQLite metadata repository. This is intentionally an
ingestion boundary: later dataset management can expose these imported assets
to the canonical query engine without coupling file parsing to query execution.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO
import csv
import json
import os
import secrets
import shutil
import zipfile
import xml.etree.ElementTree as ET

from config import (DATA_DIR, METADATA_BACKEND, METADATA_DB_FILE, IMPORT_DATA_DIR,
                    MAX_IMPORT_FILE_MB, IMPORT_PREVIEW_ROWS)
from metadata_repository import MetadataRepository, create_metadata_repository

IMPORT_COLLECTION = "imported_datasets"
IMPORT_METADATA_FILE = Path(DATA_DIR) / "imported_datasets.json"
IMPORT_ROOT = IMPORT_DATA_DIR
MAX_IMPORT_MB = MAX_IMPORT_FILE_MB
# 0 = no artificial application file-size ceiling; physical/resource limits still apply.
PREVIEW_ROWS = IMPORT_PREVIEW_ROWS
ALLOWED_EXTENSIONS = {".csv", ".json", ".xlsx"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(name: str) -> str:
    raw = Path(name or "upload").name
    cleaned = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in raw).strip(" .")
    return cleaned or "upload"


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _unique_columns(columns: list[Any]) -> list[str]:
    used: dict[str, int] = {}
    result: list[str] = []
    for index, raw in enumerate(columns, start=1):
        name = str(raw).strip() if raw is not None else ""
        name = name or f"column_{index}"
        count = used.get(name, 0) + 1
        used[name] = count
        result.append(name if count == 1 else f"{name}_{count}")
    return result


def _infer_type(values: list[Any]) -> str:
    usable = [v for v in values if v not in (None, "")]
    if not usable:
        return "string"
    if all(isinstance(v, bool) for v in usable):
        return "boolean"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in usable):
        return "integer"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in usable):
        return "number"
    lowered = {str(v).strip().lower() for v in usable}
    if lowered <= {"true", "false", "yes", "no", "0", "1"}:
        return "boolean"
    return "string"


def _write_jsonl(rows: list[dict[str, Any]], target: Path) -> None:
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _iter_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            return [], iter(())
    columns = _unique_columns(header)

    def rows():
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            for raw in reader:
                if not any(str(value).strip() for value in raw):
                    continue
                values = list(raw) + [None] * max(0, len(columns) - len(raw))
                yield {columns[i]: _json_value(values[i]) for i in range(len(columns))}

    return columns, rows()


def _parse_csv(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    columns, rows = _iter_csv(path)
    return columns, list(rows)


def _iter_json_objects(path: Path):
    """Yield JSON objects from an array without loading the complete file.

    Supports a top-level array of objects and {"rows": [...]} objects. The
    parser uses only the standard library and reads incrementally from disk.
    """
    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8") as handle:
        buffer = ""
        eof = False
        position = 0

        def read_more():
            nonlocal buffer, eof, position
            chunk = handle.read(1024 * 1024)
            if chunk:
                buffer += chunk
                return True
            eof = True
            return False

        if not read_more():
            raise ValueError("JSON import must contain an object, or an array of objects.")
        while position < len(buffer) and buffer[position].isspace():
            position += 1
        if position >= len(buffer):
            raise ValueError("JSON import must contain an object, or an array of objects.")

        first = buffer[position]
        if first == "[":
            position += 1
            while True:
                while True:
                    while position < len(buffer) and buffer[position].isspace():
                        position += 1
                    if position < len(buffer):
                        break
                    if eof:
                        raise ValueError("Invalid JSON array.")
                    read_more()
                if buffer[position] == "]":
                    return
                try:
                    value, end = decoder.raw_decode(buffer, position)
                except json.JSONDecodeError:
                    if eof:
                        raise ValueError("Invalid JSON array.")
                    if position > 0:
                        buffer = buffer[position:]
                        position = 0
                    read_more()
                    continue
                position = end
                if not isinstance(value, dict):
                    raise ValueError("JSON import contains a non-object row.")
                yield value
                while True:
                    while position < len(buffer) and buffer[position].isspace():
                        position += 1
                    if position < len(buffer):
                        break
                    if eof:
                        raise ValueError("Invalid JSON array.")
                    read_more()
                if buffer[position] == ",":
                    position += 1
                    continue
                if buffer[position] == "]":
                    return
                raise ValueError("Invalid JSON array.")

        if first == "{":
            decoder = json.JSONDecoder()
            try:
                value, end = decoder.raw_decode(buffer, position)
            except json.JSONDecodeError:
                value = json.loads(path.read_text(encoding="utf-8"))
                end = len(buffer)
            if not isinstance(value, dict):
                raise ValueError("JSON import must contain an object, or an array of objects.")
            rows = value.get("rows")
            if isinstance(rows, list):
                for item in rows:
                    if not isinstance(item, dict):
                        raise ValueError("JSON import contains a non-object row.")
                    yield item
                return
            yield value
            return

        raise ValueError("JSON import must contain an object, or an array of objects.")


def _iter_json(path: Path):
    # First pass discovers the complete schema without retaining rows.
    source_keys = []
    for item in _iter_json_objects(path):
        for key in item.keys():
            if key not in source_keys:
                source_keys.append(key)

    columns = _unique_columns(source_keys)
    mapping = dict(zip(source_keys, columns))

    def rows():
        for item in _iter_json_objects(path):
            yield {mapping[key]: _json_value(item.get(key)) for key in source_keys}

    return columns, rows()


def _parse_json(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    columns, rows = _iter_json(path)
    return columns, list(rows)


def _iter_xlsx(path: Path):
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("Excel import requires openpyxl. Install backend requirements first.") from exc
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        worksheet = workbook.active
        header = next(worksheet.iter_rows(values_only=True), None)
        if header is None:
            return [], iter(())
        columns = _unique_columns(list(header))
    finally:
        workbook.close()

    def rows():
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            iterator = workbook.active.iter_rows(values_only=True)
            next(iterator, None)
            for raw in iterator:
                if not any(value is not None and str(value).strip() for value in raw):
                    continue
                values = list(raw) + [None] * max(0, len(columns) - len(raw))
                yield {columns[i]: _json_value(values[i]) for i in range(len(columns))}
        finally:
            workbook.close()

    return columns, rows()


def _parse_xlsx(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    columns, rows = _iter_xlsx(path)
    return columns, list(rows)


def _iter_parsed_rows(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _iter_csv(path)
    if suffix == ".json":
        return _iter_json(path)
    if suffix == ".xlsx":
        return _iter_xlsx(path)
    raise ValueError(f"Unsupported import format: {suffix or 'unknown'}")


def _parse(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    columns, rows = _iter_parsed_rows(path)
    return columns, list(rows)


class ImportedDataRegistry:
    def __init__(self, repository: MetadataRepository):
        self.repository = repository

    def list(self, user: dict[str, Any]) -> list[dict[str, Any]]:
        records = self.repository.read()
        if str(user.get("role", "")).lower() == "admin":
            return records
        user_id = str(user.get("id", ""))
        return [item for item in records if str(item.get("owner_id", "")) == user_id]

    def get(self, dataset_id: str, user: dict[str, Any]) -> dict[str, Any] | None:
        item = next((x for x in self.repository.read() if x.get("id") == dataset_id), None)
        if item is None:
            return None
        if str(user.get("role", "")).lower() == "admin" or str(item.get("owner_id")) == str(user.get("id")):
            return item
        return None

    def get_raw(self, dataset_id: str) -> dict[str, Any] | None:
        return next((x for x in self.repository.read() if x.get("id") == dataset_id), None)

    def save(self, item: dict[str, Any]) -> dict[str, Any]:
        records = [x for x in self.repository.read() if x.get("id") != item.get("id")]
        records.insert(0, item)
        self.repository.write(records)
        return item

    def update(self, dataset_id: str, changes: dict[str, Any], user: dict[str, Any]) -> dict[str, Any] | None:
        item = self.get(dataset_id, user)
        if item is None:
            return None
        name = str(changes.get("name", item.get("name", ""))).strip()
        if not name:
            raise ValueError("Dataset name cannot be empty.")
        return self.save({**item, "name": name, "updated_at": _now()})

    def delete(self, dataset_id: str, user: dict[str, Any]) -> bool:
        item = self.get(dataset_id, user)
        if item is None:
            return False
        records = [x for x in self.repository.read() if x.get("id") != dataset_id]
        self.repository.write(records)
        original_path = item.get("original_path") or item.get("storage_path")
        if original_path:
            storage_dir = (DATA_DIR / original_path).resolve().parent
            data_root = DATA_DIR.resolve()
            if data_root not in storage_dir.parents:
                raise ValueError("Invalid imported data storage path.")
            shutil.rmtree(storage_dir, ignore_errors=True)
        return True


def create_imported_data_registry(repository: MetadataRepository | None = None) -> ImportedDataRegistry:
    if repository is None:
        repository = create_metadata_repository(
            IMPORT_METADATA_FILE,
            backend=METADATA_BACKEND,
            collection=IMPORT_COLLECTION,
            db_path=METADATA_DB_FILE,
        )
    return ImportedDataRegistry(repository)


IMPORTED_DATA_REGISTRY = create_imported_data_registry()


def import_file(upload: BinaryIO, filename: str, content_length: int | None, owner: dict[str, Any]) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    original_name = _safe_filename(filename)
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Supported import formats are CSV, JSON and XLSX.")
    if MAX_IMPORT_MB > 0 and content_length is not None and content_length > MAX_IMPORT_MB * 1024 * 1024:
        raise ValueError(f"Import file exceeds the {MAX_IMPORT_MB} MB limit.")

    dataset_id = f"import_{secrets.token_hex(8)}"
    dataset_dir = IMPORT_ROOT / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=False)
    source_path = dataset_dir / original_name
    normalized_path = dataset_dir / "data.jsonl"

    try:
        total = 0
        with source_path.open("wb") as target:
            while True:
                chunk = upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if MAX_IMPORT_MB > 0 and total > MAX_IMPORT_MB * 1024 * 1024:
                    raise ValueError(f"Import file exceeds the {MAX_IMPORT_MB} MB limit.")
                target.write(chunk)

        columns, rows = _iter_parsed_rows(source_path)
        sample_rows: list[dict[str, Any]] = []
        row_count = 0
        with normalized_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                if len(sample_rows) < 100:
                    sample_rows.append(row)
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                row_count += 1
        metadata = {
            "id": dataset_id,
            "name": Path(original_name).stem or dataset_id,
            "format": suffix.lstrip("."),
            "source_type": "imported",
            "database": "local_imports",
            "object_name": Path(original_name).stem or dataset_id,
            "object_type": "file",
            "source_filename": original_name,
            "storage_format": "jsonl",
            "storage_path": str(normalized_path.relative_to(DATA_DIR)),
            "original_path": str(source_path.relative_to(DATA_DIR)),
            "row_count": row_count,
            "columns": [{"name": column, "type": _infer_type([row.get(column) for row in sample_rows])} for column in columns],
            "owner_id": str(owner.get("id", "")),
            "owner_username": str(owner.get("username", "")),
            "created_at": _now(),
            "updated_at": _now(),
            "status": "ready",
        }
        return IMPORTED_DATA_REGISTRY.save(metadata)
    except Exception:
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise


def iter_import_rows(dataset: dict[str, Any], required_columns: list[str] | None = None):
    """Stream a persisted imported dataset as qualified reporting rows."""
    path = (DATA_DIR / dataset["storage_path"]).resolve()
    data_root = DATA_DIR.resolve()
    if data_root not in path.parents:
        raise ValueError("Invalid imported data path.")
    allowed = set(required_columns or [])
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = json.loads(line)
            if allowed:
                raw = {key: value for key, value in raw.items() if key in allowed}
            yield {f"{dataset['id']}.{key}": value for key, value in raw.items()}


def read_import_rows(dataset: dict[str, Any], required_columns: list[str] | None = None) -> list[dict[str, Any]]:
    """Read a persisted imported dataset as qualified reporting rows."""
    path = (DATA_DIR / dataset["storage_path"]).resolve()
    data_root = DATA_DIR.resolve()
    if data_root not in path.parents:
        raise ValueError("Invalid imported data path.")
    allowed = set(required_columns or [])
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = json.loads(line)
            if allowed:
                raw = {key: value for key, value in raw.items() if key in allowed}
            rows.append({f"{dataset['id']}.{key}": value for key, value in raw.items()})
    return rows


def preview_import(dataset: dict[str, Any], limit: int = PREVIEW_ROWS) -> dict[str, Any]:
    path = (DATA_DIR / dataset["storage_path"]).resolve()
    if DATA_DIR.resolve() not in path.parents:
        raise ValueError("Invalid imported data path.")
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(rows) >= max(1, int(limit)):
                break
            rows.append(json.loads(line))
    return {"columns": dataset.get("columns", []), "rows": rows}
