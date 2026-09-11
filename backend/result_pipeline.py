"""Unified result transport boundary for execution, paging, and export."""
from __future__ import annotations

from typing import Any, Iterable

from result_store import DEFAULT_PAGE_SIZE, ExecutionResultStore


class UnifiedResultPipeline:
    """Keep result transport concerns independent from connector execution.

    The pipeline never turns a stored result into one Python collection. It
    delegates persistence, page reads, and row iteration to the disk-backed
    ResultStore so MySQL, MongoDB, ClickHouse, and cross-source execution can
    share the same downstream contract.
    """

    def __init__(self, store: ExecutionResultStore):
        self.store = store

    def ingest(
        self,
        job_id: str,
        rows: Iterable[dict[str, Any]],
        *,
        columns: list[str] | None = None,
        total_rows: int | None = None,
        cancel_event: Any = None,
    ) -> dict[str, Any]:
        return self.store.ingest(
            job_id,
            rows,
            columns=columns,
            total_rows=total_rows,
            cancel_event=cancel_event,
        )

    def page(self, job_id: str, *, offset: int = 0, limit: int = DEFAULT_PAGE_SIZE) -> dict[str, Any] | None:
        return self.store.get_page(job_id, offset=offset, limit=limit)

    def metadata(self, job_id: str) -> dict[str, Any] | None:
        return self.store.get_metadata(job_id)

    def iter_rows(self, job_id: str):
        return self.store.iter_rows(job_id)
