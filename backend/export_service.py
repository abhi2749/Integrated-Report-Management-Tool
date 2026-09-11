from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Iterable, Iterator
from typing import Any


def _json_default(value: Any) -> str:
    return str(value)


def _cell(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=_json_default)
    return value


def safe_export_filename(name: str | None, extension: str) -> str:
    """Return a download-safe filename without accepting path components."""
    extension = extension.lower().lstrip(".")
    base = str(name or "report").strip()
    base = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", base)
    base = base.strip(" ._") or "report"
    suffix = f".{extension}"
    if base.lower().endswith(suffix):
        base = base[: -len(suffix)] or "report"
    return f"{base[:120]}{suffix}"


def csv_stream_rows(columns: list[Any], rows: Iterable[dict[str, Any]]) -> Iterator[str]:
    """Yield CSV from a row iterator without materializing the result."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    yield buffer.getvalue()
    buffer.seek(0); buffer.truncate(0)
    for row in rows:
        row = row if isinstance(row, dict) else {}
        writer.writerow([_cell(row.get(column)) for column in columns])
        yield buffer.getvalue()
        buffer.seek(0); buffer.truncate(0)


def json_stream_rows(columns: list[Any], rows: Iterable[dict[str, Any]], total_rows: int = 0) -> Iterator[str]:
    """Yield JSON envelope from a row iterator without materializing the result."""
    yield "{\"success\":true,\"columns\":"
    yield json.dumps(columns, ensure_ascii=False, default=_json_default, separators=(",", ":"))
    yield ",\"total_rows\":" + str(max(0, int(total_rows or 0))) + ",\"rows\":["
    first = True
    for row in rows:
        if not first: yield ","
        yield json.dumps(row if isinstance(row, dict) else {}, ensure_ascii=False, default=_json_default, separators=(",", ":"))
        first = False
    yield "]}"


def csv_stream(result: dict[str, Any]) -> Iterator[str]:
    """Yield CSV incrementally instead of constructing one giant string."""
    columns = result.get("columns") if isinstance(result.get("columns"), list) else []
    rows = result.get("rows") if isinstance(result.get("rows"), list) else []

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    writer.writerow(columns)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for row in rows:
        row = row if isinstance(row, dict) else {}
        writer.writerow([_cell(row.get(column)) for column in columns])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


def json_stream(result: dict[str, Any]) -> Iterator[str]:
    """Yield a stable report-result JSON envelope incrementally."""
    columns = result.get("columns") if isinstance(result.get("columns"), list) else []
    rows = result.get("rows") if isinstance(result.get("rows"), list) else []
    total_rows = result.get("total_rows", len(rows))
    returned_rows = result.get("returned_rows", len(rows))

    yield '{"success":true,"columns":'
    yield json.dumps(columns, ensure_ascii=False, default=_json_default)
    yield ',"total_rows":'
    yield json.dumps(total_rows, default=_json_default)
    yield ',"returned_rows":'
    yield json.dumps(returned_rows, default=_json_default)
    yield ',"rows":['
    for index, row in enumerate(rows):
        if index:
            yield ','
        yield json.dumps(row, ensure_ascii=False, default=_json_default, separators=(",", ":"))
    yield "]}"
