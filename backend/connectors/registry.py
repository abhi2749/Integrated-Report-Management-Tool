from __future__ import annotations

from typing import Any

from .base import DataSourceConnector
from .mysql import MySQLConnector
from .mongodb import MongoDBConnector
from .clickhouse import ClickHouseConnector


CONNECTOR_REGISTRY: dict[str, type[DataSourceConnector]] = {
    "mysql": MySQLConnector,
    "mongodb": MongoDBConnector,
    "clickhouse": ClickHouseConnector,
}


def get_connector_class(source_type: str) -> type[DataSourceConnector]:
    normalized = str(source_type).lower().strip()

    if normalized not in CONNECTOR_REGISTRY:
        supported = ", ".join(sorted(CONNECTOR_REGISTRY))
        raise ValueError(
            f"Unsupported source_type '{source_type}'. "
            f"Supported connectors: {supported}"
        )

    return CONNECTOR_REGISTRY[normalized]


def create_connector(
    source_type: str,
    host: str,
    port: int,
    username: str | None = None,
    password: str | None = None,
) -> DataSourceConnector:
    connector_class = get_connector_class(source_type)
    return connector_class(
        host=host,
        port=port,
        username=username,
        password=password,
    )


def supported_connectors() -> list[dict[str, Any]]:
    return [
        {
            "source_type": source_type,
            "display_name": connector_class.__name__.replace("Connector", ""),
            "status": "available",
        }
        for source_type, connector_class in sorted(
            CONNECTOR_REGISTRY.items()
        )
    ]
