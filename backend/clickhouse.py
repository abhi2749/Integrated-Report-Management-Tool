from __future__ import annotations

from typing import Any

import clickhouse_connect

from .base import DataSourceConnector


class ClickHouseConnector(DataSourceConnector):
    """ClickHouse connector using the ClickHouse HTTP interface."""

    source_type = "clickhouse"

    def _client(self, database: str | None = None):
        return clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            username=self.username or "default",
            password=self.password or "",
            database=database or "default",
        )

    def test_connection(self) -> dict[str, Any]:
        client = None
        try:
            client = self._client()
            version = client.server_version
            client.command("SELECT 1")
            return {
                "success": True,
                "source_type": self.source_type,
                "message": "ClickHouse connection successful",
                "server_version": str(version),
            }
        except Exception as error:
            return {
                "success": False,
                "source_type": self.source_type,
                "message": str(error),
            }
        finally:
            if client:
                client.close()

    def list_databases(self) -> list[str]:
        client = None
        try:
            client = self._client()
            result = client.query("SHOW DATABASES")
            return [str(row[0]) for row in result.result_rows]
        finally:
            if client:
                client.close()

    def list_tables(self, database: str) -> list[dict[str, Any]]:
        client = None
        try:
            client = self._client(database)
            result = client.query(
                "SELECT name, engine FROM system.tables WHERE database = {database:String} ORDER BY name",
                parameters={"database": database},
            )
            return [{"name": row[0], "type": str(row[1])} for row in result.result_rows]
        finally:
            if client:
                client.close()

    def list_columns(self, database: str, table: str) -> list[dict[str, Any]]:
        client = None
        try:
            client = self._client(database)
            result = client.query(
                """
                SELECT name, type, default_kind, default_expression, position
                FROM system.columns
                WHERE database = {database:String} AND table = {table:String}
                ORDER BY position
                """,
                parameters={"database": database, "table": table},
            )
            return [
                {
                    "name": row[0],
                    "data_type": row[1],
                    "nullable": "Nullable" in str(row[1]),
                    "key": "",
                    "position": row[4],
                    "default_kind": row[2],
                    "default_expression": row[3],
                }
                for row in result.result_rows
            ]
        finally:
            if client:
                client.close()

    def preview(self, database: str, table: str, sample_limit: int = 25) -> dict[str, Any]:
        client = None
        try:
            client = self._client(database)
            sample_limit = max(1, int(sample_limit))
            columns = self.list_columns(database, table)
            safe_table = _quote_identifier(table)
            count_result = client.query(f"SELECT count() FROM {safe_table}")
            total_rows = int(count_result.result_rows[0][0] or 0)
            result = client.query(f"SELECT * FROM {safe_table} LIMIT {sample_limit}")
            rows = []
            for raw in result.result_rows:
                row = {}
                for index, name in enumerate(result.column_names):
                    value = raw[index]
                    row[name] = _json_safe(value)
                rows.append(row)
            return {
                "success": True,
                "source_type": self.source_type,
                "database": database,
                "table": table,
                "total_rows": total_rows,
                "sample_rows": len(rows),
                "column_count": len(columns),
                "columns": [item["name"] for item in columns],
                "rows": rows,
            }
        finally:
            if client:
                client.close()


def _quote_identifier(value: str) -> str:
    text = str(value)
    if not text or "\x00" in text:
        raise ValueError("Invalid ClickHouse identifier")
    return "`" + text.replace("`", "``") + "`"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)
