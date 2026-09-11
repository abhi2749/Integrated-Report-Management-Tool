"""Backend data-lineage foundation for reports and execution jobs.

Lineage is derived from the canonical QueryDefinition so reports, dashboards,
imported datasets, and future semantic assets can share one lineage model.
Sensitive connection credentials are deliberately excluded.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import secrets

from config import METADATA_BACKEND, METADATA_DB_FILE, DATA_DIR
from metadata_repository import MetadataRepository, create_metadata_repository
from query_contract import canonical_query_from_payload
from query_model import QueryDefinition

LINEAGE_COLLECTION = "lineage"
LINEAGE_FILE = Path(DATA_DIR) / "lineage.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str = "lin") -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _node(node_id: str, node_type: str, label: str, **metadata: Any) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": node_type,
        "label": label,
        "metadata": {key: value for key, value in metadata.items() if value is not None},
    }


def _edge(edge_id: str, source: str, target: str, relation: str, **metadata: Any) -> dict[str, Any]:
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "relation": relation,
        "metadata": {key: value for key, value in metadata.items() if value is not None},
    }


def build_lineage(query: QueryDefinition, *, target_type: str, target_id: str,
                  target_label: str | None = None, owner: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a deterministic source-to-target lineage graph."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()

    def add_node(item: dict[str, Any]) -> None:
        if item["id"] not in seen_nodes:
            nodes.append(item)
            seen_nodes.add(item["id"])

    def add_edge(item: dict[str, Any]) -> None:
        if item["id"] not in seen_edges:
            edges.append(item)
            seen_edges.add(item["id"])

    target_node_id = f"{target_type}:{target_id}"
    add_node(_node(target_node_id, target_type, target_label or target_id,
                   owner_id=_text((owner or {}).get("id")),
                   owner_username=_text((owner or {}).get("username"))))

    dataset_nodes: dict[str, str] = {}
    for dataset in query.datasets:
        dataset_id = _text(dataset.id) or "unknown"
        ds_node = f"dataset:{dataset_id}"
        dataset_nodes[dataset_id] = ds_node
        add_node(_node(
            ds_node,
            "dataset",
            dataset_id,
            dataset_id=dataset_id,
            connection_id=_text(dataset.connection_id),
            source_type=_text(dataset.source_type),
            host=_text(dataset.host),
            database=_text(dataset.database),
            table=_text(dataset.table),
            object_name=_text(dataset.object_name),
        ))
        add_edge(_edge(_id("edge"), ds_node, target_node_id, "feeds"))

        # A source node is intentionally descriptive only; no credentials are
        # copied into lineage records.
        source_key = _text(dataset.connection_id) or ":".join(
            item for item in (_text(dataset.source_type), _text(dataset.host), _text(dataset.port)) if item
        )
        if source_key:
            source_node = f"source:{source_key}"
            add_node(_node(source_node, "source", source_key,
                           connection_id=_text(dataset.connection_id),
                           source_type=_text(dataset.source_type),
                           host=_text(dataset.host)))
            add_edge(_edge(_id("edge"), source_node, ds_node, "contains"))

    def dataset_for_field(field: str) -> str | None:
        prefix = _text(field).split(".", 1)[0] if _text(field) else None
        return dataset_nodes.get(prefix) if prefix else None

    # Selected columns and query operations become explicit lineage nodes.
    for column in query.columns:
        field = _text(column.field) or "unknown"
        column_node = f"column:{field}"
        add_node(_node(column_node, "column", _text(column.alias) or field,
                       field=field, alias=_text(column.alias)))
        ds_node = dataset_for_field(field)
        if ds_node:
            add_edge(_edge(_id("edge"), ds_node, column_node, "provides"))
        add_edge(_edge(_id("edge"), column_node, target_node_id, "projects"))

    for index, join in enumerate(query.joins):
        join_node = f"join:{target_id}:{index}"
        add_node(_node(join_node, "join", f"{join.join_type} JOIN",
                       join_type=join.join_type,
                       left_dataset=join.left_dataset,
                       right_dataset=join.right_dataset,
                       left_column=join.left_column,
                       right_column=join.right_column))
        left_node = dataset_nodes.get(join.left_dataset)
        right_node = dataset_nodes.get(join.right_dataset)
        if left_node:
            add_edge(_edge(_id("edge"), left_node, join_node, "join_input", column=join.left_column))
        if right_node:
            add_edge(_edge(_id("edge"), right_node, join_node, "join_input", column=join.right_column))
        add_edge(_edge(_id("edge"), join_node, target_node_id, "transforms"))

    for index, item in enumerate(query.filters):
        op_node = f"filter:{target_id}:{index}"
        add_node(_node(op_node, "filter", f"{item.field} {item.operator}",
                       field=item.field, operator=item.operator, logic=item.logic))
        ds_node = dataset_for_field(item.field)
        if ds_node:
            add_edge(_edge(_id("edge"), ds_node, op_node, "filtered"))
        add_edge(_edge(_id("edge"), op_node, target_node_id, "transforms"))

    for index, field in enumerate(query.group_by):
        group_node = f"group:{target_id}:{index}"
        add_node(_node(group_node, "group_by", field, field=field))
        ds_node = dataset_for_field(field)
        if ds_node:
            add_edge(_edge(_id("edge"), ds_node, group_node, "groups"))
        add_edge(_edge(_id("edge"), group_node, target_node_id, "transforms"))

    for index, aggregation in enumerate(query.aggregations):
        agg_node = f"aggregation:{target_id}:{index}"
        add_node(_node(agg_node, "aggregation", f"{aggregation.function}({aggregation.field})",
                       function=aggregation.function, field=aggregation.field, alias=aggregation.alias))
        ds_node = dataset_for_field(aggregation.field)
        if ds_node:
            add_edge(_edge(_id("edge"), ds_node, agg_node, "aggregates"))
        add_edge(_edge(_id("edge"), agg_node, target_node_id, "transforms"))

    for index, calculation in enumerate(query.calculations):
        calc_node = f"calculation:{target_id}:{index}"
        add_node(_node(calc_node, "calculation", calculation.alias,
                       alias=calculation.alias,
                       left_field=calculation.left_field,
                       operation=calculation.operation,
                       right_field=calculation.right_field))
        for field in (calculation.left_field, calculation.right_field):
            ds_node = dataset_for_field(field or "")
            if ds_node:
                add_edge(_edge(_id("edge"), ds_node, calc_node, "calculation_input", field=field))
        add_edge(_edge(_id("edge"), calc_node, target_node_id, "calculates"))

    return {
        "lineage_version": 1,
        "target": {"type": target_type, "id": str(target_id)},
        "query_summary": {
            "dataset_count": len(query.datasets),
            "join_count": len(query.joins),
            "column_count": len(query.columns),
            "filter_count": len(query.filters),
            "group_by_count": len(query.group_by),
            "aggregation_count": len(query.aggregations),
            "calculation_count": len(query.calculations),
        },
        "nodes": nodes,
        "edges": edges,
    }


class LineageRegistry:
    def __init__(self, repository: MetadataRepository):
        self.repository = repository

    def save(self, graph: dict[str, Any], owner: dict[str, Any] | None = None) -> dict[str, Any]:
        target = graph.get("target") or {}
        target_type = str(target.get("type") or "unknown")
        target_id = str(target.get("id") or "")
        if not target_id:
            raise ValueError("Lineage target id is required.")
        records = self.repository.read()
        record_id = f"{target_type}:{target_id}"
        record = {
            "id": record_id,
            "target_type": target_type,
            "target_id": target_id,
            "owner_id": _text((owner or {}).get("id")),
            "owner_username": _text((owner or {}).get("username")),
            "created_at": next((item.get("created_at") for item in records if item.get("id") == record_id), _now()),
            "updated_at": _now(),
            "graph": graph,
        }
        records = [item for item in records if item.get("id") != record_id]
        records.insert(0, record)
        self.repository.write(records)
        return record

    def get(self, target_type: str, target_id: str) -> dict[str, Any] | None:
        key = f"{target_type}:{target_id}"
        return next((item for item in self.repository.read() if item.get("id") == key), None)


def create_lineage_registry(repository: MetadataRepository | None = None) -> LineageRegistry:
    if repository is None:
        repository = create_metadata_repository(
            LINEAGE_FILE,
            backend=METADATA_BACKEND,
            collection=LINEAGE_COLLECTION,
            db_path=METADATA_DB_FILE,
        )
    return LineageRegistry(repository)


LINEAGE_REGISTRY = create_lineage_registry()


def lineage_from_payload(payload: dict[str, Any], *, target_type: str, target_id: str,
                         target_label: str | None = None, owner: dict[str, Any] | None = None) -> dict[str, Any]:
    query = canonical_query_from_payload(payload)
    return build_lineage(query, target_type=target_type, target_id=target_id,
                         target_label=target_label, owner=owner)
