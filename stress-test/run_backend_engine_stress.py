#!/usr/bin/env python3
r"""Offline ReportingTool backend stress harness.

Exercises the actual JOIN engine and ExecutionResultStore without company data
or external databases. The default run uses 100,000 rows per side and forces
spill-to-disk so the test remains deterministic on developer machines.

Examples (from C:\ReportingTool):
  python stress-test\run_backend_engine_stress.py
  python stress-test\run_backend_engine_stress.py --rows 500000 --spill-memory-mb 1
  python stress-test\run_backend_engine_stress.py --rows 1000000 --spill-memory-mb 4
"""

from __future__ import annotations

import argparse
import gc
import os
import shutil
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from join_engine import hash_join  # noqa: E402
from result_store import ExecutionResultStore  # noqa: E402


def rows(count: int, offset: int = 0):
    for i in range(count):
        key = offset + i + 1
        yield {
            "id": key,
            "meter_id": f"MTR-{key:09d}",
            "zone": ("NORTH", "SOUTH", "EAST", "WEST")[key % 4],
            "energy_kwh": round(100 + (key * 31 % 900000) / 100, 2),
        }


def run_join(rows_per_side: int, spill_memory_mb: int) -> tuple[int, float, float]:
    # Both sides have exactly one matching key for each row.
    left = rows(rows_per_side, 0)
    right = rows(rows_per_side, 0)
    started = time.perf_counter()
    tracemalloc.start()
    count = 0
    checksum = 0
    try:
        for row in hash_join(
            left,
            right,
            "id",
            "id",
            join_type="INNER",
            max_memory_bytes=max(1, spill_memory_mb) * 1024 * 1024,
            spill_partitions=32,
        ):
            count += 1
            checksum += int(row["id"])
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    elapsed = time.perf_counter() - started
    expected_checksum = rows_per_side * (rows_per_side + 1) // 2
    if count != rows_per_side or checksum != expected_checksum:
        raise AssertionError(
            f"JOIN validation failed: rows={count}, checksum={checksum}, "
            f"expected rows={rows_per_side}, checksum={expected_checksum}"
        )
    return count, elapsed, peak / (1024 * 1024)


def _cleanup_windows_safe(path: Path, attempts: int = 8) -> None:
    """Remove a SQLite stress directory reliably on Windows."""
    last_error = None
    for attempt in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except PermissionError as exc:
            last_error = exc
            gc.collect()
            time.sleep(0.1 * (attempt + 1))
    if last_error is not None:
        raise last_error


def run_result_store(row_count: int) -> tuple[int, float]:
    temp_dir = Path(tempfile.mkdtemp(prefix="reportingtool_stress_"))
    db_path = temp_dir / "results.sqlite3"
    store = None
    try:
        store = ExecutionResultStore(db_path)
        started = time.perf_counter()
        stored = store.ingest(
            "stress-job",
            rows(row_count),
            columns=["id", "meter_id", "zone", "energy_kwh"],
        )
        elapsed = time.perf_counter() - started
        page = store.get_page("stress-job", offset=row_count - 10, limit=10)
        if stored["total_rows"] != row_count or not page or len(page["rows"]) != 10:
            raise AssertionError("ResultStore validation failed")
        return stored["total_rows"], elapsed
    finally:
        # ExecutionResultStore opens short-lived SQLite connections, but
        # Windows can briefly retain file handles after the final connection
        # closes. Explicitly release the store and retry cleanup.
        store = None
        gc.collect()
        if os.name == "nt":
            _cleanup_windows_safe(temp_dir)
        else:
            shutil.rmtree(temp_dir)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--spill-memory-mb", type=int, default=1)
    parser.add_argument("--skip-result-store", action="store_true")
    args = parser.parse_args()
    if args.rows < 1 or args.spill_memory_mb < 1:
        parser.error("--rows and --spill-memory-mb must be positive")

    print(f"JOIN stress: {args.rows:,} rows/side, spill threshold {args.spill_memory_mb} MB")
    joined, join_seconds, peak_mb = run_join(args.rows, args.spill_memory_mb)
    print(f"JOIN PASS: {joined:,} rows in {join_seconds:.2f}s; Python peak allocation {peak_mb:.1f} MB")

    if not args.skip_result_store:
        stored, store_seconds = run_result_store(args.rows)
        print(f"RESULT STORE PASS: {stored:,} rows ingested in {store_seconds:.2f}s")

    print("STRESS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
