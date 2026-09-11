import json
from pathlib import Path

from dashboard_registry import DashboardRegistry


def _users():
    return (
        {"id": "owner-1", "username": "owner", "role": "report_user"},
        {"id": "viewer-1", "username": "viewer", "role": "report_user"},
        {"id": "admin-1", "username": "admin", "role": "admin"},
    )


def test_dashboard_share_grants_view_access(tmp_path: Path):
    registry = DashboardRegistry(tmp_path / "metadata.db")
    owner, viewer, _ = _users()
    registry.save("dash-1", "Sales", {"widgets": []}, owner)
    registry.add_share("dash-1", viewer["id"], viewer["username"], owner)
    item = registry.get("dash-1", viewer)
    assert item["id"] == "dash-1"
    assert registry.list_shares("dash-1", owner)[0]["shared_with_username"] == "viewer"


def test_non_owner_cannot_manage_shares_or_modify_dashboard(tmp_path: Path):
    registry = DashboardRegistry(tmp_path / "metadata.db")
    owner, viewer, _ = _users()
    registry.save("dash-1", "Sales", {"widgets": []}, owner)
    try:
        registry.save("dash-1", "Changed", {"widgets": []}, viewer)
        assert False, "expected permission error"
    except PermissionError:
        pass
    try:
        registry.add_share("dash-1", "another", "another", viewer)
        assert False, "expected permission error"
    except PermissionError:
        pass


def test_admin_can_view_and_manage_shared_dashboard(tmp_path: Path):
    registry = DashboardRegistry(tmp_path / "metadata.db")
    owner, viewer, admin = _users()
    registry.save("dash-1", "Sales", {"widgets": [1]}, owner)
    registry.add_share("dash-1", viewer["id"], viewer["username"], owner)
    assert registry.get("dash-1", admin)["definition"]["widgets"] == [1]
    registry.add_share("dash-1", "viewer-2", "viewer2", admin)
    assert len(registry.list_shares("dash-1", admin)) == 2
    assert registry.remove_share("dash-1", viewer["id"], admin) is True


def test_remove_share_revokes_view_access(tmp_path: Path):
    registry = DashboardRegistry(tmp_path / "metadata.db")
    owner, viewer, _ = _users()
    registry.save("dash-1", "Sales", {"widgets": []}, owner)
    registry.add_share("dash-1", viewer["id"], viewer["username"], owner)
    assert registry.remove_share("dash-1", viewer["id"], owner) is True
    assert registry.get("dash-1", viewer) is None


def test_dashboard_definition_contains_execution_job_for_data_delivery(tmp_path: Path):
    registry = DashboardRegistry(tmp_path / "metadata.db")
    owner, _, _ = _users()
    definition = {"widgets": [], "filters": [], "execution_job_id": "job-123"}
    item = registry.save("dash-1", "Sales", definition, owner)
    assert json.loads(item["definition"].__class__.__name__ and json.dumps(item["definition"]))["execution_job_id"] == "job-123"
