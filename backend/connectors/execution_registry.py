from __future__ import annotations

from typing import Any, Callable, Iterable

from .registry import get_connector_class

ExecutionHandler = Callable[..., Iterable[dict[str, Any]] | list[dict[str, Any]]]


class ConnectorExecutionRegistry:
    """Central dispatch boundary for dataset execution.

    Connector implementations own the source type contract, while the
    existing execution handlers can be migrated behind this boundary one at
    a time without changing report semantics.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, ExecutionHandler] = {}

    @staticmethod
    def normalize_source_type(source_type: str) -> str:
        text = str(source_type or "").strip().lower()
        if not text:
            raise ValueError("Dataset source_type is required")
        get_connector_class(text)  # validates against the connector registry
        return text

    def register(self, source_type: str, handler: ExecutionHandler) -> None:
        normalized = self.normalize_source_type(source_type)
        if not callable(handler):
            raise TypeError("Connector execution handler must be callable")
        self._handlers[normalized] = handler

    def has_handler(self, source_type: str) -> bool:
        normalized = self.normalize_source_type(source_type)
        return normalized in self._handlers

    def supported_source_types(self) -> list[str]:
        return sorted(self._handlers)

    def execute(self, dataset: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
        if not isinstance(dataset, dict):
            raise ValueError("Dataset must be a JSON object")

        source_type = self.normalize_source_type(dataset.get("source_type"))
        handler = self._handlers.get(source_type)
        if handler is None:
            raise RuntimeError(
                f"No execution handler registered for connector '{source_type}'."
            )

        result = handler(dataset, **kwargs)
        if result is None:
            return []
        if isinstance(result, list):
            return result
        if hasattr(result, "__iter__") and not isinstance(result, (str, bytes, dict)):
            return result
        raise TypeError(f"Connector '{source_type}' execution handler must return a list or iterable of rows.")


CONNECTOR_EXECUTION_REGISTRY = ConnectorExecutionRegistry()


def register_execution_handler(source_type: str, handler: ExecutionHandler) -> None:
    CONNECTOR_EXECUTION_REGISTRY.register(source_type, handler)


def execute_dataset(dataset: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
    return CONNECTOR_EXECUTION_REGISTRY.execute(dataset, **kwargs)
