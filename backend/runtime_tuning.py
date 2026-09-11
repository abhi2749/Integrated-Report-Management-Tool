from __future__ import annotations

import os
from pathlib import Path


def _positive_int_env(name: str) -> int:
    try:
        return max(0, int(os.getenv(name, "0")))
    except (TypeError, ValueError):
        return 0


def _cgroup_memory_bytes() -> int | None:
    candidates = (
        Path("/sys/fs/cgroup/memory.max"),
        Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    )
    for path in candidates:
        try:
            raw = path.read_text().strip()
        except OSError:
            continue
        if not raw or raw == "max":
            continue
        try:
            value = int(raw)
        except ValueError:
            continue
        if value > 0:
            return value
    return None


def recommended_worker_count() -> int:
    """Choose a conservative execution pool size from available resources.

    An explicit EXECUTION_WORKERS value always wins. Otherwise the runtime
    uses CPU availability and, when visible, the container memory limit. This
    is a resource guard, not a row/data limit.
    """
    explicit = _positive_int_env("EXECUTION_WORKERS")
    if explicit > 0:
        return explicit

    cpu = max(1, os.cpu_count() or 1)
    workers = min(cpu, 8)
    memory = _cgroup_memory_bytes()
    if memory is not None:
        # Reserve roughly 1 GiB of memory budget per concurrent execution.
        workers = min(workers, max(1, memory // (1024 ** 3)))
    return max(1, workers)
