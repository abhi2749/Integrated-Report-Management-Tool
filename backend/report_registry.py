"""Saved report domain/persistence boundary.

Change #8 promotes saved reports to a first-class backend entity while keeping
existing API payloads compatible with the current frontend.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import secrets

from config import METADATA_DB_FILE, METADATA_BACKEND, REPORTS_FILE
from metadata_repository import create_metadata_repository, MetadataRepository


REPORT_COLLECTION = "saved_reports"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return f"report_{secrets.token_hex(8)}"


def _user_id(user: dict[str, Any]) -> str:
    return str(user.get("id") or "").strip()


def _username(user: dict[str, Any]) -> str:
    return str(user.get("username") or "").strip()


def _is_admin(user: dict[str, Any]) -> bool:
    return str(user.get("role") or "").strip().lower() == "admin"


class ReportRegistry:
    """Repository-backed saved-report operations with lightweight ownership."""

    def __init__(self, repository: MetadataRepository):
        self.repository = repository

    def list(self, user: dict[str, Any]) -> list[dict[str, Any]]:
        reports = self.repository.read()
        if _is_admin(user):
            return reports

        uid = _user_id(user)
        # Legacy reports have no owner. They remain visible for backward
        # compatibility and become owned by the first user who updates them.
        return [
            item
            for item in reports
            if not item.get("owner_id") or str(item.get("owner_id")) == uid
        ]

    def get(self, report_id: str, user: dict[str, Any]) -> dict[str, Any] | None:
        report = next(
            (item for item in self.repository.read() if str(item.get("id")) == str(report_id)),
            None,
        )
        if report is None:
            return None
        if _is_admin(user) or not report.get("owner_id"):
            return report
        if str(report.get("owner_id")) == _user_id(user):
            return report
        return None

    def save(self, payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        report_id = str(payload.get("id") or _new_id()).strip()
        name = str(payload.get("name") or "Untitled Report").strip() or "Untitled Report"
        definition = payload.get("definition")
        if not isinstance(definition, dict):
            raise ValueError("Report definition must be an object.")

        reports = self.repository.read()
        existing_index = next(
            (index for index, item in enumerate(reports) if str(item.get("id")) == report_id),
            None,
        )
        now = _now()

        if existing_index is None:
            item = {
                "id": report_id,
                "name": name,
                "definition": definition,
                "created_at": payload.get("created_at") or now,
                "updated_at": now,
                "owner_id": _user_id(user) or None,
                "owner_username": _username(user) or None,
                "version": 1,
            }
            reports.insert(0, item)
        else:
            existing = dict(reports[existing_index])
            owner_id = str(existing.get("owner_id") or "").strip()
            if owner_id and not _is_admin(user) and owner_id != _user_id(user):
                raise PermissionError("You do not have permission to modify this report.")

            # A legacy report with no owner is claimed by the first user who
            # successfully updates it. Admin ownership remains unchanged.
            item = {
                **existing,
                "id": report_id,
                "name": name,
                "definition": definition,
                "created_at": existing.get("created_at") or payload.get("created_at") or now,
                "updated_at": now,
                "owner_id": existing.get("owner_id") or (_user_id(user) or None),
                "owner_username": existing.get("owner_username") or (_username(user) or None),
                "version": max(1, int(existing.get("version") or 1)) + 1,
            }
            reports[existing_index] = item

        self.repository.write(reports)
        return item

    def delete(self, report_id: str, user: dict[str, Any]) -> bool:
        reports = self.repository.read()
        index = next(
            (index for index, item in enumerate(reports) if str(item.get("id")) == str(report_id)),
            None,
        )
        if index is None:
            return False

        existing = reports[index]
        owner_id = str(existing.get("owner_id") or "").strip()
        if owner_id and not _is_admin(user) and owner_id != _user_id(user):
            raise PermissionError("You do not have permission to delete this report.")

        reports.pop(index)
        self.repository.write(reports)
        return True

    def duplicate(self, report_id: str, user: dict[str, Any], name: str | None = None) -> dict[str, Any] | None:
        source = self.get(report_id, user)
        if source is None:
            return None

        now = _now()
        new_id = _new_id()
        copy = {
            "id": new_id,
            "name": (str(name).strip() if name else f"Copy of {source.get('name') or 'Report'}") or "Copy of Report",
            "definition": dict(source.get("definition") or {}),
            "created_at": now,
            "updated_at": now,
            "owner_id": _user_id(user) or None,
            "owner_username": _username(user) or None,
            "version": 1,
            "copied_from": source.get("id"),
        }
        reports = self.repository.read()
        reports.insert(0, copy)
        self.repository.write(reports)
        return copy


def create_report_registry(repository: MetadataRepository | None = None) -> ReportRegistry:
    if repository is None:
        repository = create_metadata_repository(
            REPORTS_FILE,
            backend=METADATA_BACKEND,
            collection=REPORT_COLLECTION,
            db_path=METADATA_DB_FILE,
        )
    return ReportRegistry(repository)


REPORT_REGISTRY = create_report_registry()
