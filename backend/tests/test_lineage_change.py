from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lineage_service import LineageRegistry, build_lineage
from metadata_repository import SqliteMetadataRepository
from query_model import QueryDefinition


def make_query() -> QueryDefinition:
    return QueryDefinition.model_validate({
        "datasets": [
            {"id": "meter", "connection_id": "mysql_1", "source_type": "mysql", "database": "pspcl", "table": "meters"},
            {"id": "reading", "connection_id": "mongo_1", "source_type": "mongodb", "database": "PSPCL_DATA", "object_name": "readings"},
        ],
        "joins": [{"left_dataset": "meter", "right_dataset": "reading", "left_column": "meter_id", "right_column": "meter_id", "join_type": "LEFT"}],
        "columns": [{"field": "meter.DISCOM", "alias": "Discom"}, {"field": "reading.energy", "alias": "Energy"}],
        "filters": [{"field": "meter.DISCOM", "operator": "=", "value": "PSPCL"}],
        "group_by": ["meter.DISCOM"],
        "aggregations": [{"function": "SUM", "field": "reading.energy", "alias": "Total Energy"}],
        "calculations": [{"alias": "Adjusted", "left_field": "reading.energy", "operation": "*", "right_value": 1.1}],
    })


def test_lineage_graph_contains_sources_datasets_columns_and_transformations():
    graph = build_lineage(make_query(), target_type="report", target_id="r1", target_label="Energy Report")
    types = {node["type"] for node in graph["nodes"]}
    assert {"report", "source", "dataset", "column", "join", "filter", "group_by", "aggregation", "calculation"} <= types
    assert any(edge["relation"] == "feeds" for edge in graph["edges"])
    assert any(edge["relation"] == "transforms" for edge in graph["edges"])


def test_lineage_does_not_store_passwords():
    query = QueryDefinition.model_validate({
        "datasets": [{"id": "d1", "connection_id": "c1", "source_type": "mysql", "database": "db", "table": "t", "password": "DO_NOT_STORE"}]
    })
    graph = build_lineage(query, target_type="report", target_id="r2")
    assert "DO_NOT_STORE" not in str(graph)


def test_lineage_registry_upserts_by_target(tmp_path):
    repo = SqliteMetadataRepository(tmp_path / "lineage.db", "lineage")
    registry = LineageRegistry(repo)
    first = registry.save(build_lineage(make_query(), target_type="report", target_id="r1"), {"id": "u1", "username": "alice"})
    second = registry.save(build_lineage(make_query(), target_type="report", target_id="r1"), {"id": "u1", "username": "alice"})
    assert first["id"] == second["id"] == "report:r1"
    assert len(repo.read()) == 1


def test_lineage_registry_supports_job_targets(tmp_path):
    repo = SqliteMetadataRepository(tmp_path / "lineage.db", "lineage")
    registry = LineageRegistry(repo)
    registry.save(build_lineage(make_query(), target_type="execution_job", target_id="job_123"))
    record = registry.get("execution_job", "job_123")
    assert record is not None
    assert record["target_type"] == "execution_job"
