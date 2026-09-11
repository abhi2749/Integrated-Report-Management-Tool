from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from report_registry import ReportRegistry
from metadata_repository import JsonMetadataRepository


def user(uid="u1", role="report_user"):
    return {"id": uid, "username": uid, "role": role}


def test_registry_create_update_and_versioning(tmp_path):
    repo = JsonMetadataRepository(tmp_path / "reports.json")
    registry = ReportRegistry(repo)
    first = registry.save({"id": "r1", "name": "A", "definition": {"x": 1}}, user())
    second = registry.save({"id": "r1", "name": "B", "definition": {"x": 2}}, user())
    assert first["version"] == 1
    assert second["version"] == 2
    assert second["owner_id"] == "u1"


def test_registry_blocks_other_user_from_mutating_owned_report(tmp_path):
    repo = JsonMetadataRepository(tmp_path / "reports.json")
    registry = ReportRegistry(repo)
    registry.save({"id": "r1", "name": "A", "definition": {}}, user("u1"))
    try:
        registry.save({"id": "r1", "name": "B", "definition": {}}, user("u2"))
        assert False, "Expected PermissionError"
    except PermissionError:
        pass
    try:
        registry.delete("r1", user("u2"))
        assert False, "Expected PermissionError"
    except PermissionError:
        pass


def test_registry_duplicate_assigns_new_owner(tmp_path):
    repo = JsonMetadataRepository(tmp_path / "reports.json")
    registry = ReportRegistry(repo)
    registry.save({"id": "r1", "name": "A", "definition": {"x": 1}}, user("u1"))
    copy = registry.duplicate("r1", user("u1"))
    assert copy["id"] != "r1"
    assert copy["owner_id"] == "u1"
    assert copy["copied_from"] == "r1"
