from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import (
    MAX_EXPORT_FILE_MB,
    MAX_JOIN_MEMORY_MB,
    MAX_QUERY_ROWS,
    QUERY_CHUNK_SIZE,
)


@dataclass(frozen=True)
class LargeDataPolicy:
    """Central policy for large report datasets.

    MAX_QUERY_ROWS=0 means there is no artificial application row ceiling.
    Other controls protect the server/browser independently.
    """
    report_row_limit: int = MAX_QUERY_ROWS
    chunk_size: int = QUERY_CHUNK_SIZE
    max_join_memory_mb: int = MAX_JOIN_MEMORY_MB
    max_export_file_mb: int = MAX_EXPORT_FILE_MB

    @property
    def dynamic_rows(self) -> bool:
        return self.report_row_limit == 0

    def validate_chunk_size(self) -> None:
        if self.chunk_size < 1:
            raise ValueError("QUERY_CHUNK_SIZE must be at least 1.")

    def validate_export_size(self, size_bytes: int) -> None:
        if size_bytes < 0:
            raise ValueError("Export size cannot be negative.")
        # A value of 0 means the application imposes no artificial export-size
        # ceiling. Physical storage, filesystem, and connector limitations remain.
        if self.max_export_file_mb > 0 and size_bytes > self.max_export_file_mb * 1024 * 1024:
            raise ValueError(
                f"Export exceeds the configured {self.max_export_file_mb} MB server limit."
            )

    def summary(self) -> dict[str, Any]:
        return {
            "report_row_limit": self.report_row_limit,
            "report_row_limit_mode": "dynamic" if self.dynamic_rows else "configured",
            "query_chunk_size": self.chunk_size,
            "max_join_memory_mb": self.max_join_memory_mb,
            "max_export_file_mb": self.max_export_file_mb,
            "server_side_filtering_required": True,
            "server_side_aggregation_preferred": True,
            "browser_full_dataset_rendering": False,
        }


POLICY = LargeDataPolicy()
POLICY.validate_chunk_size()
