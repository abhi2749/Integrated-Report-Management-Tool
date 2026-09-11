from __future__ import annotations

import threading
import copy
import time
import inspect
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from result_store import ExecutionResultStore, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from config import EXECUTION_INLINE_RESULT_ROWS, EXECUTION_INLINE_RESULT_BYTES
from api_security import public_exception_message

from result_pipeline import UnifiedResultPipeline
from persistent_job_store import PersistentJobStore
from runtime_tuning import recommended_worker_count


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    id: str
    status: str = "queued"
    created_at: str = field(default_factory=_now)
    started_at: str | None = None
    finished_at: str | None = None
    rows: int = 0
    result_total_rows: int = 0
    result_returned_rows: int = 0
    result_columns: list[str] = field(default_factory=list)
    error: str | None = None
    result: Any = None
    owner_user_id: str | None = None
    owner_username: str | None = None
    query_payload: dict[str, Any] | None = field(default=None, repr=False)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)


class ExecutionManager:
    """Small in-process execution manager for the current deployment.

    It provides bounded concurrency, cancellation state, status tracking and
    cleanup. The interface is intentionally deployment-neutral so it can later
    be backed by Redis/Celery/RQ without changing the frontend contract.
    """

    def __init__(self, max_workers: int = 2, retention_seconds: int = 3600, inline_result_row_limit: int | None = None, inline_result_byte_limit: int | None = None):
        configured_workers = int(max_workers)
        self.max_workers = configured_workers if configured_workers > 0 else recommended_worker_count()
        self.retention_seconds = max(60, int(retention_seconds))
        configured_inline = inline_result_row_limit
        if configured_inline is None:
            configured_inline = EXECUTION_INLINE_RESULT_ROWS
        self.inline_result_row_limit = max(1, int(configured_inline))
        configured_inline_bytes = inline_result_byte_limit
        if configured_inline_bytes is None:
            configured_inline_bytes = EXECUTION_INLINE_RESULT_BYTES
        self.inline_result_byte_limit = max(0, int(configured_inline_bytes))
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="report-job",
        )
        self._jobs: dict[str, Job] = {}
        self._lock = threading.RLock()
        self.result_store = ExecutionResultStore()
        self.result_pipeline = UnifiedResultPipeline(self.result_store)
        self.job_store = PersistentJobStore()
        self._restore_persisted_jobs()

    def _snapshot(self, job: Job) -> dict[str, Any]:
        return {
            "id": job.id, "status": job.status, "created_at": job.created_at,
            "started_at": job.started_at, "finished_at": job.finished_at, "rows": job.rows,
            "result_total_rows": job.result_total_rows, "result_returned_rows": job.result_returned_rows,
            "result_columns": list(job.result_columns), "result": job.result, "error": job.error,
            "owner_user_id": job.owner_user_id, "owner_username": job.owner_username,
            "query_payload": copy.deepcopy(job.query_payload),
        }

    def _persist_locked(self, job: Job) -> None:
        self.job_store.save_execution(self._snapshot(job))

    def _restore_persisted_jobs(self) -> None:
        now = _now()
        for record in self.job_store.load_executions():
            status = str(record.get("status") or "failed")
            if status in {"queued", "running"}:
                status = "failed"
                record["error"] = "Backend restarted before this execution completed."
                record["finished_at"] = now
            job = Job(
                id=str(record["id"]), status=status, created_at=str(record.get("created_at") or now),
                started_at=record.get("started_at"), finished_at=record.get("finished_at"),
                rows=int(record.get("rows") or 0), result_total_rows=int(record.get("result_total_rows") or 0),
                result_returned_rows=int(record.get("result_returned_rows") or 0),
                result_columns=[str(c) for c in (record.get("result_columns") or [])],
                error=record.get("error"), result=record.get("result"),
                owner_user_id=record.get("owner_user_id"), owner_username=record.get("owner_username"),
                query_payload=record.get("query_payload") if isinstance(record.get("query_payload"), dict) else None,
            )
            self._jobs[job.id] = job
            if status == "completed" and job.result is None and self.result_store.get_metadata(job.id) is None:
                job.status = "failed"
                job.error = "Execution result is unavailable after backend restart."
                job.finished_at = now
            if status != record.get("status") or job.error != record.get("error"):
                self._persist_locked(job)

    def submit(
        self,
        fn: Callable[..., Any],
        *args,
        owner_user_id: str | None = None,
        owner_username: str | None = None,
        query_payload: dict[str, Any] | None = None,
        **kwargs,
    ) -> str:
        """Submit a job and associate it with its authenticated owner.

        Ownership is metadata only; the execution callable remains unchanged.
        Existing callers that omit ownership continue to work.
        """
        job_id = "job_" + uuid.uuid4().hex[:16]
        job = Job(
            id=job_id,
            owner_user_id=str(owner_user_id) if owner_user_id is not None else None,
            owner_username=str(owner_username) if owner_username is not None else None,
            query_payload=copy.deepcopy(query_payload) if isinstance(query_payload, dict) else None,
        )
        with self._lock:
            self._cleanup_locked()
            self._jobs[job_id] = job
            self._persist_locked(job)
        self._executor.submit(self._run, job_id, fn, args, kwargs)
        return job_id

    def _result_size_estimate(self, rows: list[Any]) -> int:
        """Estimate JSON payload size without serializing every row.

        Materialized compatibility results are already in memory when they
        reach the manager. A bounded sample lets us avoid retaining unusually
        wide rows in the job object while keeping this check independent of
        total dataset size.
        """
        if not rows or self.inline_result_byte_limit <= 0:
            return 0
        sample_size = min(len(rows), 32)
        total = 0
        for row in rows[:sample_size]:
            try:
                total += len(json.dumps(row, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8"))
            except (TypeError, ValueError):
                total += 1024
        average = total / sample_size if sample_size else 0
        return int(average * len(rows))

    def _run(self, job_id: str, fn: Callable[..., Any], args, kwargs):
        # Transition to running under the manager lock, then release it before
        # executing or ingesting rows. This keeps cancel/status endpoints
        # responsive while a large result is being streamed to disk.
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            if job.cancel_event.is_set():
                job.status = "cancelled"
                job.finished_at = _now()
                return
            job.status = "running"
            job.started_at = _now()
            self._persist_locked(job)

        try:
            try:
                accepts_cancel = "cancel_event" in inspect.signature(fn).parameters
            except (TypeError, ValueError):
                accepts_cancel = False

            result = fn(*args, cancel_event=job.cancel_event, **kwargs) if accepts_cancel else fn(*args, **kwargs)

            # Never hold the manager lock during potentially unbounded result
            # ingestion. ExecutionResultStore checks cancel_event between rows
            # and aborts promptly without blocking the cancellation endpoint.
            if isinstance(result, dict) and result.get("streaming_rows") is not None:
                stored = self.result_pipeline.ingest(
                    job_id,
                    result["streaming_rows"],
                    columns=result.get("columns") or [],
                    cancel_event=job.cancel_event,
                )
                with self._lock:
                    job = self._jobs.get(job_id)
                    if not job:
                        return
                    if job.cancel_event.is_set():
                        job.status = "cancelled"
                        job.result = None
                    else:
                        job.status = "completed"
                        job.result_total_rows = int(stored.get("total_rows", 0))
                        job.result_returned_rows = 0
                        job.result_columns = [str(c) for c in stored.get("columns", [])]
                        job.rows = job.result_total_rows
                        job.result = {
                            "success": result.get("success", True),
                            "columns": job.result_columns,
                            "total_rows": job.result_total_rows,
                            "returned_rows": 0,
                        }
                    job.finished_at = _now()
                    self._persist_locked(job)
                if job.cancel_event.is_set():
                    self.result_store.delete(job_id)
                return

            # Prepare any disk persistence before acquiring the manager lock.
            # A materialized compatibility result may require a large SQLite
            # write; keeping that work outside the lock ensures status/result
            # page/cancel calls remain responsive during persistence.
            disk_backed_result = None
            result_metadata = None
            if isinstance(result, dict):
                result_rows = result.get("rows")
                loaded_rows = len(result_rows) if isinstance(result_rows, list) else 0
                total_rows = result.get("total_rows")
                if total_rows is None:
                    total_rows = result.get("grouped_rows")
                try:
                    total_rows = max(0, int(total_rows or 0))
                except (TypeError, ValueError):
                    total_rows = loaded_rows
                result_columns = [str(column) for column in (result.get("columns") or [])]
                estimated_bytes = self._result_size_estimate(result_rows)
                if (
                    loaded_rows > self.inline_result_row_limit
                    or (self.inline_result_byte_limit > 0 and estimated_bytes > self.inline_result_byte_limit)
                ):
                    disk_backed_result = self.result_store.replace_result(job_id, result)
                result_metadata = (loaded_rows, total_rows, result_columns)

            with self._lock:
                job = self._jobs.get(job_id)
                if not job:
                    return
                if job.cancel_event.is_set():
                    job.status = "cancelled"
                    job.result = None
                else:
                    job.status = "completed"
                    job.result = result
                    if result_metadata is not None:
                        loaded_rows, total_rows, result_columns = result_metadata
                        job.result_total_rows = total_rows
                        job.result_returned_rows = loaded_rows
                        job.result_columns = result_columns
                        job.rows = loaded_rows
                        if disk_backed_result is not None:
                            job.result = {
                                "success": result.get("success", True),
                                "columns": result.get("columns", []),
                                "total_rows": total_rows,
                                "returned_rows": loaded_rows,
                            }
                job.finished_at = _now()
                self._persist_locked(job)
        except InterruptedError as exc:
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    job.status = "cancelled"
                    job.result = None
                    job.error = None
                    job.finished_at = _now()
                    self._persist_locked(job)
            self.result_store.delete(job_id)
        except Exception as exc:
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    job.status = "cancelled" if job.cancel_event.is_set() else "failed"
                    job.error = public_exception_message(exc, "Execution failed.")
                    job.finished_at = _now()
                    if job.status == "cancelled":
                        job.result = None
                    self._persist_locked(job)
            if job and job.cancel_event.is_set():
                self.result_store.delete(job_id)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status in {"completed", "failed", "cancelled"}:
                return False
            job.cancel_event.set()
            if job.status == "queued":
                job.status = "cancelled"
                job.finished_at = _now()
                self._persist_locked(job)
            return True


    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._cleanup_locked()
            job = self._jobs.get(job_id)
            if not job:
                return None
            return self._public(job)

    def get_query_payload(self, job_id: str) -> dict[str, Any] | None:
        """Return the private canonical query payload for an owned job.

        The payload is never included in the public job response. A copy is
        returned so callers cannot mutate the stored execution definition.
        """
        with self._lock:
            self._cleanup_locked()
            job = self._jobs.get(job_id)
            if not job or not isinstance(job.query_payload, dict):
                return None
            return copy.deepcopy(job.query_payload)

    def result_page(self, job_id: str, offset: int = 0, limit: int = DEFAULT_PAGE_SIZE) -> dict[str, Any] | None:
        offset = max(0, int(offset))
        limit = max(1, int(limit))
        with self._lock:
            self._cleanup_locked()
            job = self._jobs.get(job_id)
            if not job:
                return None
            status = job.status
            fallback_result = job.result if isinstance(job.result, dict) else {}

        # Disk-backed streaming results are readable while the worker is still
        # ingesting them. SQLite WAL keeps readers independent from writers.
        page = self.result_pipeline.page(job_id, offset=offset, limit=limit)
        if page is not None:
            page["status"] = status
            page["ready"] = bool(page.get("returned_rows", 0)) or status == "completed"
            page["streaming"] = status == "running"
            page["has_more"] = bool(page.get("has_more")) or status == "running"
            return page

        if status != "completed":
            return {
                "ready": False,
                "status": status,
                "streaming": status == "running",
                "rows": [],
                "columns": job.result_columns,
                "total_rows": job.result_total_rows or job.rows,
                "returned_rows": 0,
                "offset": offset,
                "limit": limit,
                "has_more": status == "running",
            }

        rows = fallback_result.get("rows") if isinstance(fallback_result.get("rows"), list) else []
        page_rows = rows[offset:offset + limit]
        return {
            "ready": True,
            "status": "completed",
            "streaming": False,
            "rows": page_rows,
            "columns": fallback_result.get("columns", []),
            "total_rows": len(rows),
            "returned_rows": len(page_rows),
            "materialized_rows": len(rows),
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(page_rows) < len(rows),
        }

    def iter_result_rows(self, job_id: str):
        """Yield a completed job result without materializing disk-backed rows."""
        with self._lock:
            self._cleanup_locked()
            job = self._jobs.get(job_id)
            if not job:
                return None
            if job.status != "completed":
                return None
            result = job.result if isinstance(job.result, dict) else {}
            rows = result.get("rows")
            if isinstance(rows, list):
                return iter(rows)
            if job.result_total_rows > 0 or result.get("result_available"):
                return self.result_pipeline.iter_rows(job_id)
            return iter(())

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            self._cleanup_locked()
            return [self._public(job) for job in self._jobs.values()]

    def _public(self, job: Job) -> dict[str, Any]:
        data = {
            "id": job.id,
            "status": job.status,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "rows": job.rows,
            "result_total_rows": job.result_total_rows,
            "result_returned_rows": job.result_returned_rows,
            "result_columns": job.result_columns,
            "owner_user_id": job.owner_user_id,
            "owner_username": job.owner_username,
        }
        if job.error:
            data["error"] = job.error
        if job.status == "running":
            progress = self.result_pipeline.metadata(job.id)
            if progress is not None:
                data["result_available"] = progress["total_rows"] > 0
                data["result_streaming"] = True
                data["result_row_count"] = progress["total_rows"]
                data["result_page_size"] = 5000
                data["columns"] = progress["columns"]
        if job.status == "completed" and isinstance(job.result, dict):
            rows = job.result.get("rows")
            row_count = len(rows) if isinstance(rows, list) else 0
            is_disk_backed = job.result_total_rows > 0 and not isinstance(rows, list)
            if row_count <= self.inline_result_row_limit and not is_disk_backed:
                data["result"] = job.result
            else:
                # Avoid serializing a potentially very large result on every
                # status poll. Clients can use the bounded result-page API.
                data["result_available"] = True
                data["result_row_count"] = job.result_total_rows or row_count
                data["result_materialized_rows"] = row_count
                data["result_page_size"] = 5000
                data["columns"] = job.result.get("columns", [])
        return data

    def _cleanup_locked(self):
        now = time.time()
        remove = []
        for job_id, job in self._jobs.items():
            if not job.finished_at:
                continue
            try:
                finished = datetime.fromisoformat(job.finished_at).timestamp()
            except ValueError:
                continue
            if now - finished > self.retention_seconds:
                remove.append(job_id)
        for job_id in remove:
            self._jobs.pop(job_id, None)
            self.result_store.delete(job_id)
            self.job_store.delete_execution(job_id)
        self.result_store.cleanup_jobs(remove)

    def shutdown(self, wait: bool = False):
        self._executor.shutdown(wait=wait, cancel_futures=True)


EXECUTION_MANAGER = ExecutionManager()
