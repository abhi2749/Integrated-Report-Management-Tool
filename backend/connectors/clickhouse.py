from __future__ import annotations

from typing import Any

import clickhouse_connect

from .base import DataSourceConnector
from config import MAX_PREVIEW_ROWS


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

    def execute_dataset(
        self,
        dataset: dict[str, Any],
        required_columns: list[str] | None = None,
        pushdown_filters: list[dict[str, Any]] | None = None,
        pushdown_sorts: list[dict[str, Any]] | None = None,
        pushdown_limit: int | None = None,
        pushdown_group_by: list[str] | None = None,
        pushdown_aggregations: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute one report dataset using safe ClickHouse pushdown."""
        database = dataset.get("database") or "default"
        table = dataset.get("table") or dataset.get("object_name")
        if not table:
            raise ValueError("ClickHouse dataset table is required")

        columns = [str(c) for c in (required_columns or []) if str(c).strip()]
        group_fields = [str(field).rsplit(".", 1)[-1].strip() for field in (pushdown_group_by or []) if str(field).strip()]
        aggregations = list(pushdown_aggregations or [])
        if group_fields or aggregations:
            select_parts = [f"{_quote_identifier(field)} AS {_quote_identifier(f'{dataset.get('id')}.{field}')}" for field in group_fields]
            allowed_functions = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
            for item in aggregations:
                function = str(item.get("function", "")).upper().strip()
                field = str(item.get("field", "")).rsplit(".", 1)[-1].strip()
                if function not in allowed_functions or not field:
                    raise ValueError(f"Unsupported ClickHouse aggregation: {function}")
                expression = "count()" if function == "COUNT" and field == "*" else f"{function.lower()}({_quote_identifier(field)})"
                alias = str(item.get("alias") or f"{function}_{field}").strip()
                select_parts.append(f"{expression} AS {_quote_identifier(alias)}")
            select_sql = ", ".join(select_parts)
        else:
            select_sql = ", ".join(_quote_identifier(c) for c in columns) if columns else "*"
        query = f"SELECT {select_sql} FROM {_quote_identifier(str(table))}"
        parameters: dict[str, Any] = {}
        clauses: list[str] = []

        for index, item in enumerate(pushdown_filters or []):
            field = str(item.get("field", "")).strip()
            operator = str(item.get("operator", "")).strip().upper()
            if not field or operator not in {"=", "!=", ">", "<", ">=", "<=", "IS_NULL", "IS_NOT_NULL", "CONTAINS", "STARTS_WITH", "ENDS_WITH", "NOT_CONTAINS", "IN", "NOT_IN", "BETWEEN"}:
                continue
            qfield = _quote_identifier(field)
            if operator == "IS_NULL":
                clauses.append(f"{qfield} IS NULL")
            elif operator == "IS_NOT_NULL":
                clauses.append(f"{qfield} IS NOT NULL")
            elif operator in {"CONTAINS", "STARTS_WITH", "ENDS_WITH", "NOT_CONTAINS"}:
                value = str(item.get("value", ""))
                pattern = {"CONTAINS": f"%{value}%", "STARTS_WITH": f"{value}%", "ENDS_WITH": f"%{value}", "NOT_CONTAINS": f"%{value}%"}[operator]
                key=f"p{index}"; parameters[key]=pattern
                cmp="NOT LIKE" if operator == "NOT_CONTAINS" else "LIKE"
                clauses.append(f"{qfield} {cmp} {{{key}:String}}")
            else:
                key=f"p{index}"; parameters[key]=item.get("value")
                clauses.append(f"{qfield} {operator} {{${key}:String}}".replace("{$", "{"))

        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        if group_fields:
            query += " GROUP BY " + ", ".join(_quote_identifier(field) for field in group_fields)

        for item in pushdown_sorts or []:
            field = str(item.get("field", "")).strip()
            direction = str(item.get("direction", "ASC")).upper()
            if field and direction in {"ASC", "DESC"}:
                query += (" ORDER BY " if " ORDER BY " not in query else ", ") + f"{_quote_identifier(field)} {direction}"

        # A missing/zero pushdown limit means the canonical query is unbounded.
        # Never introduce an undocumented 10,000-row ceiling here: interactive
        # callers request a bounded limit explicitly, while full exports use 0.
        if pushdown_limit is not None and int(pushdown_limit) > 0:
            query += f" LIMIT {int(pushdown_limit)}"

        client = None
        try:
            client = self._client(database)
            result = client.query(query, parameters=parameters or None)
            rows = []
            names = list(result.column_names)
            for raw in result.result_rows:
                rows.append({f"{dataset.get('id')}.{name}": _json_safe(raw[i]) for i, name in enumerate(names)})
            return rows
        finally:
            if client:
                client.close()

    def execute_dataset_stream(self, dataset: dict[str, Any], required_columns=None, pushdown_filters=None, pushdown_sorts=None, pushdown_limit=None, pushdown_group_by=None, pushdown_aggregations=None, cancel_event=None):
        database = dataset.get("database") or "default"
        table = dataset.get("table") or dataset.get("object_name")
        if not table: raise ValueError("ClickHouse dataset table is required")
        columns = [str(c) for c in (required_columns or []) if str(c).strip()]
        group_fields = [str(field).rsplit(".", 1)[-1].strip() for field in (pushdown_group_by or []) if str(field).strip()]
        aggregations = list(pushdown_aggregations or [])
        if group_fields or aggregations:
            select_parts = [
                f"{_quote_identifier(field)} AS {_quote_identifier(f'{dataset.get('id')}.{field}')}"
                for field in group_fields
            ]
            allowed_functions = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
            for item in aggregations:
                function = str(item.get("function", "")).upper().strip()
                field_text = str(item.get("field", "")).strip()
                field = field_text.rsplit(".", 1)[-1].strip() if field_text != "*" else ""
                if function not in allowed_functions:
                    raise ValueError(f"Unsupported ClickHouse aggregation: {function}")
                if function == "COUNT":
                    expression = "count()" if not field else f"count({_quote_identifier(field)})"
                elif field:
                    expression = f"{function.lower()}({_quote_identifier(field)})"
                else:
                    raise ValueError(f"{function} requires a field")
                alias = str(item.get("alias") or f"{function}_{field or 'all'}").strip()
                select_parts.append(f"{expression} AS {_quote_identifier(alias)}")
            select_sql = ", ".join(select_parts) or "*"
        else:
            select_sql = ", ".join(_quote_identifier(c.rsplit(".", 1)[-1]) for c in columns) if columns else "*"
        query = f"SELECT {select_sql} FROM {_quote_identifier(str(table))}"
        parameters = {}; clauses = []
        for index, item in enumerate(pushdown_filters or []):
            field = str(item.get("field", "")).strip()
            op = str(item.get("operator", "")).upper()
            key = f"p{index}"
            if not field:
                continue
            q = _quote_identifier(field)
            if op == "IS_NULL":
                clauses.append(f"{q} IS NULL")
            elif op == "IS_NOT_NULL":
                clauses.append(f"{q} IS NOT NULL")
            elif op in {"CONTAINS", "STARTS_WITH", "ENDS_WITH", "NOT_CONTAINS"}:
                value = str(item.get("value", ""))
                pattern = {
                    "CONTAINS": f"%{value}%",
                    "STARTS_WITH": f"{value}%",
                    "ENDS_WITH": f"%{value}",
                    "NOT_CONTAINS": f"%{value}%",
                }[op]
                parameters[key] = pattern
                clauses.append(f"{q} {'NOT LIKE' if op == 'NOT_CONTAINS' else 'LIKE'} {{{key}:String}}")
            elif op in {"=", "!=", ">", "<", ">=", "<="}:
                parameters[key] = item.get("value")
                clauses.append(f"{q} {op} {{{key}:String}}")
            elif op in {"IN", "NOT_IN"}:
                values = item.get("value")
                if isinstance(values, (list, tuple, set)):
                    values = list(values)
                elif isinstance(values, str):
                    values = [v.strip() for v in values.split(",")]
                else:
                    values = [values]
                if not values:
                    clauses.append("1 = 0" if op == "IN" else "1 = 1")
                else:
                    placeholders = []
                    for value_index, value in enumerate(values):
                        value_key = f"{key}_{value_index}"
                        parameters[value_key] = value
                        placeholders.append(f"{{{value_key}:String}}")
                    clauses.append(f"{q} {'NOT IN' if op == 'NOT_IN' else 'IN'} ({', '.join(placeholders)})")
            elif op == "BETWEEN":
                value = item.get("value")
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    low, high = value
                elif isinstance(value, str):
                    parts = [v.strip() for v in value.split(",", 1)]
                    if len(parts) != 2:
                        continue
                    low, high = parts
                else:
                    continue
                parameters[f"{key}_low"] = low
                parameters[f"{key}_high"] = high
                clauses.append(f"{q} BETWEEN {{{key}_low:String}} AND {{{key}_high:String}}")
        if clauses: query += " WHERE " + " AND ".join(clauses)
        if group_fields:
            query += " GROUP BY " + ", ".join(_quote_identifier(field) for field in group_fields)
        parts=[]
        for item in pushdown_sorts or []:
            field=str(item.get("field","")).rsplit(".", 1)[-1].strip(); direction=str(item.get("direction","ASC")).upper()
            if field and direction in {"ASC","DESC"}: parts.append(f"{_quote_identifier(field)} {direction}")
        if parts: query += " ORDER BY " + ", ".join(parts)
        if pushdown_limit is not None and int(pushdown_limit)>0: query += f" LIMIT {int(pushdown_limit)}"
        client=self._client(database)
        try:
            with client.query_row_block_stream(query, parameters=parameters or None) as stream:
                names = list(stream.source.column_names)
                for block in stream:
                    for raw in block:
                        if cancel_event is not None and cancel_event.is_set():
                            raise InterruptedError("Execution cancelled")
                        yield {f"{dataset.get('id')}.{name}": _json_safe(raw[i]) for i, name in enumerate(names)}
        finally: client.close()

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



def execute_dataset(dataset: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
    """Connector-registry handler for ClickHouse report execution."""
    connector = ClickHouseConnector(
        host=dataset.get("host"),
        port=int(dataset.get("port", 8123)),
        username=dataset.get("username") or "default",
        password=dataset.get("password") or "",
    )
    return connector.execute_dataset(dataset, **kwargs)


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
