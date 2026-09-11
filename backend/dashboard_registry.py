from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import METADATA_DB_FILE

def _now():
    return datetime.now(timezone.utc).isoformat()


class DashboardRegistry:
    def __init__(self, db_path=None):
        default = METADATA_DB_FILE
        self.db_path = Path(db_path or default)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self):
        with self._connect() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS saved_dashboards ("
                "id TEXT PRIMARY KEY,name TEXT NOT NULL,definition_json TEXT NOT NULL,"
                "owner_id TEXT NOT NULL,owner_username TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,"
                "created_at TEXT NOT NULL,updated_at TEXT NOT NULL)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS dashboard_shares ("
                "dashboard_id TEXT NOT NULL,shared_with_id TEXT NOT NULL,shared_with_username TEXT NOT NULL,"
                "created_at TEXT NOT NULL,PRIMARY KEY (dashboard_id, shared_with_id))"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_dashboard_shares_user ON dashboard_shares(shared_with_id)"
            )
            c.commit()

    @staticmethod
    def _is_admin(user):
        return str(user.get("role", "")).lower() == "admin"

    @staticmethod
    def _owner(user):
        return str(user.get("id") or user.get("user_id") or user.get("username") or ""), str(user.get("username") or "")

    def _visible(self, row, user):
        if self._is_admin(user):
            return True
        owner_id = self._owner(user)[0]
        if str(row["owner_id"]) == owner_id:
            return True
        with self._connect() as c:
            shared = c.execute(
                "SELECT 1 FROM dashboard_shares WHERE dashboard_id=? AND shared_with_id=?",
                (row["id"], owner_id),
            ).fetchone()
        return shared is not None

    def _can_modify(self, row, user):
        return self._is_admin(user) or str(row["owner_id"]) == self._owner(user)[0]

    @staticmethod
    def _item(row):
        return {
            "id": row["id"],
            "name": row["name"],
            "definition": json.loads(row["definition_json"]),
            "owner_id": row["owner_id"],
            "owner_username": row["owner_username"],
            "version": row["version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list(self, user):
        with self._connect() as c:
            rows = c.execute("SELECT * FROM saved_dashboards ORDER BY updated_at DESC").fetchall()
        return [self._item(r) for r in rows if self._visible(r, user)]

    def get(self, dashboard_id, user):
        with self._connect() as c:
            row = c.execute("SELECT * FROM saved_dashboards WHERE id=?", (dashboard_id,)).fetchone()
        return None if row is None or not self._visible(row, user) else self._item(row)

    def save(self, dashboard_id, name, definition, user):
        owner_id, owner_username = self._owner(user)
        dashboard_id = str(dashboard_id).strip()
        name = str(name).strip()
        if not owner_id:
            raise ValueError("Authenticated user identity is required.")
        if not dashboard_id or not name:
            raise ValueError("Dashboard id and name are required.")
        now = _now()
        with self._connect() as c:
            old = c.execute("SELECT * FROM saved_dashboards WHERE id=?", (dashboard_id,)).fetchone()
            if old:
                if not self._can_modify(old, user):
                    raise PermissionError("You do not have permission to modify this dashboard.")
                version = int(old["version"]) + 1
                c.execute(
                    "UPDATE saved_dashboards SET name=?,definition_json=?,version=?,updated_at=? WHERE id=?",
                    (name, json.dumps(definition, ensure_ascii=False), version, now, dashboard_id),
                )
            else:
                version = 1
                c.execute(
                    "INSERT INTO saved_dashboards (id,name,definition_json,owner_id,owner_username,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (dashboard_id, name, json.dumps(definition, ensure_ascii=False), owner_id, owner_username, version, now, now),
                )
            c.commit()
        return self.get(dashboard_id, user)

    def delete(self, dashboard_id, user):
        with self._connect() as c:
            row = c.execute("SELECT * FROM saved_dashboards WHERE id=?", (dashboard_id,)).fetchone()
            if row is None:
                return False
            if not self._can_modify(row, user):
                raise PermissionError("You do not have permission to delete this dashboard.")
            c.execute("DELETE FROM dashboard_shares WHERE dashboard_id=?", (dashboard_id,))
            c.execute("DELETE FROM saved_dashboards WHERE id=?", (dashboard_id,))
            c.commit()
            return True

    def list_shares(self, dashboard_id, user):
        with self._connect() as c:
            row = c.execute("SELECT * FROM saved_dashboards WHERE id=?", (dashboard_id,)).fetchone()
            if row is None:
                return None
            if not self._can_modify(row, user):
                raise PermissionError("Only the dashboard owner or an admin can manage sharing.")
            shares = c.execute(
                "SELECT shared_with_id,shared_with_username,created_at FROM dashboard_shares WHERE dashboard_id=? ORDER BY shared_with_username",
                (dashboard_id,),
            ).fetchall()
        return [dict(s) for s in shares]

    def add_share(self, dashboard_id, shared_with_id, shared_with_username, user):
        shared_with_id = str(shared_with_id or "").strip()
        shared_with_username = str(shared_with_username or "").strip()
        if not shared_with_id or not shared_with_username:
            raise ValueError("A target user id and username are required.")
        with self._connect() as c:
            row = c.execute("SELECT * FROM saved_dashboards WHERE id=?", (dashboard_id,)).fetchone()
            if row is None:
                return None
            if not self._can_modify(row, user):
                raise PermissionError("Only the dashboard owner or an admin can manage sharing.")
            c.execute(
                "INSERT OR REPLACE INTO dashboard_shares (dashboard_id,shared_with_id,shared_with_username,created_at) VALUES (?,?,?,?)",
                (dashboard_id, shared_with_id, shared_with_username, _now()),
            )
            c.commit()
        return self.list_shares(dashboard_id, user)

    def remove_share(self, dashboard_id, shared_with_id, user):
        with self._connect() as c:
            row = c.execute("SELECT * FROM saved_dashboards WHERE id=?", (dashboard_id,)).fetchone()
            if row is None:
                return False
            if not self._can_modify(row, user):
                raise PermissionError("Only the dashboard owner or an admin can manage sharing.")
            cursor = c.execute(
                "DELETE FROM dashboard_shares WHERE dashboard_id=? AND shared_with_id=?",
                (dashboard_id, str(shared_with_id).strip()),
            )
            deleted = cursor.rowcount > 0
            c.commit()
        return deleted


DASHBOARD_REGISTRY = DashboardRegistry()
