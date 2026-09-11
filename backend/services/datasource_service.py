from __future__ import annotations

from typing import Any

from connectors.registry import create_connector, supported_connectors
from connection_registry import get_connection


def datasource_test(
    source_type: str,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
) -> dict[str, Any]:
    connector = create_connector(
        source_type,
        host,
        port,
        username,
        password,
    )

    try:
        return connector.test_connection()
    except Exception as error:
        return {
            "success": False,
            "source_type": source_type,
            "message": str(error),
        }


def datasource_databases(
    source_type: str,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
) -> dict[str, Any]:
    connector = create_connector(
        source_type,
        host,
        port,
        username,
        password,
    )

    try:
        databases = connector.list_databases()
        return {
            "success": True,
            "source_type": source_type,
            "databases": databases,
        }
    except Exception as error:
        return {
            "success": False,
            "source_type": source_type,
            "message": str(error),
            "databases": [],
        }
    finally:
        connector.close()


def datasource_tables(
    source_type: str,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    database: str,
) -> dict[str, Any]:
    connector = create_connector(
        source_type,
        host,
        port,
        username,
        password,
    )

    try:
        tables = connector.list_tables(database)
        return {
            "success": True,
            "source_type": source_type,
            "database": database,
            "tables": tables,
        }
    except Exception as error:
        return {
            "success": False,
            "source_type": source_type,
            "database": database,
            "message": str(error),
            "tables": [],
        }
    finally:
        connector.close()


def datasource_columns(
    source_type: str,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    database: str,
    table: str,
) -> dict[str, Any]:
    connector = create_connector(
        source_type,
        host,
        port,
        username,
        password,
    )

    try:
        columns = connector.list_columns(database, table)
        return {
            "success": True,
            "source_type": source_type,
            "database": database,
            "table": table,
            "columns": columns,
        }
    except Exception as error:
        return {
            "success": False,
            "source_type": source_type,
            "database": database,
            "table": table,
            "message": str(error),
            "columns": [],
        }
    finally:
        connector.close()


def datasource_preview(
    source_type: str,
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    database: str,
    table: str,
    sample_limit: int = 25,
) -> dict[str, Any]:
    connector = create_connector(
        source_type,
        host,
        port,
        username,
        password,
    )

    try:
        return connector.preview(
            database,
            table,
            sample_limit,
        )
    except Exception as error:
        return {
            "success": False,
            "source_type": source_type,
            "database": database,
            "table": table,
            "message": str(error),
            "rows": [],
        }
    finally:
        connector.close()


def connector_catalog() -> dict[str, Any]:
    return {
        "success": True,
        "connectors": supported_connectors(),
    }


def _saved_connector(connection_id: str):
    connection = get_connection(connection_id)
    if not connection:
        raise ValueError(f"Saved connection '{connection_id}' was not found.")
    return connection, create_connector(
        connection["source_type"],
        connection["host"],
        int(connection["port"]),
        connection.get("username"),
        connection.get("password"),
    )


def saved_connection_test(connection_id: str) -> dict[str, Any]:
    connection, connector = _saved_connector(connection_id)
    try:
        result = connector.test_connection()
        result["connection_id"] = connection_id
        return result
    finally:
        connector.close()


def saved_connection_databases(connection_id: str) -> dict[str, Any]:
    connection, connector = _saved_connector(connection_id)
    try:
        return {"success": True, "connection_id": connection_id, "source_type": connection["source_type"], "databases": connector.list_databases()}
    finally:
        connector.close()


def saved_connection_tables(connection_id: str, database: str) -> dict[str, Any]:
    connection, connector = _saved_connector(connection_id)
    try:
        return {"success": True, "connection_id": connection_id, "source_type": connection["source_type"], "database": database, "tables": connector.list_tables(database)}
    finally:
        connector.close()


def saved_connection_columns(connection_id: str, database: str, table: str) -> dict[str, Any]:
    connection, connector = _saved_connector(connection_id)
    try:
        return {"success": True, "connection_id": connection_id, "source_type": connection["source_type"], "database": database, "table": table, "columns": connector.list_columns(database, table)}
    finally:
        connector.close()


def saved_connection_preview(connection_id: str, database: str, table: str, sample_limit: int = 25) -> dict[str, Any]:
    connection, connector = _saved_connector(connection_id)
    try:
        result = connector.preview(database, table, sample_limit)
        result["connection_id"] = connection_id
        return result
    finally:
        connector.close()
