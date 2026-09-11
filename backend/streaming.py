from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any


def stream_fetchmany(cursor: Any, chunk_size: int = 5000) -> Iterator[list[Any]]:
    """Yield database cursor results in bounded chunks."""
    size = max(1, int(chunk_size))
    while True:
        rows = cursor.fetchmany(size)
        if not rows:
            break
        yield rows


def stream_batches(
    fetch_batch: Callable[[int, int], list[Any]],
    *,
    chunk_size: int = 5000,
) -> Iterator[list[Any]]:
    """Generic offset/page batch iterator for connectors without cursors."""
    size = max(1, int(chunk_size))
    offset = 0
    while True:
        rows = fetch_batch(offset, size)
        if not rows:
            break
        yield rows
        if len(rows) < size:
            break
        offset += len(rows)
