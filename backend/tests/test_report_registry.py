from pathlib import Path

from metadata_repository import create_metadata_repository
from report_registry import ReportRegistry


def _registry(tmp_path: Path) -> ReportRegistry:
    repo = create_metadata_repository(
        tmp_path / "saved_reports.json",
        backend="sqlite",
        collection="saved_reports",
        db_path=tmp_path / "metadata.db",
    )
    return ReportRegistry(repo)


def _user(user_id="u1", username="alice", role="report_user"):
    return {"id": user_id, "username": username, "role": role}


def _payload(report_id="r1"):
    return {
        "id": report_id,
        "name": "Sales",
        "definition": {"visualization": "table", "datasets": []},
    }


def test_save_assigns_owner_and_starts_version(tmp_path):
    registry = _registry(tmp_path)
    report = registry.save(_payload(), _user())

    assert report["owner_id"] == "u1"
    assert report["owner_username"] == "alice"
    assert report["version"] == 1
    assert registry.get("r1", _user())["name"] == "Sales"


def test_update_increments_version_and_enforces_owner(tmp_path):
    registry = _registry(tmp_path)
    registry.save(_payload(), _user())

    updated = registry.save(
        {**_payload(), "name": "Sales Updated"},
        _user(),
    )
    assert updated["version"] == 2

    try:
        registry.save(_payload(), _user("u2", "bob"))
    except PermissionError:
        pass
    else:
        raise AssertionError("Expected PermissionError for another user's report")


def test_duplicate_creates_new_owned_report(tmp_path):
    registry = _registry(tmp_path)
    registry.save(_payload(), _user())

    copy = registry.duplicate("r1", _user())

    assert copy["id"] != "r1"
    assert copy["name"] == "Copy of Sales"
    assert copy["copied_from"] == "r1"
    assert copy["version"] == 1
    assert copy["owner_id"] == "u1"


def test_admin_can_access_and_delete_other_users_report(tmp_path):
    registry = _registry(tmp_path)
    registry.save(_payload(), _user("u1", "alice"))

    admin = _user("admin", "administrator", "admin")
    assert registry.get("r1", admin)["owner_id"] == "u1"
    assert registry.delete("r1", admin) is True
    assert registry.get("r1", admin) is None

def test_saved_reports_are_not_artificially_capped_at_100(tmp_path):
    registry = _registry(tmp_path)

    for index in range(101):
        registry.save(_payload(f"r{index}"), _user())

    reports = registry.list(_user())
    assert len(reports) == 101
    assert {item["id"] for item in reports} == {f"r{index}" for index in range(101)}

