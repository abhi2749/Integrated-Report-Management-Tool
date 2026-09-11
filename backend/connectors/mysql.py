from __future__ import annotations

from typing import Any

import mysql.connector
from mysql.connector import Error as MySQLError

from .base import DataSourceConnector
from mysql_pushdown import build_projection, build_filter_clause, build_qualified_filter_clause, build_group_aggregation, quote_identifier
from config import MAX_PREVIEW_ROWS
from streaming import stream_fetchmany


class MySQLConnector(DataSourceConnector):
    source_type = "mysql"

    def _connect(self, database: str | None = None):
        return mysql.connector.connect(
            host=self.host,
            port=self.port,
            user=self.username,
            password=self.password,
            database=database,
        )

    def test_connection(self) -> dict[str, Any]:
        connection = None
        try:
            connection = self._connect()
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            cursor.close()
            return {
                "success": True,
                "source_type": self.source_type,
                "message": "MySQL connection successful",
                "server_version": str(version),
            }
        except MySQLError as error:
            return {
                "success": False,
                "source_type": self.source_type,
                "message": str(error),
            }
        finally:
            if connection and connection.is_connected():
                connection.close()

    def list_databases(self) -> list[str]:
        connection = None
        try:
            connection = self._connect()
            cursor = connection.cursor()
            cursor.execute("SHOW DATABASES")
            return [row[0] for row in cursor.fetchall()]
        finally:
            if connection and connection.is_connected():
                connection.close()

    def list_tables(self, database: str) -> list[dict[str, Any]]:
        connection = None
        try:
            connection = self._connect(database)
            cursor = connection.cursor()
            cursor.execute("SHOW FULL TABLES")
            return [
                {"name": row[0], "type": row[1]}
                for row in cursor.fetchall()
            ]
        finally:
            if connection and connection.is_connected():
                connection.close()

    def list_columns(self, database: str, table: str) -> list[dict[str, Any]]:
        connection = None
        try:
            connection = self._connect(database)
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT
                    COLUMN_NAME,
                    DATA_TYPE,
                    IS_NULLABLE,
                    COLUMN_KEY,
                    ORDINAL_POSITION
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
                """,
                (database, table),
            )
            return [
                {
                    "name": row["COLUMN_NAME"],
                    "data_type": row["DATA_TYPE"],
                    "nullable": row["IS_NULLABLE"],
                    "key": row["COLUMN_KEY"],
                    "position": row["ORDINAL_POSITION"],
                }
                for row in cursor.fetchall()
            ]
        finally:
            if connection and connection.is_connected():
                connection.close()


    def execute_dataset(
        self,
        dataset: dict[str, Any],
        *,
        pushdown_filters: list[dict[str, Any]] | None = None,
        required_columns: list[str] | None = None,
        pushdown_sorts: list[dict[str, Any]] | None = None,
        pushdown_limit: int | None = None,
        cancel_event=None,
    ) -> list[dict[str, Any]]:
        """Execute a report dataset using the connector-owned MySQL path."""
        connection = None
        cursor = None
        try:
            database = str(dataset.get("database") or "")
            table = str(dataset.get("table") or "")
            if not database or not table:
                raise ValueError("MySQL dataset requires database and table")

            connection = self._connect(database)

            columns: list[str] = []
            for field in required_columns or []:
                clean = str(field).rsplit(".", 1)[-1]
                if clean and clean not in columns:
                    columns.append(clean)

            for item in pushdown_filters or []:
                clean = str(item.get("field", "")).rsplit(".", 1)[-1]
                if clean and clean not in columns:
                    columns.append(clean)

            projection = build_projection(str(dataset.get("id") or ""), columns)
            where_sql = ""
            params: list[Any] = []
            if pushdown_filters:
                where_sql, params, _ = build_filter_clause(pushdown_filters)

            safe_table = "`" + table.replace("`", "``") + "`"
            query = f"SELECT {projection} FROM {safe_table}{where_sql}"

            sort_parts: list[str] = []
            for item in pushdown_sorts or []:
                field = str(item.get("field", "")).rsplit(".", 1)[-1].strip()
                direction = str(item.get("direction", "ASC")).upper()
                if field and direction in {"ASC", "DESC"}:
                    safe_field = quote_identifier(field)
                    sort_parts.append(f"{safe_field} {direction}")
            if sort_parts:
                query += " ORDER BY " + ", ".join(sort_parts)
            if pushdown_limit is not None and int(pushdown_limit) > 0:
                query += f" LIMIT {int(pushdown_limit)}"

            cursor = connection.cursor(dictionary=True, buffered=False)
            cursor.execute(query, params)

            rows: list[dict[str, Any]] = []
            for batch in stream_fetchmany(cursor):
                if cancel_event is not None and cancel_event.is_set(): raise InterruptedError("Execution cancelled")
                for row in batch:
                    if cancel_event is not None and cancel_event.is_set(): raise InterruptedError("Execution cancelled")
                    rows.append(dict(row))
            return rows
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if connection and connection.is_connected():
                connection.close()

    def execute_dataset_stream(self, dataset: dict[str, Any], *, pushdown_filters=None, required_columns=None, pushdown_sorts=None, pushdown_limit=None, pushdown_group_by=None, pushdown_aggregations=None, cancel_event=None):
        database = str(dataset.get("database") or ""); table = str(dataset.get("table") or "")
        if not database or not table: raise ValueError("MySQL dataset requires database and table")
        columns = []
        for field in required_columns or []:
            clean = str(field).rsplit(".", 1)[-1]
            if clean and clean not in columns: columns.append(clean)
        for item in pushdown_filters or []:
            clean = str(item.get("field", "")).rsplit(".", 1)[-1]
            if clean and clean not in columns: columns.append(clean)
        if pushdown_group_by or pushdown_aggregations:
            projection, group_fields, _ = build_group_aggregation(str(dataset.get("id") or ""), pushdown_group_by, pushdown_aggregations)
        else:
            projection = build_projection(str(dataset.get("id") or ""), columns); group_fields = []
        where_sql, params, _ = build_filter_clause(pushdown_filters or []) if pushdown_filters else ("", [], None)
        safe_table = "`" + table.replace("`", "``") + "`"
        query = f"SELECT {projection} FROM {safe_table}{where_sql}"
        if group_fields: query += " GROUP BY " + ", ".join(quote_identifier(field) for field in group_fields)
        sort_parts: list[str] = []
        for item in pushdown_sorts or []:
            field = str(item.get("field", "")).rsplit(".", 1)[-1].strip()
            direction = str(item.get("direction", "ASC")).upper()
            if field and direction in {"ASC", "DESC"}:
                safe_field = "`" + field.replace("`", "``") + "`"
                sort_parts.append(f"{safe_field} {direction}")
        if sort_parts:
            query += " ORDER BY " + ", ".join(sort_parts)
        if pushdown_limit is not None and int(pushdown_limit) > 0:
            query += f" LIMIT {int(pushdown_limit)}"
        connection = self._connect(database); cursor = connection.cursor(dictionary=True, buffered=False)
        try:
            cursor.execute(query, params)
            for batch in stream_fetchmany(cursor):
                if cancel_event is not None and cancel_event.is_set(): raise InterruptedError("Execution cancelled")
                for row in batch:
                    if cancel_event is not None and cancel_event.is_set():
                        raise InterruptedError("Execution cancelled")
                    yield dict(row)
        finally:
            try: cursor.close()
            finally:
                if connection and connection.is_connected(): connection.close()

    def execute_join_stream(
        self,
        left_dataset: dict[str, Any],
        right_dataset: dict[str, Any],
        join_def: dict[str, Any],
        *,
        required_by_dataset: dict[str, set[str]] | None = None,
        filters_by_dataset: dict[str, list[dict[str, Any]]] | None = None,
        pushdown_limit=None,
        cancel_event=None,
    ):
        """Stream a safe same-connection MySQL JOIN directly from MySQL."""
        join_type = str(join_def.get("join_type", "INNER")).strip().upper()
        if join_type not in {"INNER", "LEFT"}:
            raise ValueError("MySQL source JOIN pushdown supports INNER and LEFT JOIN only")

        left_id = str(left_dataset.get("id") or "left")
        right_id = str(right_dataset.get("id") or "right")
        left_db = str(left_dataset.get("database") or "")
        right_db = str(right_dataset.get("database") or "")
        left_table = str(left_dataset.get("table") or "")
        right_table = str(right_dataset.get("table") or "")
        left_col = str(join_def.get("left_column") or "")
        right_col = str(join_def.get("right_column") or "")
        if not all((left_db, right_db, left_table, right_table, left_col, right_col)):
            raise ValueError("MySQL source JOIN requires both database/table and JOIN columns")

        required = required_by_dataset or {}
        left_columns = sorted(set(required.get(left_id, set())) | {left_col})
        right_columns = sorted(set(required.get(right_id, set())) | {right_col})
        left_projection = ", ".join(
            f"{quote_identifier('l')}.{quote_identifier(column)} AS {quote_identifier(f'{left_id}.{column}')}"
            for column in left_columns
        ) or f"{quote_identifier('l')}.*"
        right_projection = ", ".join(
            f"{quote_identifier('r')}.{quote_identifier(column)} AS {quote_identifier(f'{right_id}.{column}')}"
            for column in right_columns
        ) or f"{quote_identifier('r')}.*"

        safe_left = f"{quote_identifier(left_db)}.{quote_identifier(left_table)}"
        safe_right = f"{quote_identifier(right_db)}.{quote_identifier(right_table)}"
        query = (
            f"SELECT {left_projection}, {right_projection} "
            f"FROM {safe_left} AS {quote_identifier('l')} "
            f"{join_type} JOIN {safe_right} AS {quote_identifier('r')} "
            f"ON {quote_identifier('l')}.{quote_identifier(left_col)} = "
            f"{quote_identifier('r')}.{quote_identifier(right_col)}"
        )

        params: list[Any] = []
        where_parts = []
        for dataset_id, alias in ((left_id, "l"), (right_id, "r")):
            clause, values, _ = build_qualified_filter_clause(
                (filters_by_dataset or {}).get(dataset_id, []), alias
            )
            if clause:
                where_parts.append(clause[7:])
                params.extend(values)
        if where_parts:
            query += " WHERE " + " AND ".join(f"({part})" for part in where_parts)
        if pushdown_limit is not None and int(pushdown_limit) > 0:
            query += f" LIMIT {int(pushdown_limit)}"

        connection = self._connect(left_db)
        cursor = connection.cursor(dictionary=True, buffered=False)
        try:
            cursor.execute(query, params)
            for batch in stream_fetchmany(cursor):
                if cancel_event is not None and cancel_event.is_set():
                    raise InterruptedError("Execution cancelled")
                for row in batch:
                    if cancel_event is not None and cancel_event.is_set():
                        raise InterruptedError("Execution cancelled")
                    yield dict(row)
        finally:
            try:
                cursor.close()
            finally:
                if connection and connection.is_connected():
                    connection.close()

    def preview(
        self,
        database: str,
        table: str,
        sample_limit: int = 25,
    ) -> dict[str, Any]:
        connection = None
        try:
            connection = self._connect(database)
            cursor = connection.cursor(dictionary=True)

            safe_db = "`" + database.replace("`", "``") + "`"
            safe_table = "`" + table.replace("`", "``") + "`"
            sample_limit = max(1, int(sample_limit))

            cursor.execute(
                f"SELECT COUNT(*) AS total_rows FROM {safe_db}.{safe_table}"
            )
            total_rows = int((cursor.fetchone() or {}).get("total_rows") or 0)

            cursor.execute(
                f"SELECT * FROM {safe_db}.{safe_table} LIMIT {sample_limit}"
            )
            raw_rows = cursor.fetchall()

            rows = [
                {
                    key: value if isinstance(value, (str, int, float, bool)) or value is None else str(value)
                    for key, value in row.items()
                }
                for row in raw_rows
            ]

            columns = self.list_columns(database, table)
            column_names = [column["name"] for column in columns]

            return {
                "success": True,
                "source_type": self.source_type,
                "database": database,
                "table": table,
                "total_rows": total_rows,
                "sample_rows": len(rows),
                "column_count": len(column_names),
                "columns": column_names,
                "rows": rows,
            }
        finally:
            if connection and connection.is_connected():
                connection.close()


def execute_dataset(
    dataset: dict[str, Any],
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Connector-registry handler for MySQL report execution."""
    connector = MySQLConnector(
        host=dataset.get("host"),
        port=int(dataset.get("port", 3306)),
        username=dataset.get("username"),
        password=dataset.get("password"),
    )
    return connector.execute_dataset(dataset, **kwargs)
