from __future__ import annotations

from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from config import MAX_PREVIEW_ROWS

SCHEMA_SAMPLE_ROWS = 1000  # metadata discovery sample; not a report/data-size ceiling
from .base import DataSourceConnector
from mongodb_pushdown import build_pipeline


class MongoDBConnector(DataSourceConnector):
    source_type = "mongodb"

    def _client(self):
        if self.username and self.password:
            return MongoClient(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
            )
        return MongoClient(host=self.host, port=self.port)

    def test_connection(self) -> dict[str, Any]:
        client = None
        try:
            client = self._client()
            client.admin.command("ping")
            server_info = client.server_info()
            return {
                "success": True,
                "source_type": self.source_type,
                "message": "MongoDB connection successful",
                "server_version": str(server_info.get("version", "")),
            }
        except PyMongoError as error:
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
            return client.list_database_names()
        finally:
            if client:
                client.close()

    def list_tables(self, database: str) -> list[dict[str, Any]]:
        client = None
        try:
            client = self._client()
            return [
                {"name": name, "type": "COLLECTION"}
                for name in client[database].list_collection_names()
            ]
        finally:
            if client:
                client.close()

    def list_columns(self, database: str, table: str) -> list[dict[str, Any]]:
        client = None
        try:
            client = self._client()
            collection = client[database][table]
            fields: dict[str, dict[str, Any]] = {}

            # Preserve the established MAX_PREVIEW_ROWS contract when it is explicitly
            # configured, while keeping schema discovery independently sampled when
            # the report-preview limit is unlimited (MAX_PREVIEW_ROWS == 0).
            schema_cursor = (
                collection.find().limit(MAX_PREVIEW_ROWS)
                if MAX_PREVIEW_ROWS > 0
                else collection.find().limit(SCHEMA_SAMPLE_ROWS)
            )
            for document in schema_cursor:
                for name, value in document.items():
                    if name not in fields:
                        fields[name] = {
                            "name": name,
                            "data_type": type(value).__name__,
                        }

            return list(fields.values())
        finally:
            if client:
                client.close()

    def execute_dataset(
        self,
        dataset: dict[str, Any],
        *,
        pushdown_filters: list[dict[str, Any]] | None = None,
        required_columns: list[str] | None = None,
        pushdown_sorts: list[dict[str, Any]] | None = None,
        pushdown_limit: int | None = None,
        pushdown_group_by: list[str] | None = None,
        pushdown_aggregations: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a report dataset using the connector-owned MongoDB path."""
        client = None
        try:
            database = str(dataset.get("database") or "")
            table = str(dataset.get("table") or "")
            if not database or not table:
                raise ValueError("MongoDB dataset requires database and table")

            client = self._client()
            collection = client[database][table]

            pipeline = build_pipeline(
                filters=pushdown_filters or [],
                columns=required_columns or [],
                sort=pushdown_sorts or [],
                limit=pushdown_limit,
                group_by=pushdown_group_by or [],
                aggregations=pushdown_aggregations or [],
            )

            cursor = collection.aggregate(
                pipeline,
                allowDiskUse=True,
                batchSize=5000,
            )

            prefix = f"{dataset.get('id')}."
            rows: list[dict[str, Any]] = []
            for document in cursor:
                rows.append({
                    f"{prefix}{key}": value
                    for key, value in dict(document).items()
                })
            return rows
        finally:
            if client:
                client.close()

    def execute_dataset_stream(self, dataset: dict[str, Any], *, pushdown_filters=None, required_columns=None, pushdown_sorts=None, pushdown_limit=None, pushdown_group_by=None, pushdown_aggregations=None, cancel_event=None):
        database = str(dataset.get("database") or ""); table = str(dataset.get("table") or "")
        if not database or not table: raise ValueError("MongoDB dataset requires database and table")
        client = self._client(); collection = client[database][table]
        pipeline = build_pipeline(filters=pushdown_filters or [], columns=required_columns or [], sort=pushdown_sorts or [], limit=pushdown_limit, group_by=pushdown_group_by or [], aggregations=pushdown_aggregations or [])
        cursor = collection.aggregate(pipeline, allowDiskUse=True, batchSize=5000); prefix=f"{dataset.get('id')}."
        try:
            for document in cursor:
                if cancel_event is not None and cancel_event.is_set(): raise InterruptedError("Execution cancelled")
                yield {f"{prefix}{key}": value for key, value in dict(document).items()}
        finally:
            client.close()

    def preview(
        self,
        database: str,
        table: str,
        sample_limit: int = 25,
    ) -> dict[str, Any]:
        client = None
        try:
            client = self._client()
            collection = client[database][table]
            sample_limit = max(1, int(sample_limit))

            total_rows = collection.count_documents({})
            documents = list(collection.find().limit(sample_limit))

            rows = []
            fields: list[str] = []

            for document in documents:
                row = {}
                for name, value in document.items():
                    if name not in fields:
                        fields.append(name)

                    if isinstance(value, (str, int, float, bool)) or value is None:
                        row[name] = value
                    else:
                        row[name] = str(value)

                rows.append(row)

            return {
                "success": True,
                "source_type": self.source_type,
                "database": database,
                "table": table,
                "total_rows": total_rows,
                "sample_rows": len(rows),
                "column_count": len(fields),
                "columns": fields,
                "rows": rows,
            }
        finally:
            if client:
                client.close()
