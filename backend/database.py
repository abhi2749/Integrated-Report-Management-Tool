import heapq
import os
import pickle
import re
import tempfile
from functools import cmp_to_key
from itertools import chain, islice
from typing import Any

import mysql.connector
from mysql.connector import Error as MySQLError
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import clickhouse_connect

from config import MAX_PREVIEW_ROWS
from connection_registry import get_connection
from mysql_pushdown import build_projection, build_filter_clause
from mongodb_pushdown import build_pipeline
from join_engine import hash_join, choose_build_side, join_rows, estimate_join_memory
from resource_manager import RESOURCE_MANAGER
from streaming import stream_fetchmany
from connectors.execution_registry import register_execution_handler, execute_dataset
from connectors.mysql import execute_dataset as execute_mysql_dataset, MySQLConnector
from connectors.mongodb import MongoDBConnector
from connectors.clickhouse import execute_dataset as execute_clickhouse_dataset, ClickHouseConnector
from import_service import read_import_rows, iter_import_rows, IMPORTED_DATA_REGISTRY


def create_mysql_connection(host, port, username, password, database=None):
    return mysql.connector.connect(
        host=host,
        port=port,
        user=username,
        password=password,
        database=database,
    )


def test_mysql_connection(host, port, username, password):
    connection = None
    try:
        connection = create_mysql_connection(host, port, username, password)
        cursor = connection.cursor()
        cursor.execute("SHOW DATABASES")
        databases = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return {"success": True, "message": "MySQL connection successful", "databases": databases}
    except MySQLError as error:
        return {"success": False, "message": str(error), "databases": []}
    finally:
        if connection and connection.is_connected():
            connection.close()


def get_mysql_tables(host, port, username, password, database):
    connection = None
    try:
        connection = create_mysql_connection(host, port, username, password, database)
        cursor = connection.cursor()
        cursor.execute("SHOW FULL TABLES")
        tables = [{"name": row[0], "type": row[1]} for row in cursor.fetchall()]
        cursor.close()
        return {"success": True, "database": database, "tables": tables}
    except MySQLError as error:
        return {"success": False, "database": database, "message": str(error), "tables": []}
    finally:
        if connection and connection.is_connected():
            connection.close()


def get_mysql_columns(host, port, username, password, database, table):
    connection = None
    try:
        connection = create_mysql_connection(host, port, username, password, database)
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY, ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (database, table),
        )
        columns = [
            {
                "name": row["COLUMN_NAME"],
                "data_type": row["DATA_TYPE"],
                "nullable": row["IS_NULLABLE"],
                "key": row["COLUMN_KEY"],
                "position": row["ORDINAL_POSITION"],
            }
            for row in cursor.fetchall()
        ]
        cursor.close()
        return {"success": True, "database": database, "table": table, "columns": columns}
    except MySQLError as error:
        return {"success": False, "database": database, "table": table, "message": str(error), "columns": []}
    finally:
        if connection and connection.is_connected():
            connection.close()


def create_mongo_connection(host, port, username=None, password=None):
    if username and password:
        return MongoClient(
            host=host,
            port=port,
            username=username,
            password=password,
        )
    return MongoClient(host=host, port=port)


def test_mongodb_connection(host, port, username=None, password=None):
    client = None
    try:
        client = create_mongo_connection(host, port, username, password)
        client.admin.command("ping")
        return {
            "success": True,
            "message": "MongoDB connection successful",
            "databases": client.list_database_names(),
        }
    except PyMongoError as error:
        return {"success": False, "message": str(error), "databases": []}
    finally:
        if client:
            client.close()


def get_mongodb_collections(host, port, database, username=None, password=None):
    client = None
    try:
        client = create_mongo_connection(host, port, username, password)
        return {
            "success": True,
            "database": database,
            "collections": client[database].list_collection_names(),
        }
    except PyMongoError as error:
        return {"success": False, "database": database, "message": str(error), "collections": []}
    finally:
        if client:
            client.close()


def get_mongodb_fields(host, port, database, collection, username=None, password=None):
    client = None
    try:
        client = create_mongo_connection(host, port, username, password)
        fields = {}
        for document in client[database][collection].find().limit(100):
            for field, value in document.items():
                if field not in fields:
                    fields[field] = {"name": field, "data_type": type(value).__name__}
        return {
            "success": True,
            "database": database,
            "collection": collection,
            "fields": list(fields.values()),
        }
    except PyMongoError as error:
        return {
            "success": False,
            "database": database,
            "collection": collection,
            "message": str(error),
            "fields": [],
        }
    finally:
        if client:
            client.close()


def create_clickhouse_connection(host, port, username=None, password=None, database=None):
    return clickhouse_connect.get_client(
        host=host,
        port=port,
        username=username or "default",
        password=password or "",
        database=database or "default",
    )


def test_clickhouse_connection(host, port, username=None, password=None):
    client = None
    try:
        client = create_clickhouse_connection(host, port, username, password)
        client.command("SELECT 1")
        return {
            "success": True,
            "message": "ClickHouse connection successful",
            "server_version": str(client.server_version),
            "databases": [str(row[0]) for row in client.query("SHOW DATABASES").result_rows],
        }
    except Exception as error:
        return {"success": False, "message": str(error), "databases": []}
    finally:
        if client:
            client.close()


def get_clickhouse_databases(host, port, username=None, password=None):
    client = None
    try:
        client = create_clickhouse_connection(host, port, username, password)
        return {"success": True, "databases": [str(row[0]) for row in client.query("SHOW DATABASES").result_rows]}
    except Exception as error:
        return {"success": False, "message": str(error), "databases": []}
    finally:
        if client:
            client.close()


def _clickhouse_identifier(value: str) -> str:
    text = str(value)
    if not text or "\x00" in text:
        raise ValueError("Invalid ClickHouse identifier")
    return "`" + text.replace("`", "``") + "`"


def get_clickhouse_tables(host, port, username, password, database):
    client = None
    try:
        client = create_clickhouse_connection(host, port, username, password, database)
        result = client.query(
            "SELECT name, engine FROM system.tables WHERE database = {database:String} ORDER BY name",
            parameters={"database": database},
        )
        return {"success": True, "database": database, "tables": [{"name": row[0], "type": str(row[1])} for row in result.result_rows]}
    except Exception as error:
        return {"success": False, "database": database, "message": str(error), "tables": []}
    finally:
        if client:
            client.close()


def get_clickhouse_columns(host, port, username, password, database, table):
    client = None
    try:
        client = create_clickhouse_connection(host, port, username, password, database)
        result = client.query(
            """
            SELECT name, type, default_kind, default_expression, position
            FROM system.columns
            WHERE database = {database:String} AND table = {table:String}
            ORDER BY position
            """,
            parameters={"database": database, "table": table},
        )
        columns = [{
            "name": row[0], "data_type": row[1], "nullable": "Nullable" in str(row[1]),
            "key": "", "position": row[4], "default_kind": row[2], "default_expression": row[3]
        } for row in result.result_rows]
        return {"success": True, "database": database, "table": table, "columns": columns}
    except Exception as error:
        return {"success": False, "database": database, "table": table, "message": str(error), "columns": []}
    finally:
        if client:
            client.close()


def get_clickhouse_preview(host, port, username, password, database, table, sample_limit=25):
    client = None
    try:
        client = create_clickhouse_connection(host, port, username, password, database)
        sample_limit = max(1, int(sample_limit))
        safe_table = _clickhouse_identifier(table)
        total_rows = int(client.query(f"SELECT count() FROM {safe_table}").result_rows[0][0] or 0)
        result = client.query(f"SELECT * FROM {safe_table} LIMIT {sample_limit}")
        rows = []
        for raw in result.result_rows:
            row = {}
            for index, name in enumerate(result.column_names):
                value = raw[index]
                if value is None or isinstance(value, (str, int, float, bool)):
                    row[name] = value
                else:
                    row[name] = str(value)
            rows.append(row)
        columns = get_clickhouse_columns(host, port, username, password, database, table).get("columns", [])
        return {
            "success": True, "source_type": "clickhouse", "database": database, "table": table,
            "total_rows": total_rows, "sample_rows": len(rows), "column_count": len(columns),
            "columns": [item["name"] for item in columns], "rows": rows,
        }
    except Exception as error:
        return {"success": False, "source_type": "clickhouse", "database": database, "table": table, "message": str(error), "rows": [], "columns": []}
    finally:
        if client:
            client.close()


def _safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.$]*", value):
        raise ValueError(f"Unsafe identifier: {value}")
    return value


def _coerce_scalar(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    try:
        if text == "":
            return text
        if re.fullmatch(r"[-+]?\d+", text):
            return int(text)
        return float(text)
    except ValueError:
        return text


def _compare(actual, operator, expected):
    op = operator.upper()

    if op == "IS_NULL":
        return actual is None
    if op == "IS_NOT_NULL":
        return actual is not None

    if actual is None:
        return False

    if op in ("IN", "NOT_IN"):
        if isinstance(expected, str):
            candidates = [item.strip() for item in expected.split(",")]
        elif isinstance(expected, (list, tuple, set)):
            candidates = list(expected)
        else:
            candidates = [expected]
        candidates = [_coerce_scalar(item) for item in candidates]
        actual_value = _coerce_scalar(actual)
        matched = actual_value in candidates or str(actual) in [str(item) for item in candidates]
        return (not matched) if op == "NOT_IN" else matched

    if op == "BETWEEN":
        if isinstance(expected, str):
            parts = [item.strip() for item in expected.split(",", 1)]
        elif isinstance(expected, (list, tuple)):
            parts = list(expected)
        else:
            parts = []
        if len(parts) != 2:
            raise ValueError("BETWEEN requires two comma-separated values")
        low, high = _coerce_scalar(parts[0]), _coerce_scalar(parts[1])
        actual_value = _coerce_scalar(actual)
        try:
            return low <= actual_value <= high
        except TypeError:
            return str(low) <= str(actual_value) <= str(high)

    if op == "CONTAINS":
        return str(expected).lower() in str(actual).lower()
    if op == "NOT_CONTAINS":
        return str(expected).lower() not in str(actual).lower()
    if op == "STARTS_WITH":
        return str(actual).lower().startswith(str(expected).lower())
    if op == "ENDS_WITH":
        return str(actual).lower().endswith(str(expected).lower())

    expected = _coerce_scalar(expected)
    actual = _coerce_scalar(actual)
    try:
        if op == "=":
            return actual == expected
        if op == "!=":
            return actual != expected
        if op == ">":
            return actual > expected
        if op == "<":
            return actual < expected
        if op == ">=":
            return actual >= expected
        if op == "<=":
            return actual <= expected
    except TypeError:
        left, right = str(actual), str(expected)
        if op == "=": return left == right
        if op == "!=": return left != right
        if op == ">": return left > right
        if op == "<": return left < right
        if op == ">=": return left >= right
        if op == "<=": return left <= right

    raise ValueError(f"Unsupported filter operator: {operator}")


def _iter_filter_rows(rows, filters):
    """Yield rows matching filters without retaining the complete result."""
    if not filters:
        yield from rows
        return
    for row in rows:
        expression = None
        for index, item in enumerate(filters):
            matched = _compare(row.get(item["field"]), item["operator"], item.get("value"))
            if index == 0:
                expression = matched
            elif str(item.get("logic", "AND")).upper() == "OR":
                expression = expression or matched
            else:
                expression = expression and matched
        if expression:
            yield row


def _filter_rows(rows, filters):
    if not filters:
        return rows

    result = []

    for row in rows:
        expression = None

        for index, item in enumerate(filters):
            field = item["field"]
            operator = item["operator"]
            value = item.get("value")
            logic = item.get("logic", "AND").upper()

            matched = _compare(row.get(field), operator, value)

            if index == 0:
                expression = matched
            elif logic == "OR":
                expression = expression or matched
            else:
                expression = expression and matched

        if expression:
            result.append(row)

    return result


def _iter_sort_rows(rows, sorts, *, spill_memory_bytes=32 * 1024 * 1024):
    """Yield sorted rows with bounded in-memory chunks and disk-backed merging."""
    sorts = list(sorts or [])
    if not sorts:
        yield from rows
        return

    memory_budget = max(1, int(spill_memory_bytes or 1))

    def compare(left, right):
        for sort in sorts:
            field = sort["field"]
            direction = str(sort.get("direction", "ASC")).upper()
            left_value = left.get(field)
            right_value = right.get(field)
            if left_value == right_value:
                continue
            left_none = left_value is None
            right_none = right_value is None
            if left_none != right_none:
                result = 1 if left_none else -1
            else:
                try:
                    if left_value < right_value:
                        result = -1
                    elif left_value > right_value:
                        result = 1
                    else:
                        continue
                except TypeError:
                    left_text = str(left_value)
                    right_text = str(right_value)
                    if left_text < right_text:
                        result = -1
                    elif left_text > right_text:
                        result = 1
                    else:
                        continue
            if direction == "DESC":
                result = -result
            return result
        return 0

    row_key = cmp_to_key(compare)
    chunk_files = []
    chunk = []
    chunk_bytes = 0

    def flush_chunk(items):
        if not items:
            return
        items.sort(key=row_key)
        handle = tempfile.NamedTemporaryFile(mode="wb", prefix="report-sort-", suffix=".bin", delete=False)
        path = handle.name
        try:
            with handle:
                for item in items:
                    pickle.dump(item, handle, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        chunk_files.append(path)

    try:
        for row in rows:
            chunk.append(row)
            try:
                chunk_bytes += len(pickle.dumps(row, protocol=pickle.HIGHEST_PROTOCOL))
            except Exception:
                chunk_bytes += 1
            if chunk_bytes >= memory_budget:
                flush_chunk(chunk)
                chunk = []
                chunk_bytes = 0

        if not chunk_files:
            chunk.sort(key=row_key)
            yield from chunk
            return

        flush_chunk(chunk)
        streams = [open(path, "rb") for path in chunk_files]

        class HeapItem:
            __slots__ = ("row", "source")

            def __init__(self, row, source):
                self.row = row
                self.source = source

            def __lt__(self, other):
                result = compare(self.row, other.row)
                return result < 0 if result else self.source < other.source

        heap = []
        for index, stream in enumerate(streams):
            try:
                first = pickle.load(stream)
            except EOFError:
                continue
            heapq.heappush(heap, HeapItem(first, index))

        while heap:
            item = heapq.heappop(heap)
            yield item.row
            stream = streams[item.source]
            try:
                next_row = pickle.load(stream)
            except EOFError:
                continue
            heapq.heappush(heap, HeapItem(next_row, item.source))
    finally:
        for stream in locals().get("streams", []):
            try:
                stream.close()
            except Exception:
                pass
        for path in chunk_files:
            try:
                os.unlink(path)
            except OSError:
                pass


def _sort_rows(rows, sorts, *, spill_memory_bytes=32 * 1024 * 1024):
    """Backward-compatible materialized sort wrapper."""
    return list(_iter_sort_rows(rows, sorts, spill_memory_bytes=spill_memory_bytes))


def _fetch_mysql(dataset, pushdown_filters=None, required_columns=None):
    """Backward-compatible adapter to the connector-owned MySQL executor."""
    return execute_mysql_dataset(
        dataset,
        pushdown_filters=pushdown_filters,
        required_columns=required_columns,
    )

def _fetch_mongodb(
    dataset,
    pushdown_filters=None,
    required_columns=None,
    pushdown_sorts=None,
    pushdown_limit=None,
):
    """Backward-compatible adapter to the connector-owned MongoDB executor."""
    connector = MongoDBConnector(
        host=dataset.get("host"),
        port=dataset.get("port"),
        username=dataset.get("username"),
        password=dataset.get("password", ""),
    )
    return connector.execute_dataset(
        dataset,
        pushdown_filters=pushdown_filters,
        required_columns=required_columns,
        pushdown_sorts=pushdown_sorts,
        pushdown_limit=pushdown_limit,
    )


def _fetch_dataset(dataset):
    """Dispatch dataset execution through the connector registry."""
    return execute_dataset(dataset)


def _stream_dataset(
    dataset,
    *,
    pushdown_filters=None,
    required_columns=None,
    pushdown_sorts=None,
    pushdown_limit=None,
    cancel_event=None,
):
    """Return a lazy row iterable for JOIN execution.

    JOIN workflows keep the probe side lazy so the JOIN engine does not
    materialize every source before matching. Connector stream APIs own the
    source cursor and cleanup; imported rows are wrapped as a plain iterator.
    """
    source_type = str(dataset.get("source_type") or "").lower()
    if source_type == "mysql":
        connector = MySQLConnector(
            host=dataset.get("host"),
            port=dataset.get("port"),
            username=dataset.get("username"),
            password=dataset.get("password", ""),
        )
        return connector.execute_dataset_stream(
            dataset,
            pushdown_filters=pushdown_filters,
            required_columns=required_columns,
            pushdown_sorts=pushdown_sorts,
            pushdown_limit=pushdown_limit,
            cancel_event=cancel_event,
        )
    if source_type == "mongodb":
        connector = MongoDBConnector(
            host=dataset.get("host"),
            port=dataset.get("port"),
            username=dataset.get("username"),
            password=dataset.get("password", ""),
        )
        return connector.execute_dataset_stream(
            dataset,
            pushdown_filters=pushdown_filters,
            required_columns=required_columns,
            pushdown_sorts=pushdown_sorts,
            pushdown_limit=pushdown_limit,
            cancel_event=cancel_event,
        )
    if source_type == "clickhouse":
        connector = ClickHouseConnector(
            host=dataset.get("host"),
            port=int(dataset.get("port", 8123)),
            username=dataset.get("username") or "default",
            password=dataset.get("password") or "",
        )
        return connector.execute_dataset_stream(
            dataset,
            required_columns=required_columns,
            pushdown_filters=pushdown_filters,
            pushdown_sorts=pushdown_sorts,
            pushdown_limit=pushdown_limit,
            cancel_event=cancel_event,
        )
    if source_type == "imported":
        return iter_import_rows(dataset, sorted(required_columns or []))
    return iter(_fetch_dataset(dataset))


def _qualified(dataset_id, column):
    return f"{dataset_id}.{column}"


def _join(left_rows, right_rows, join_def):
    """Execute a validated application-side JOIN through the JOIN engine."""
    left_field = _qualified(join_def["left_dataset"], join_def["left_column"])
    right_field = _qualified(join_def["right_dataset"], join_def["right_column"])
    join_type = str(join_def.get("join_type", "INNER")).strip().upper()

    # Legacy relational transforms still require a concrete collection.
    return list(hash_join(
        left_rows,
        right_rows,
        left_field,
        right_field,
        join_type=join_type,
    ))


def _join_stream(left_rows, right_rows, join_def, *, cancel_event=None):
    """Return a lazy JOIN iterator for the result-store streaming path."""
    left_field = _qualified(join_def["left_dataset"], join_def["left_column"])
    right_field = _qualified(join_def["right_dataset"], join_def["right_column"])
    join_type = str(join_def.get("join_type", "INNER")).strip().upper()
    return hash_join(
        left_rows,
        right_rows,
        left_field,
        right_field,
        join_type=join_type,
        cancel_event=cancel_event,
    )


def _project_join_stream(rows, columns, limit=None):
    """Project JOIN rows lazily without materializing the complete result."""
    aliases = {}
    selected = []
    for item in columns or []:
        field = str(item.get("field", ""))
        if not field:
            continue
        if field not in selected:
            selected.append(field)
        alias = str(item.get("alias", "") or "").strip()
        if alias:
            aliases[field] = alias

    def projected():
        for row in rows:
            if selected:
                yield {
                    aliases.get(field, field): row.get(
                        field, row.get(str(field).rsplit(".", 1)[-1])
                    )
                    for field in selected
                }
            else:
                yield row

    stream = projected()
    if limit is not None and int(limit) > 0:
        return islice(stream, int(limit)), selected
    return stream, selected


def _hashable_group_value(value):
    if isinstance(value, dict):
        return tuple(sorted((str(k), _hashable_group_value(v)) for k, v in value.items()))
    if isinstance(value, list):
        return tuple(_hashable_group_value(v) for v in value)
    if isinstance(value, set):
        return tuple(sorted(_hashable_group_value(v) for v in value))
    try:
        hash(value)
        return value
    except TypeError:
        return str(value)


def _numeric_values(values):
    numeric = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            numeric.append(value)
            continue
        try:
            text = str(value).strip()
            if text == "":
                continue
            numeric.append(float(text))
        except (TypeError, ValueError):
            continue
    return numeric


def _aggregate_rows(rows, group_by, aggregations):
    """Aggregate rows incrementally without retaining every row in a group.

    The accumulator state scales with the number of distinct groups and
    requested aggregations rather than with the number of input rows.  The
    function accepts lists and lazy iterables and preserves group insertion
    order and the legacy aggregation semantics.
    """
    if not group_by and not aggregations:
        return rows

    aggregation_specs = []
    for aggregation in aggregations or []:
        function = str(aggregation["function"]).upper()
        field = aggregation["field"]
        alias = (aggregation.get("alias") or "").strip()
        if not alias:
            alias = f"{function}_{field.replace('.', '_')}"
        if function not in {"COUNT", "SUM", "AVG", "MIN", "MAX"}:
            raise ValueError(f"Unsupported aggregation function: {function}")
        aggregation_specs.append((function, field, alias))

    groups = {}
    order = []

    def create_state(group_values):
        state = {"values": group_values}
        for function, field, alias in aggregation_specs:
            state[alias] = {
                "function": function,
                "field": field,
                "count_non_null": 0,
                "numeric_sum": 0,
                "numeric_count": 0,
                "min_value": None,
                "max_value": None,
                "native_ok": True,
                "min_string": None,
                "max_string": None,
            }
        return state

    if not group_by:
        groups[()] = create_state(())
        order.append(())

    for row in rows:
        group_values = tuple(row.get(field) for field in group_by)
        key = tuple(_hashable_group_value(value) for value in group_values)
        if key not in groups:
            groups[key] = create_state(group_values)
            order.append(key)
        state = groups[key]

        for function, field, alias in aggregation_specs:
            value = row.get(field)
            accumulator = state[alias]

            if value is not None:
                accumulator["count_non_null"] += 1

            if function in {"SUM", "AVG"}:
                numeric = _numeric_values((value,))
                if numeric:
                    accumulator["numeric_sum"] += numeric[0]
                    accumulator["numeric_count"] += 1

            if function in {"MIN", "MAX"} and value is not None:
                text = str(value)
                if accumulator["min_string"] is None or text < accumulator["min_string"]:
                    accumulator["min_string"] = text
                if accumulator["max_string"] is None or text > accumulator["max_string"]:
                    accumulator["max_string"] = text

                if accumulator["native_ok"]:
                    try:
                        if accumulator["min_value"] is None or value < accumulator["min_value"]:
                            accumulator["min_value"] = value
                        if accumulator["max_value"] is None or value > accumulator["max_value"]:
                            accumulator["max_value"] = value
                    except TypeError:
                        accumulator["native_ok"] = False
                        accumulator["min_value"] = None
                        accumulator["max_value"] = None

    result = []
    for key in order:
        state = groups[key]
        output = {}
        for index, field in enumerate(group_by):
            output[field] = state["values"][index]

        for function, field, alias in aggregation_specs:
            accumulator = state[alias]
            if function == "COUNT":
                value = accumulator["count_non_null"]
            elif function == "SUM":
                value = accumulator["numeric_sum"] if accumulator["numeric_count"] else 0
            elif function == "AVG":
                value = (
                    accumulator["numeric_sum"] / accumulator["numeric_count"]
                    if accumulator["numeric_count"]
                    else None
                )
            elif function == "MIN":
                value = accumulator["min_value"] if accumulator["native_ok"] else accumulator["min_string"]
            else:  # MAX
                value = accumulator["max_value"] if accumulator["native_ok"] else accumulator["max_string"]
            output[alias] = value
        result.append(output)

    return result


def _calculate_row(original, calculated_columns):
    if not calculated_columns:
        return original
    allowed = {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "CONCAT", "IF_NULL", "COALESCE"}
    row = dict(original)
    for calc in calculated_columns:
        alias = str(calc.get("alias", "")).strip()
        left_field = calc.get("left_field")
        operation = str(calc.get("operation", "")).upper()
        right_field = calc.get("right_field")
        right_value = calc.get("right_value")
        if not alias or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_. $-]*", alias):
            raise ValueError(f"Invalid calculated column alias: {alias}")
        if operation not in allowed:
            raise ValueError(f"Unsupported calculated column operation: {operation}")
        if left_field not in row:
            raise ValueError(f"Calculated column field not found: {left_field}")
        left = row.get(left_field)
        right = row.get(right_field) if right_field else right_value
        if operation == "CONCAT":
            value = f"{'' if left is None else left}{'' if right is None else right}"
        elif operation == "IF_NULL":
            value = right if left is None else left
        elif operation == "COALESCE":
            value = left if left is not None else right
        elif operation == "ADD":
            value = (float(left) if left is not None else 0) + (float(right) if right is not None else 0)
        elif operation == "SUBTRACT":
            value = (float(left) if left is not None else 0) - (float(right) if right is not None else 0)
        elif operation == "MULTIPLY":
            value = (float(left) if left is not None else 0) * (float(right) if right is not None else 0)
        elif operation == "DIVIDE":
            if right in (0, 0.0, "0", None):
                value = None
            else:
                value = (float(left) if left is not None else 0) / float(right)
        row[alias] = value
    return row


def _calculate_rows(rows, calculated_columns):
    if not calculated_columns:
        return rows
    return [_calculate_row(row, calculated_columns) for row in rows]


def _iter_calculate_rows(rows, calculated_columns):
    for row in rows:
        yield _calculate_row(row, calculated_columns)


def _resolve_report_dataset(dataset):
    """
    Resolve a reporting dataset through the existing saved connection registry.

    The frontend supplies connection_id, database and object/table information.
    Credentials remain server-side and are never returned to the browser.
    Legacy callers that already provide host/port/username/password remain
    supported.
    """
    resolved = dict(dataset or {})
    connection_id = resolved.get("connection_id")

    # Imported datasets are local persistent data assets, not external DB
    # connections. They must bypass the host/port/credential requirements
    # used by MySQL, MongoDB and ClickHouse datasets.
    if str(resolved.get("source_type", "")).strip().lower() == "imported":
        resolved.setdefault("database", "local_imports")
        resolved["table"] = (
            resolved.get("table")
            or resolved.get("object_name")
            or resolved.get("name")
        )
        required_imported = ["id", "source_type", "database", "table"]
        missing_imported = [
            key for key in required_imported
            if resolved.get(key) in (None, "", 0)
        ]
        if missing_imported:
            raise ValueError(
                f"Imported dataset '{resolved.get('id', 'unknown')}' is missing: "
                + ", ".join(missing_imported)
            )
        return resolved

    if connection_id:
        saved = get_connection(str(connection_id))
        if not saved:
            raise ValueError(f"Saved connection not found: {connection_id}")

        resolved["source_type"] = (
            resolved.get("source_type")
            or saved.get("source_type")
            or ""
        )
        resolved["host"] = saved.get("host")
        resolved["port"] = int(saved.get("port") or 0)
        resolved["username"] = saved.get("username")
        resolved["password"] = saved.get("password")

    if not resolved.get("table"):
        resolved["table"] = (
            resolved.get("object_name")
            or resolved.get("collection")
        )

    required = ["id", "source_type", "host", "port", "database", "table"]
    missing = [key for key in required if resolved.get(key) in (None, "", 0)]

    if missing:
        raise ValueError(
            f"Dataset '{resolved.get('id', 'unknown')}' is missing: "
            + ", ".join(missing)
        )

    return resolved



def _same_source_join_eligible(datasets, joins):
    if len(joins or []) != 1:
        return False
    if len(datasets or []) != 2:
        return False
    left_id = joins[0].get("left_dataset")
    right_id = joins[0].get("right_dataset")
    by_id = {d.get("id"): d for d in datasets}
    if left_id not in by_id or right_id not in by_id:
        return False
    left = by_id[left_id]
    right = by_id[right_id]
    return (
        left.get("connection_id") == right.get("connection_id")
        and str(left.get("source_type", "")).lower()
        == str(right.get("source_type", "")).lower()
        and str(joins[0].get("join_type", "INNER")).upper() in {"INNER", "LEFT"}
    )



def _execute_report_query_unbounded(datasets, joins, columns, filters, sorts, group_by, aggregations, calculated_columns, limit, stream=False, cancel_event=None, execution_plan=None):
    try:
        # Resolve saved connection credentials before any DB connection is made.
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Execution cancelled")
        datasets = [_resolve_report_dataset(dataset) for dataset in datasets]

        if len(datasets) < 1:
            return {"success": False, "message": "At least one dataset is required."}

        dataset_map = {item["id"]: item for item in datasets}

        if len(dataset_map) != len(datasets):
            return {"success": False, "message": "Dataset IDs must be unique."}

        # True streaming is safe for the simple single-dataset path. Complex
        # joins/grouping/calculated columns retain the existing materialized
        # engine until a spill-aware relational pipeline is introduced.
        if stream and len(datasets) == 1 and not joins and not calculated_columns:
            ds = datasets[0]; ds_id = ds["id"]
            required = set()
            for item in columns or []:
                field = str(item.get("field", ""))
                if "." in field and field.rsplit(".", 1)[0] == ds_id: required.add(field.rsplit(".", 1)[1])
            push_filters = []
            for item in filters or []:
                if str(item.get("logic", "AND")).upper() != "AND": return _execute_report_query_unbounded(datasets, joins, columns, filters, sorts, group_by, aggregations, calculated_columns, limit, stream=False, cancel_event=cancel_event)
                field = str(item.get("field", "")); op=str(item.get("operator", "")).upper()
                if "." in field and field.rsplit(".",1)[0] == ds_id:
                    name=field.rsplit(".",1)[1]; required.add(name); push_filters.append({"field":name,"operator":op,"value":item.get("value")})
            for item in group_by or []:
                field = str(item)
                if "." in field and field.rsplit(".", 1)[0] == ds_id:
                    required.add(field.rsplit(".", 1)[1])
            for aggregation in aggregations or []:
                field = str(aggregation.get("field", ""))
                if field != "*" and "." in field and field.rsplit(".", 1)[0] == ds_id:
                    required.add(field.rsplit(".", 1)[1])
            source = str(ds.get("source_type", "")).lower()
            if source == "mysql":
                connector = __import__("connectors.mysql", fromlist=["MySQLConnector"]).MySQLConnector(host=ds.get("host"), port=int(ds.get("port",3306)), username=ds.get("username"), password=ds.get("password"))
                rows = connector.execute_dataset_stream(ds, pushdown_filters=push_filters, required_columns=sorted(required), pushdown_sorts=sorts or [], pushdown_limit=limit if limit and int(limit)>0 else None, pushdown_group_by=group_by or [], pushdown_aggregations=aggregations or [], cancel_event=cancel_event)
            elif source == "mongodb":
                connector = MongoDBConnector(host=ds.get("host"), port=int(ds.get("port",27017)), username=ds.get("username"), password=ds.get("password"))
                rows = connector.execute_dataset_stream(ds, pushdown_filters=push_filters, required_columns=sorted(required), pushdown_sorts=sorts or [], pushdown_limit=limit if limit and int(limit)>0 else None, pushdown_group_by=group_by or [], pushdown_aggregations=aggregations or [], cancel_event=cancel_event)
                if group_by:
                    group_names = {str(field).rsplit(".", 1)[-1] for field in group_by}
                    def _qualify_mongo_groups(source_rows):
                        for row in source_rows:
                            yield {(f"{ds_id}.{key}" if key in group_names else key): value for key, value in row.items()}
                    rows = _qualify_mongo_groups(rows)
            elif source == "clickhouse":
                connector = __import__("connectors.clickhouse", fromlist=["ClickHouseConnector"]).ClickHouseConnector(host=ds.get("host"), port=int(ds.get("port",8123)), username=ds.get("username") or "default", password=ds.get("password") or "")
                rows = connector.execute_dataset_stream(ds, required_columns=sorted(required), pushdown_filters=push_filters, pushdown_sorts=sorts or [], pushdown_limit=limit if limit and int(limit)>0 else None, pushdown_group_by=group_by or [], pushdown_aggregations=aggregations or [], cancel_event=cancel_event)
            else:
                return _execute_report_query_unbounded(datasets, joins, columns, filters, sorts, group_by, aggregations, calculated_columns, limit, stream=False, cancel_event=cancel_event)
            selected_columns = []
            aliases = {}
            for item in columns or []:
                field = str(item.get("field", ""))
                alias = str(item.get("alias", "") or "").strip()
                if field:
                    selected_columns.append(field)
                    if alias:
                        aliases[field] = alias

            def _stream_transformed_rows(source_rows):
                transformed = _iter_calculate_rows(source_rows, calculated_columns or [])
                for row in transformed:
                    if selected_columns:
                        yield {aliases.get(field, field): row.get(field) for field in selected_columns}
                    else:
                        yield row

            return {
                "success": True,
                "message": "Report query streaming",
                "dataset_count": 1,
                "join_count": 0,
                "total_rows": 0,
                "returned_rows": 0,
                "columns": [aliases.get(field, field) for field in selected_columns],
                "rows": [],
                "streaming_rows": _stream_transformed_rows(rows),
                "applied_filters": filters,
                "applied_sorts": sorts,
                "group_by": group_by or [],
                "aggregations": aggregations or [],
                "calculated_columns": calculated_columns or [],
            }

        # Determine the minimum set of fields required for the report.
        # This enables safe MySQL column projection before data leaves the DB.
        required_by_dataset = {item["id"]: set() for item in datasets}
        for join_def in joins or []:
            left_id = join_def.get("left_dataset")
            right_id = join_def.get("right_dataset")
            if left_id in required_by_dataset:
                required_by_dataset[left_id].add(str(join_def.get("left_column")))
            if right_id in required_by_dataset:
                required_by_dataset[right_id].add(str(join_def.get("right_column")))

        for item in columns or []:
            field = str(item.get("field", ""))
            if "." in field:
                ds_id, field_name = field.rsplit(".", 1)
                if ds_id in required_by_dataset:
                    required_by_dataset[ds_id].add(field_name)

        for item in group_by or []:
            field = str(item)
            if "." in field:
                ds_id, field_name = field.rsplit(".", 1)
                if ds_id in required_by_dataset:
                    required_by_dataset[ds_id].add(field_name)

        for item in aggregations or []:
            field = str(item.get("field", ""))
            if "." in field:
                ds_id, field_name = field.rsplit(".", 1)
                if ds_id in required_by_dataset:
                    required_by_dataset[ds_id].add(field_name)

        for item in sorts or []:
            field = str(item.get("field", ""))
            if "." in field:
                ds_id, field_name = field.rsplit(".", 1)
                if ds_id in required_by_dataset:
                    required_by_dataset[ds_id].add(field_name)

        for item in calculated_columns or []:
            for field in (item.get("left_field"), item.get("right_field")):
                if "." in str(field or ""):
                    ds_id, field_name = str(field).rsplit(".", 1)
                    if ds_id in required_by_dataset:
                        required_by_dataset[ds_id].add(field_name)

        # Only push filters that are direct physical columns belonging to a
        # dataset and where all filter logic is AND. OR groups stay application-
        # side to preserve the existing semantics exactly.
        filters_by_dataset = {item["id"]: [] for item in datasets}
        pushdown_filter_count = 0
        can_push_filters = all(
            str(item.get("logic", "AND")).upper() == "AND" for item in (filters or [])
        )

        if can_push_filters:
            for item in filters or []:
                field = str(item.get("field", ""))
                operator = str(item.get("operator", "")).upper()
                if "." not in field or operator not in {
                    "=", "!=", ">", "<", ">=", "<=", "CONTAINS",
                    "STARTS_WITH", "ENDS_WITH", "NOT_CONTAINS",
                    "IS_NULL", "IS_NOT_NULL", "IN", "NOT_IN", "BETWEEN"
                }:
                    continue
                ds_id, field_name = field.rsplit(".", 1)
                if ds_id in filters_by_dataset:
                    filters_by_dataset[ds_id].append({
                        "field": field_name,
                        "operator": operator,
                        "value": item.get("value"),
                    })
                    required_by_dataset[ds_id].add(field_name)
                    pushdown_filter_count += 1

        data = {}
        for item in datasets:
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("Execution cancelled")
            ds_id = item["id"]
            if joins:
                # JOIN execution consumes connector cursors lazily. Keep the
                # source rows as iterables instead of materializing every
                # dataset up front. The JOIN engine materializes only its
                # selected hash/build side.
                data[ds_id] = _stream_dataset(
                    item,
                    pushdown_filters=filters_by_dataset[ds_id],
                    required_columns=sorted(required_by_dataset[ds_id]),
                    cancel_event=cancel_event,
                )
            elif item["source_type"].lower() == "mysql":
                data[ds_id] = execute_dataset(
                    item,
                    pushdown_filters=filters_by_dataset[ds_id],
                    required_columns=sorted(required_by_dataset[ds_id]),
                )
            elif item["source_type"].lower() == "mongodb":
                mongo_sorts = []
                for sort_item in sorts or []:
                    field = str(sort_item.get("field", ""))
                    if "." in field:
                        source_id, field_name = field.rsplit(".", 1)
                        if source_id == ds_id:
                            mongo_sorts.append({
                                "field": field_name,
                                "direction": sort_item.get("direction", "ASC"),
                            })
                data[ds_id] = _fetch_mongodb(
                    item,
                    pushdown_filters=filters_by_dataset[ds_id],
                    required_columns=sorted(required_by_dataset[ds_id]),
                    pushdown_sorts=mongo_sorts,
                    # A final LIMIT can only be pushed safely when no later
                    # operation can change row order/count. Otherwise the
                    # limit belongs at the end of the lazy pipeline.
                    pushdown_limit=(
                        limit
                        if not joins and not filters and not sorts and not group_by
                        and not aggregations and not calculated_columns
                        else None
                    ),
                )
            elif item["source_type"].lower() == "imported":
                data[ds_id] = iter_import_rows(
                    item,
                    sorted(required_by_dataset[ds_id]),
                )
            else:
                data[ds_id] = _fetch_dataset(item)

        if joins:
            if (stream and len(joins) == 1 and can_push_filters and not sorts and not group_by and not aggregations and not calculated_columns
                    and all(str(ds.get("source_type", "")).lower() == "mysql" for ds in datasets)):
                join_def = joins[0]
                left_ds = dataset_map.get(join_def.get("left_dataset")); right_ds = dataset_map.get(join_def.get("right_dataset"))
                if (left_ds and right_ds and left_ds.get("connection_id") and left_ds.get("connection_id") == right_ds.get("connection_id")):
                    connector = MySQLConnector(host=left_ds.get("host"), port=int(left_ds.get("port",3306)), username=left_ds.get("username"), password=left_ds.get("password"))
                    native_rows = connector.execute_join_stream(left_ds, right_ds, join_def, required_by_dataset=required_by_dataset, filters_by_dataset=filters_by_dataset, pushdown_limit=limit if limit and int(limit)>0 else None, cancel_event=cancel_event)
                    projected_stream, stream_columns = _project_join_stream(native_rows, columns, limit=None)
                    return {"success": True, "message": "Report native MySQL JOIN streaming", "dataset_count": len(datasets), "join_count": 1, "total_rows": 0, "returned_rows": 0, "columns": stream_columns, "rows": [], "streaming_rows": projected_stream, "applied_filters": filters, "applied_sorts": sorts, "group_by": group_by or [], "aggregations": aggregations or [], "query_pushdown": {"enabled": True, "join_strategy": "native_mysql_join", "cross_source_join_supported": True}}
            first_join = joins[0]
            current = data[first_join["left_dataset"]]

            for join_def in joins:
                left_id = join_def["left_dataset"]
                right_id = join_def["right_dataset"]

                if left_id != first_join["left_dataset"] and not current:
                    current = []

                right_rows = data[right_id]
                if cancel_event is not None and cancel_event.is_set():
                    raise InterruptedError("Execution cancelled")

                # Raw JOINs with no post-processing can flow directly from
                # connector streams through the JOIN engine into ResultStore.
                # This removes the previous full JOIN-result list() boundary.
                can_stream_join = (
                    not filters
                    and not sorts
                    and not group_by
                    and not aggregations
                    and not calculated_columns
                )
                if stream:
                    # Keep the JOIN iterator lazy. The JOIN engine itself handles
                    # build-side hashing/spill; downstream filters, aggregation,
                    # sorting and projection consume it incrementally.
                    current = _join_stream(
                        current, right_rows, join_def, cancel_event=cancel_event
                    )
                else:
                    current = _join(current, right_rows, join_def)

            if stream and can_stream_join:
                projected_stream, stream_columns = _project_join_stream(
                    current, columns, limit=limit
                )
                return {
                    "success": True,
                    "message": "Report JOIN query streaming",
                    "dataset_count": len(datasets),
                    "join_count": len(joins),
                    "total_rows": 0,
                    "returned_rows": 0,
                    "columns": stream_columns,
                    "rows": [],
                    "streaming_rows": projected_stream,
                    "applied_filters": filters,
                    "applied_sorts": sorts,
                    "group_by": group_by or [],
                    "aggregations": aggregations or [],
                    "query_pushdown": {
                        "enabled": True,
                        "join_strategy": "application_join_streaming",
                        "cross_source_join_supported": True,
                    },
                }
        else:
            # A single dataset is a valid report source. JOIN Designer still
            # requires multiple datasets for JOIN workflows, but Report Builder
            # must also support the common single-table reporting workflow.
            current = data[datasets[0]["id"]]

        # Preserve the historical in-process contract for callers that
        # explicitly request materialized execution (stream=False). The
        # unified ExecutionManager path uses stream=True, so this compatibility
        # branch does not reintroduce a large-result boundary into normal jobs.
        if not stream:
            current = list(_iter_calculate_rows(current, calculated_columns or []))
            current = list(_iter_filter_rows(current, filters))
            total_after_filter = len(current)
            current = _aggregate_rows(current, group_by or [], aggregations or [])
            total_after_grouping = len(current)
            current = _sort_rows(current, sorts)
            limited = current if limit is None or int(limit) <= 0 else current[:int(limit)]

            all_columns = []
            for row in limited:
                for key in row.keys():
                    if key not in all_columns:
                        all_columns.append(key)

            if aggregations or group_by:
                selected_columns = all_columns
            elif columns:
                selected_columns = []
                for item in columns:
                    field = str(item.get("field", ""))
                    if field in all_columns and field not in selected_columns:
                        selected_columns.append(field)
            else:
                selected_columns = all_columns

            aliases = {}
            for item in columns or []:
                field = str(item.get("field", ""))
                alias = str(item.get("alias", "") or "").strip()
                if field in selected_columns and alias:
                    aliases[field] = alias

            result_rows = [
                {aliases.get(column, column): row.get(column) for column in selected_columns}
                for row in limited
            ]
            return {
                "success": True,
                "message": "Report query executed successfully",
                "dataset_count": len(datasets),
                "join_count": len(joins),
                "total_rows": total_after_filter,
                "grouped_rows": total_after_grouping,
                "returned_rows": len(result_rows),
                "columns": selected_columns,
                "rows": result_rows,
                "applied_filters": filters,
                "applied_sorts": sorts,
                "query_pushdown": {
                    "enabled": True,
                    "mysql_filters_pushed": pushdown_filter_count,
                    "mysql_projection_enabled": True,
                    "mysql_streaming_enabled": True,
                    "mongodb_filters_pushed": sum(
                        1 for ds_id, items in filters_by_dataset.items()
                        if next((d for d in datasets if d["id"] == ds_id), {}).get("source_type", "").lower() == "mongodb"
                        for _ in items
                    ),
                    "mongodb_projection_enabled": True,
                    "mongodb_pipeline_enabled": True,
                    "mongodb_batch_streaming_enabled": True,
                    "join_strategy": (
                        "same_source_optimized_candidate"
                        if _same_source_join_eligible(datasets, joins)
                        else "existing_join_engine"
                    ),
                    "cross_source_join_supported": True,
                },
                "group_by": group_by or [],
                "aggregations": aggregations or [],
                "calculated_columns": calculated_columns or [],
            }

        # From this point forward the normal unified execution pipeline stays
        # lazy. Filters, calculated columns, sorting and projection no longer
        # create a full Python list; the ResultStore is the durable result
        # boundary.
        current = _iter_calculate_rows(current, calculated_columns or [])
        current = _iter_filter_rows(current, filters)
        current = _aggregate_rows(current, group_by or [], aggregations or [])
        current = _iter_sort_rows(current, sorts)

        if limit is not None and int(limit) > 0:
            current = islice(current, int(limit))

        aliases = {}
        selected_columns = []
        for item in columns or []:
            field = str(item.get("field", ""))
            if field and field not in selected_columns:
                selected_columns.append(field)
            alias = str(item.get("alias", "") or "").strip()
            if field and alias:
                aliases[field] = alias

        if not selected_columns and group_by:
            selected_columns.extend(str(field) for field in group_by if str(field) not in selected_columns)
        for aggregation in aggregations or []:
            function = str(aggregation.get("function", "")).upper()
            field = str(aggregation.get("field", ""))
            alias = str(aggregation.get("alias", "") or "").strip() or f"{function}_{field.replace('.', '_')}"
            if alias and alias not in selected_columns:
                selected_columns.append(alias)

        # Preserve the legacy "all columns" behavior without consuming the
        # stream: peek one row and chain it back into the iterator.
        if not selected_columns:
            iterator = iter(current)
            try:
                first_row = next(iterator)
            except StopIteration:
                first_row = None
                iterator = iter(())
            if isinstance(first_row, dict):
                selected_columns = list(first_row.keys())
            current = chain((first_row,), iterator) if first_row is not None else iterator

        def project_rows(rows):
            for row in rows:
                if selected_columns:
                    yield {aliases.get(column, column): row.get(column) for column in selected_columns}
                else:
                    yield row

        projected_rows = project_rows(current)
        return {
            "success": True,
            "message": "Report query streaming",
            "dataset_count": len(datasets),
            "join_count": len(joins),
            "total_rows": 0,
            "grouped_rows": 0,
            "returned_rows": 0,
            "columns": [aliases.get(column, column) for column in selected_columns],
            "rows": [],
            "streaming_rows": projected_rows,
            "applied_filters": filters,
            "applied_sorts": sorts,
            "query_pushdown": {
                "enabled": True,
                "mysql_filters_pushed": pushdown_filter_count,
                "mysql_projection_enabled": True,
                "mysql_streaming_enabled": True,
                "mongodb_filters_pushed": sum(
                    1 for ds_id, items in filters_by_dataset.items()
                    if next((d for d in datasets if d["id"] == ds_id), {}).get("source_type", "").lower() == "mongodb"
                    for _ in items
                ),
                "mongodb_projection_enabled": True,
                "mongodb_pipeline_enabled": True,
                "mongodb_batch_streaming_enabled": True,
                "join_strategy": (
                    "same_source_optimized_candidate"
                    if _same_source_join_eligible(datasets, joins)
                    else "existing_join_engine"
                ),
                "cross_source_join_supported": True,
            },
            "group_by": group_by or [],
            "aggregations": aggregations or [],
            "calculated_columns": calculated_columns or [],
        }

    except (MySQLError, PyMongoError, ValueError, Exception) as error:
        return {
            "success": False,
            "message": str(error),
            "dataset_count": len(datasets),
            "join_count": len(joins),
            "total_rows": 0,
            "returned_rows": 0,
            "columns": [],
            "rows": [],
        }


def execute_join_request(request):
    """
    Backward-compatible adapter for the existing /join/execute endpoint.

    Converts the old two-dataset JOIN payload into the newer report-query
    engine so existing frontend calls continue to work.
    """
    dataset_a = request.get("dataset_a") or {}
    dataset_b = request.get("dataset_b") or {}

    if not dataset_a or not dataset_b:
        return {
            "success": False,
            "message": "dataset_a and dataset_b are required.",
            "rows": [],
            "columns": [],
        }

    join_type = str(request.get("join_type") or "INNER").upper()

    allowed = {"INNER", "LEFT", "RIGHT", "FULL"}
    if join_type not in allowed:
        return {
            "success": False,
            "message": f"Unsupported join type: {join_type}",
            "rows": [],
            "columns": [],
        }

    # The legacy endpoint expects A./B. prefixes in the result.
    datasets = [
        {
            **dataset_a,
            "id": "dataset_a",
        },
        {
            **dataset_b,
            "id": "dataset_b",
        },
    ]

    joins = [
        {
            "left_dataset": "dataset_a",
            "right_dataset": "dataset_b",
            "left_column": request.get("column_a"),
            "right_column": request.get("column_b"),
            "join_type": join_type,
        }
    ]

    result = execute_report_query(
        datasets=datasets,
        joins=joins,
        columns=[],
        filters=[],
        sorts=[],
        group_by=[],
        aggregations=[],
        calculated_columns=[],
        limit=int(request.get("limit") or 100),
    )

    if not result.get("success"):
        return result

    # Keep the response shape expected by the old Join Designer.
    return {
        "success": True,
        "message": "Join executed successfully",
        "join_type": join_type,
        "dataset_a": {
            "source_type": dataset_a.get("source_type"),
            "database": dataset_a.get("database"),
            "table": dataset_a.get("table"),
            "column": request.get("column_a"),
        },
        "dataset_b": {
            "source_type": dataset_b.get("source_type"),
            "database": dataset_b.get("database"),
            "table": dataset_b.get("table"),
            "column": request.get("column_b"),
        },
        "total_rows": result.get("total_rows", 0),
        "returned_rows": result.get("returned_rows", 0),
        "columns": result.get("columns", []),
        "rows": result.get("rows", []),
    }


def _json_safe(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _mysql_profile_column(cursor, database, table, column):
    quoted_db = "`" + database.replace("`", "``") + "`"
    quoted_table = "`" + table.replace("`", "``") + "`"
    quoted_column = "`" + column.replace("`", "``") + "`"

    query = f"""
        SELECT
            COUNT(*) AS total_count,
            SUM(CASE WHEN {quoted_column} IS NULL THEN 1 ELSE 0 END) AS null_count,
            COUNT(DISTINCT {quoted_column}) AS distinct_count,
            MIN({quoted_column}) AS min_value,
            MAX({quoted_column}) AS max_value
        FROM {quoted_db}.{quoted_table}
    """
    cursor.execute(query)
    row = cursor.fetchone() or {}
    total = int(row.get("total_count") or 0)
    nulls = int(row.get("null_count") or 0)
    return {
        "name": column,
        "null_count": nulls,
        "null_percent": (nulls / total * 100) if total else 0,
        "distinct_count": int(row.get("distinct_count") or 0),
        "min": _json_safe(row.get("min_value")),
        "max": _json_safe(row.get("max_value")),
    }


def _mongo_profile_column(collection, field, total_count):
    exists_filter = {field: {"$exists": True}}
    null_count = collection.count_documents({field: None})
    distinct_values = collection.distinct(field, exists_filter)

    values = collection.find(exists_filter, {field: 1, "_id": 0}).limit(100)
    examples = []
    for item in values:
        if field in item and item[field] is not None:
            examples.append(item[field])
            if len(examples) >= 1:
                break

    comparable = [v for v in examples if isinstance(v, (int, float, str))]
    minimum = None
    maximum = None
    if comparable:
        try:
            minimum = _json_safe(min(comparable))
            maximum = _json_safe(max(comparable))
        except TypeError:
            minimum = None
            maximum = None

    return {
        "name": field,
        "null_count": int(null_count),
        "null_percent": (null_count / total_count * 100) if total_count else 0,
        "distinct_count": len(distinct_values),
        "min": minimum,
        "max": maximum,
        "example": _json_safe(examples[0]) if examples else None,
    }


def preview_dataset(
    source_type,
    host,
    port,
    username,
    password,
    database,
    table,
    sample_limit=25,
):
    try:
        sample_limit = max(1, int(sample_limit or 25))
        source_type = str(source_type).lower().strip()

        if source_type == "mysql":
            connection = None
            try:
                connection = create_mysql_connection(
                    host, port, username, password, database
                )
                cursor = connection.cursor(dictionary=True)

                safe_db = "`" + database.replace("`", "``") + "`"
                safe_table = "`" + table.replace("`", "``") + "`"

                cursor.execute(
                    f"SELECT COUNT(*) AS total_rows FROM {safe_db}.{safe_table}"
                )
                total_rows = int((cursor.fetchone() or {}).get("total_rows") or 0)

                cursor.execute(
                    """
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s
                      AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                    """,
                    (database, table),
                )
                metadata = cursor.fetchall()
                column_names = [row["COLUMN_NAME"] for row in metadata]

                cursor.execute(
                    f"SELECT * FROM {safe_db}.{safe_table} LIMIT {sample_limit}"
                )
                raw_rows = cursor.fetchall()
                rows = [
                    {key: _json_safe(value) for key, value in row.items()}
                    for row in raw_rows
                ]

                profiles = []
                for item in metadata:
                    profile = _mysql_profile_column(
                        cursor, database, table, item["COLUMN_NAME"]
                    )
                    profile["data_type"] = item["DATA_TYPE"]
                    profile["example"] = (
                        rows[0].get(item["COLUMN_NAME"]) if rows else None
                    )
                    profiles.append(profile)

                cursor.close()

                return {
                    "success": True,
                    "source_type": "mysql",
                    "database": database,
                    "table": table,
                    "total_rows": total_rows,
                    "sample_rows": len(rows),
                    "column_count": len(column_names),
                    "columns": column_names,
                    "column_profiles": profiles,
                    "rows": rows,
                }
            finally:
                if connection and connection.is_connected():
                    connection.close()

        if source_type == "clickhouse":
            return get_clickhouse_preview(host, port, username, password, database, table, sample_limit)

        if source_type == "mongodb":
            client = None
            try:
                client = create_mongo_connection(
                    host, port, username, password
                )
                collection = client[database][table]
                total_rows = collection.count_documents({})

                documents = list(collection.find().limit(sample_limit))
                rows = []
                all_fields = set()

                for document in documents:
                    converted = {}
                    for key, value in document.items():
                        all_fields.add(key)
                        converted[key] = _json_safe(value)
                    rows.append(converted)

                column_names = sorted(all_fields)
                profiles = []

                for field in column_names:
                    field_profile = _mongo_profile_column(
                        collection, field, total_rows
                    )
                    examples = [
                        row.get(field)
                        for row in rows
                        if row.get(field) is not None
                    ]
                    field_profile["data_type"] = (
                        type(examples[0]).__name__ if examples else "unknown"
                    )
                    field_profile["example"] = examples[0] if examples else None
                    profiles.append(field_profile)

                return {
                    "success": True,
                    "source_type": "mongodb",
                    "database": database,
                    "table": table,
                    "total_rows": total_rows,
                    "sample_rows": len(rows),
                    "column_count": len(column_names),
                    "columns": column_names,
                    "column_profiles": profiles,
                    "rows": rows,
                }
            finally:
                if client:
                    client.close()

        return {
            "success": False,
            "message": f"Unsupported source type: {source_type}",
            "rows": [],
            "column_profiles": [],
        }

    except (MySQLError, PyMongoError, ValueError, TypeError) as error:
        return {
            "success": False,
            "message": str(error),
            "rows": [],
            "column_profiles": [],
        }


def _execute_mongodb_dataset(dataset, **kwargs):
    connector = MongoDBConnector(
        host=dataset.get("host"),
        port=dataset.get("port"),
        username=dataset.get("username"),
        password=dataset.get("password", ""),
    )
    return connector.execute_dataset(dataset, **kwargs)


# Register the existing handlers behind the connector execution boundary.
# Keeping registration here is intentional for this incremental migration:
# connector-specific implementation code can move into connectors/ later
# without changing the report execution API.
register_execution_handler("mysql", execute_mysql_dataset)
register_execution_handler("mongodb", _execute_mongodb_dataset)
register_execution_handler("clickhouse", execute_clickhouse_dataset)


def execute_report_query(*args, **kwargs):
    """Execute a report under the server's concurrent-resource guard."""
    with RESOURCE_MANAGER.report_slot():
        return _execute_report_query_unbounded(*args, **kwargs)
