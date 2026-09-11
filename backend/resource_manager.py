from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from typing import Iterator

from runtime_tuning import recommended_worker_count


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


class ResourceManager:
    """Process-local resource guard.

    It limits concurrent report executions rather than limiting dataset rows.
    A production deployment can replace this with a distributed semaphore.
    """

    def __init__(self):
        configured = _int_env("MAX_CONCURRENT_REPORTS", 0)
        self.max_concurrent = configured if configured > 0 else recommended_worker_count()
        self.acquire_timeout = max(1, _int_env("REPORT_RESOURCE_WAIT_SECONDS", 30))
        self._semaphore = threading.BoundedSemaphore(self.max_concurrent)

    @contextmanager
    def report_slot(self) -> Iterator[None]:
        acquired = self._semaphore.acquire(timeout=self.acquire_timeout)
        if not acquired:
            raise RuntimeError(
                "Report execution capacity is busy. Retry when another report finishes."
            )
        try:
            yield
        finally:
            self._semaphore.release()


RESOURCE_MANAGER = ResourceManager()
