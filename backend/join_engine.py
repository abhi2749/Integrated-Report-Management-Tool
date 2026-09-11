from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from decimal import Decimal, InvalidOperation
import hashlib
import pickle
from itertools import chain
import sys
import tempfile
from pathlib import Path
from typing import Any

from config import MAX_JOIN_MEMORY_MB

SUPPORTED_JOIN_TYPES = {"INNER", "LEFT", "RIGHT", "FULL"}


def normalize_join_key(value: Any) -> Any:
    """Normalize common cross-source scalar representations for JOIN equality.

    SQL NULL semantics are preserved: None never matches another None.
    Numeric strings are normalized to Decimal when they are unambiguous, while
    ordinary identifiers remain strings. Leading-zero integer strings are kept
    as strings to avoid changing identifier semantics (e.g. '00123').
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float, Decimal)):
        try:
            return ("number", Decimal(str(value)))
        except (InvalidOperation, ValueError):
            return ("value", str(value).strip())

    text = str(value).strip()
    if text == "":
        return ("string", "")

    numeric_candidate = text
    integer_text = numeric_candidate.lstrip("+-")
    looks_integer = integer_text.isdigit()
    has_leading_zero = len(integer_text) > 1 and integer_text.startswith("0")
    if looks_integer and not has_leading_zero:
        try:
            return ("number", Decimal(numeric_candidate))
        except InvalidOperation:
            pass

    try:
        if any(ch in numeric_candidate.lower() for ch in (".", "e")):
            return ("number", Decimal(numeric_candidate))
    except InvalidOperation:
        pass

    return ("string", text)


def _key(row: dict[str, Any], field: str) -> Any:
    return normalize_join_key(row.get(field))


def validate_join(
    left_rows: Iterable[dict[str, Any]],
    right_rows: Iterable[dict[str, Any]],
    left_field: str,
    right_field: str,
    join_type: str = "INNER",
) -> str:
    """Validate the row-level JOIN contract and return normalized JOIN type."""
    how = str(join_type or "INNER").strip().upper()
    if how not in SUPPORTED_JOIN_TYPES:
        raise ValueError(f"Unsupported join type: {how}")
    if not str(left_field or "").strip():
        raise ValueError("Left JOIN field is required")
    if not str(right_field or "").strip():
        raise ValueError("Right JOIN field is required")
    return how


def _row_size(row: dict[str, Any]) -> int:
    size = sys.getsizeof(row)
    for key, value in row.items():
        size += sys.getsizeof(key) + sys.getsizeof(value)
    return size


def estimate_join_memory(rows: Iterable[dict[str, Any]], sample_size: int = 100) -> dict[str, int | None]:
    """Estimate memory needed for indexing a JOIN build side.

    This is intentionally a planning estimate, not an exact allocator measurement.
    """
    items = list(rows) if not isinstance(rows, list) else rows
    if not items:
        return {"row_count": 0, "sample_rows": 0, "estimated_bytes": 0}
    sample = items[: max(1, int(sample_size))]
    average = sum(_row_size(row) for row in sample) / len(sample)
    return {
        "row_count": len(items),
        "sample_rows": len(sample),
        "estimated_bytes": int(average * len(items)),
    }


def choose_build_side(left_count: int | None, right_count: int | None) -> str:
    """Choose the smaller known side for the hash table."""
    if left_count is None or right_count is None:
        return "right"
    return "left" if left_count < right_count else "right"


def _fields(rows: list[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for row in rows:
        result.update(row.keys())
    return result


def _merge(left: dict[str, Any] | None, right: dict[str, Any] | None, left_fields: set[str], right_fields: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if left is None:
        for field in left_fields:
            result[field] = None
    else:
        result.update(left)
    if right is None:
        for field in right_fields:
            result.setdefault(field, None)
    else:
        result.update(right)
    return result


def _partition_index(key: Any, partition_count: int) -> int:
    """Return a stable partition number for a normalized JOIN key."""
    if key is None:
        return 0
    digest = hashlib.blake2b(repr(key).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % partition_count


def _write_pickle_row(handle, row: dict[str, Any]) -> None:
    pickle.dump(row, handle, protocol=pickle.HIGHEST_PROTOCOL)


def _iter_pickle_rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("rb") as handle:
        while True:
            try:
                yield pickle.load(handle)
            except EOFError:
                return


def _spill_join(
    build_rows: Iterable[dict[str, Any]],
    probe_rows: Iterable[dict[str, Any]],
    build_field: str,
    probe_field: str,
    *,
    build_is_right: bool,
    join_type: str,
    partition_count: int = 32,
    cancel_event=None,
) -> Iterator[dict[str, Any]]:
    """Execute a partitioned hash JOIN using temporary disk storage.

    Both sides are partitioned by normalized JOIN key, so only one partition
    of the build side is held in memory at a time. This supports generators on
    the probe side and arbitrary Python scalar values via pickle.
    """
    partition_count = max(2, min(int(partition_count), 256))
    how = join_type

    with tempfile.TemporaryDirectory(prefix="reportingtool_join_") as temp_dir:
        root = Path(temp_dir)
        build_paths = [root / f"build_{index}.bin" for index in range(partition_count)]
        probe_paths = [root / f"probe_{index}.bin" for index in range(partition_count)]

        all_build_fields: set[str] = set()
        all_probe_fields: set[str] = set()

        build_handles = [path.open("wb") for path in build_paths]
        try:
            for row in build_rows:
                if cancel_event is not None and cancel_event.is_set():
                    raise InterruptedError("Execution cancelled")
                all_build_fields.update(row.keys())
                key = _key(row, build_field)
                _write_pickle_row(build_handles[_partition_index(key, partition_count)], row)
        finally:
            for handle in build_handles:
                handle.close()

        probe_handles = [path.open("wb") for path in probe_paths]
        try:
            for row in probe_rows:
                if cancel_event is not None and cancel_event.is_set():
                    raise InterruptedError("Execution cancelled")
                all_probe_fields.update(row.keys())
                key = _key(row, probe_field)
                _write_pickle_row(probe_handles[_partition_index(key, partition_count)], row)
        finally:
            for handle in probe_handles:
                handle.close()

        for partition in range(partition_count):
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("Execution cancelled")
            build_partition = list(_iter_pickle_rows(build_paths[partition]))
            probe_partition = _iter_pickle_rows(probe_paths[partition])
            if not build_partition and not (how in {"LEFT", "RIGHT", "FULL"}):
                continue

            build_fields = all_build_fields
            probe_fields = all_probe_fields
            index: dict[Any, list[int]] = defaultdict(list)
            for position, row in enumerate(build_partition):
                key = _key(row, build_field)
                if key is not None:
                    index[key].append(position)

            matched_build: set[int] = set()
            for probe_row in probe_partition:
                if cancel_event is not None and cancel_event.is_set():
                    raise InterruptedError("Execution cancelled")
                probe_fields.update(probe_row.keys())
                key = _key(probe_row, probe_field)
                matches = index.get(key, []) if key is not None else []
                if matches:
                    for build_position in matches:
                        matched_build.add(build_position)
                        if build_is_right:
                            yield _merge(probe_row, build_partition[build_position], probe_fields, build_fields)
                        else:
                            yield _merge(build_partition[build_position], probe_row, build_fields, probe_fields)
                elif (build_is_right and how in {"LEFT", "FULL"}) or (not build_is_right and how in {"RIGHT", "FULL"}):
                    if build_is_right:
                        yield _merge(probe_row, None, probe_fields, build_fields)
                    else:
                        yield _merge(None, probe_row, build_fields, probe_fields)

            if how in {"RIGHT", "FULL"} and build_is_right:
                for position, row in enumerate(build_partition):
                    if position not in matched_build:
                        yield _merge(None, row, probe_fields, build_fields)
            elif how in {"LEFT", "FULL"} and not build_is_right:
                for position, row in enumerate(build_partition):
                    if position not in matched_build:
                        yield _merge(row, None, build_fields, probe_fields)


def hash_join(
    left_rows: Iterable[dict[str, Any]],
    right_rows: Iterable[dict[str, Any]],
    left_field: str,
    right_field: str,
    *,
    join_type: str = "INNER",
    max_memory_bytes: int | None = None,
    spill_partitions: int = 32,
    cancel_event=None,
) -> Iterator[dict[str, Any]]:
    """Perform a hash JOIN with optional spill-to-disk protection.

    The build side is consumed lazily. Once its estimated retained row memory
    exceeds the configured threshold, the already-buffered build rows and the
    remaining probe rows are partitioned to temporary disk files and processed
    one partition at a time. A non-positive threshold disables spilling.
    """
    left_is_list = isinstance(left_rows, list)
    right_is_list = isinstance(right_rows, list)

    if left_is_list and right_is_list:
        left = left_rows
        right = right_rows
        build_side = choose_build_side(len(left), len(right))
    elif left_is_list:
        left = left_rows
        right = right_rows
        build_side = "right"
    else:
        left = left_rows
        right = right_rows
        build_side = "right"

    how = validate_join(left, right, left_field, right_field, join_type)
    threshold = max_memory_bytes
    if threshold is None:
        threshold = MAX_JOIN_MEMORY_MB * 1024 * 1024

    if build_side == "right":
        build_iter = iter(right)
        probe_rows = left
        build_field = right_field
        probe_field = left_field
        build_rows: list[dict[str, Any]] = []
        estimated_bytes = 0
        for row in build_iter:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("Execution cancelled")
            build_rows.append(row)
            estimated_bytes += _row_size(row)
            if threshold and estimated_bytes > threshold:
                yield from _spill_join(
                    chain(build_rows, build_iter),
                    probe_rows,
                    build_field,
                    probe_field,
                    build_is_right=True,
                    join_type=how,
                    partition_count=spill_partitions,
                    cancel_event=cancel_event,
                )
                return

        right_fields = _fields(build_rows)
        left_fields: set[str] = set()
        index: dict[Any, list[int]] = defaultdict(list)
        for index_pos, row in enumerate(build_rows):
            key = _key(row, right_field)
            if key is not None:
                index[key].append(index_pos)

        matched_right: set[int] = set()
        for left_row in probe_rows:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("Execution cancelled")
            left_fields.update(left_row.keys())
            key = _key(left_row, left_field)
            matches = index.get(key, []) if key is not None else []
            if matches:
                for right_pos in matches:
                    matched_right.add(right_pos)
                    yield _merge(left_row, build_rows[right_pos], left_fields, right_fields)
            elif how in {"LEFT", "FULL"}:
                yield _merge(left_row, None, left_fields, right_fields)

        if how in {"RIGHT", "FULL"}:
            for right_pos, right_row in enumerate(build_rows):
                if right_pos not in matched_right:
                    yield _merge(None, right_row, left_fields, right_fields)
        return

    build_iter = iter(left)
    probe_rows = right
    build_field = left_field
    probe_field = right_field
    build_rows = []
    estimated_bytes = 0
    for row in build_iter:
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Execution cancelled")
        build_rows.append(row)
        estimated_bytes += _row_size(row)
        if threshold and estimated_bytes > threshold:
            yield from _spill_join(
                chain(build_rows, build_iter),
                probe_rows,
                build_field,
                probe_field,
                build_is_right=False,
                join_type=how,
                partition_count=spill_partitions,
                cancel_event=cancel_event,
            )
            return

    left_fields = _fields(build_rows)
    right_fields: set[str] = set()
    index = defaultdict(list)
    for index_pos, row in enumerate(build_rows):
        key = _key(row, left_field)
        if key is not None:
            index[key].append(index_pos)

    matched_left: set[int] = set()
    for right_row in probe_rows:
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Execution cancelled")
        right_fields.update(right_row.keys())
        key = _key(right_row, right_field)
        matches = index.get(key, []) if key is not None else []
        if matches:
            for left_pos in matches:
                matched_left.add(left_pos)
                yield _merge(build_rows[left_pos], right_row, left_fields, right_fields)
        elif how in {"RIGHT", "FULL"}:
            yield _merge(None, right_row, left_fields, right_fields)

    if how in {"LEFT", "FULL"}:
        for left_pos, left_row in enumerate(build_rows):
            if left_pos not in matched_left:
                yield _merge(left_row, None, left_fields, right_fields)


def join_rows(
    left_rows: Iterable[dict[str, Any]],
    right_rows: Iterable[dict[str, Any]],
    left_field: str,
    right_field: str,
    *,
    join_type: str = "INNER",
) -> list[dict[str, Any]]:
    """Materialize the JOIN result for the current report execution engine."""
    return list(hash_join(left_rows, right_rows, left_field, right_field, join_type=join_type))


def project_join_result(rows, columns):
    """Project an optimized JOIN result using the report contract."""
    result = []
    for row in rows:
        out = {}
        for column in columns or []:
            field = column.get("field", "")
            alias = column.get("alias") or field
            out[alias] = row.get(field, row.get(str(field).rsplit(".", 1)[-1]))
        result.append(out)
    return result
