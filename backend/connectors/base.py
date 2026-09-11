from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DataSourceConnector(ABC):
    """Common contract used by all reporting-tool data-source connectors."""

    source_type: str = "unknown"

    def __init__(
        self,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
    ):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password

    @abstractmethod
    def test_connection(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def list_databases(self) -> list[str]:
        ...

    @abstractmethod
    def list_tables(self, database: str) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def list_columns(self, database: str, table: str) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def preview(
        self,
        database: str,
        table: str,
        sample_limit: int = 25,
    ) -> dict[str, Any]:
        ...

    def close(self) -> None:
        """Optional connector cleanup hook."""
        return None
