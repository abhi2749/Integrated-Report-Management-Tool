from __future__ import annotations

import csv
import json
import io
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from collections.abc import Iterator

from export_service import _cell, _json_default
from persistent_job_store import PersistentJobStore
from api_security import public_exception_message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExportJobManager:
    """Background, disk-backed export jobs.

    Export jobs consume a completed execution result through an iterator so the
    complete result does not need to be re-materialized in Python or held in
    the HTTP request. Files are written to a temporary path and atomically
    renamed only after successful completion.
    """

    def __init__(self, export_dir: Path, max_workers: int = 0, retention_seconds: int = 3600, progress_interval: int = 1000):
        from concurrent.futures import ThreadPoolExecutor
        self.export_dir = Path(export_dir).resolve()
        self.export_dir.mkdir(parents=True, exist_ok=True)
        configured_workers = int(max_workers or 0)
        if configured_workers > 0:
            self.max_workers = configured_workers
        else:
            from runtime_tuning import recommended_worker_count
            self.max_workers = recommended_worker_count()
        self.retention_seconds = max(60, int(retention_seconds))
        self.progress_interval = max(1, int(progress_interval))
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="report-export")
        self.job_store = PersistentJobStore()
        self._restore_persisted_jobs()

    def _persist_locked(self, job: dict[str, Any]) -> None:
        self.job_store.save_export(job)

    def _restore_persisted_jobs(self) -> None:
        now = _now()
        for record in self.job_store.load_exports():
            record["cancel_event"] = threading.Event()
            status = str(record.get("status") or "failed")
            part_path = self.export_dir / f".{record['id']}.{record['format']}.part"
            if status in {"queued", "running"}:
                record["status"] = "failed"
                record["error"] = "Backend restarted before this export completed."
                record["finished_at"] = now
                part_path.unlink(missing_ok=True)
            elif status == "completed" and not Path(record["file_path"]).exists():
                record["status"] = "failed"
                record["error"] = "Export file is no longer available after backend restart."
                record["finished_at"] = now
            self._jobs[record["id"]] = record
            if record["status"] != status:
                self._persist_locked(record)

    def submit(
        self,
        *,
        source_job_id: str,
        owner_user_id: str | None,
        owner_username: str = "",
        fmt: str,
        filename: str,
        columns: list[str],
        row_iterator_factory: Callable[[], Iterator[dict[str, Any]]],
        total_rows: int = 0,
        writer: Callable[[Path, list[str], Callable[[], Iterator[dict[str, Any]]], dict[str, Any], Callable[[], bool]], int] | None = None,
    ) -> str:
        normalized = str(fmt).lower()
        if normalized not in {"csv", "json", "xlsx", "pdf", "package"}:
            raise ValueError("Unsupported export format.")

        export_id = uuid.uuid4().hex
        final_path = self.export_dir / f"{export_id}.{normalized}"
        temp_path = self.export_dir / f".{export_id}.{normalized}.part"
        job = {
            "id": export_id,
            "source_job_id": source_job_id,
            "owner_user_id": owner_user_id,
            "owner_username": owner_username,
            "format": normalized,
            "filename": filename,
            "status": "queued",
            "created_at": _now(),
            "started_at": None,
            "finished_at": None,
            "total_rows": max(0, int(total_rows or 0)),
            "processed_rows": 0,
            "progress": 0 if total_rows else None,
            "file_size": 0,
            "file_path": str(final_path),
            "error": None,
            "cancel_event": threading.Event(),
        }
        with self._lock:
            self._cleanup_locked()
            self._jobs[export_id] = job
            self._persist_locked(job)
        self._executor.submit(self._run, export_id, columns, row_iterator_factory, temp_path, final_path, writer)
        return export_id

    def _run(self, export_id, columns, row_iterator_factory, temp_path, final_path, writer=None):
        with self._lock:
            job = self._jobs.get(export_id)
            if not job:
                return
            job["status"] = "running"
            job["started_at"] = _now()
            self._persist_locked(job)

        try:
            columns = [str(c) for c in (columns or [])]
            processed = 0
            if writer is not None:
                processed = writer(
                    temp_path, columns, row_iterator_factory, job,
                    lambda: bool(job["cancel_event"].is_set()),
                )
            else:
                with temp_path.open("w", encoding="utf-8", newline="", buffering=1024 * 1024) as handle:
                    if job["format"] == "csv":
                        processed = self._write_csv(handle, columns, row_iterator_factory, job, processed)
                    else:
                        processed = self._write_json(handle, columns, row_iterator_factory, job)

            with self._lock:
                job = self._jobs.get(export_id)
                if not job:
                    temp_path.unlink(missing_ok=True)
                    return
                if job["cancel_event"].is_set():
                    job["status"] = "cancelled"
                    job["finished_at"] = _now()
                    temp_path.unlink(missing_ok=True)
                    self._persist_locked(job)
                    return
                temp_path.replace(final_path)
                job["status"] = "completed"
                job["finished_at"] = _now()
                job["file_size"] = final_path.stat().st_size if final_path.exists() else 0
                job["processed_rows"] = processed
                job["progress"] = 100
                self._persist_locked(job)
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            with self._lock:
                job = self._jobs.get(export_id)
                if job:
                    job["status"] = "cancelled" if job["cancel_event"].is_set() else "failed"
                    job["error"] = None if job["cancel_event"].is_set() else public_exception_message(exc, "Export failed.")
                    job["finished_at"] = _now()
                    self._persist_locked(job)

    @staticmethod
    def _update_progress(job, processed):
        job["processed_rows"] = processed
        total = int(job.get("total_rows") or 0)
        job["progress"] = min(99, int(processed * 100 / total)) if total else None

    def _write_csv(self, handle, columns, factory, job, processed):
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in factory():
            if job["cancel_event"].is_set():
                raise InterruptedError("Export cancelled.")
            row = row if isinstance(row, dict) else {}
            writer.writerow([_cell(row.get(column)) for column in columns])
            processed += 1
            if processed % self.progress_interval == 0:
                handle.flush()
                with self._lock:
                    current = self._jobs.get(job["id"])
                    if current:
                        self._update_progress(current, processed)
                        self._persist_locked(current)
        return processed

    def _write_json(self, handle, columns, factory, job):
        handle.write('{"success":true,"columns":')
        handle.write(json.dumps(columns, ensure_ascii=False, default=_json_default, separators=(",", ":")))
        handle.write(',"total_rows":')
        handle.write(str(int(job.get("total_rows") or 0)))
        handle.write(',"rows":[')
        processed = 0
        first = True
        for row in factory():
            if job["cancel_event"].is_set():
                raise InterruptedError("Export cancelled.")
            if not first:
                handle.write(",")
            handle.write(json.dumps(row if isinstance(row, dict) else {}, ensure_ascii=False, default=_json_default, separators=(",", ":")))
            first = False
            processed += 1
            if processed % self.progress_interval == 0:
                handle.flush()
                with self._lock:
                    current = self._jobs.get(job["id"])
                    if current:
                        self._update_progress(current, processed)
                        self._persist_locked(current)
        handle.write("]}")
        return processed

    def get(self, export_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._cleanup_locked()
            job = self._jobs.get(export_id)
            if not job:
                return None
            return self._public(job)

    def cancel(self, export_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(export_id)
            if not job or job["status"] in {"completed", "failed", "cancelled"}:
                return False
            job["cancel_event"].set()
            if job["status"] == "queued":
                job["status"] = "cancelled"
                job["finished_at"] = _now()
                self._persist_locked(job)
            return True

    def path_for_completed(self, export_id: str) -> tuple[dict[str, Any], Path] | None:
        with self._lock:
            self._cleanup_locked()
            job = self._jobs.get(export_id)
            if not job or job["status"] != "completed":
                return None
            path = Path(job["file_path"])
            if not path.exists():
                job["status"] = "failed"
                job["error"] = "Export file is no longer available."
                job["finished_at"] = _now()
                self._persist_locked(job)
                return None
            return self._public(job), path

    def _public(self, job):
        return {k: v for k, v in job.items() if k != "cancel_event" and k != "file_path"}

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)

    def _cleanup_locked(self):
        now = datetime.now(timezone.utc).timestamp()
        remove = []
        for export_id, job in self._jobs.items():
            finished = job.get("finished_at")
            if not finished:
                continue
            try:
                age = now - datetime.fromisoformat(finished).timestamp()
            except ValueError:
                continue
            if age > self.retention_seconds:
                remove.append(export_id)
        for export_id in remove:
            job = self._jobs.pop(export_id, None)
            if job:
                Path(job["file_path"]).unlink(missing_ok=True)
                self.export_dir.joinpath(f".{export_id}.{job['format']}.part").unlink(missing_ok=True)
                self.job_store.delete_export(export_id)
