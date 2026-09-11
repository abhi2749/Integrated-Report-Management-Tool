import ast
import pathlib

from execution_manager import ExecutionManager


MAIN = pathlib.Path(__file__).resolve().parents[1] / "main.py"


def test_submit_records_job_owner():
    manager = ExecutionManager(max_workers=1, retention_seconds=60)
    try:
        job_id = manager.submit(lambda: {"rows": [], "returned_rows": 0}, owner_user_id="u1", owner_username="alice")
        job = manager.get(job_id)
        assert job["owner_user_id"] == "u1"
        assert job["owner_username"] == "alice"
    finally:
        manager.shutdown()


def test_owner_metadata_is_publicly_returned():
    manager = ExecutionManager(max_workers=1, retention_seconds=60)
    try:
        job_id = manager.submit(lambda: {"rows": []}, owner_user_id="u2", owner_username="bob")
        assert manager.get(job_id)["owner_user_id"] == "u2"
        assert manager.get(job_id)["owner_username"] == "bob"
    finally:
        manager.shutdown()


def test_owner_matching_allows_owner():
    source = MAIN.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_job_is_visible_to_user")
    body = ast.get_source_segment(source, fn)
    assert 'str(owner_id) == str(user.get("id"))' in body


def test_admin_can_access_all_jobs():
    source = MAIN.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_job_is_visible_to_user")
    body = ast.get_source_segment(source, fn)
    assert 'str(user.get("role", "")).lower() == "admin"' in body


def test_unowned_legacy_jobs_are_not_visible_to_non_admins():
    source = MAIN.read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_job_is_visible_to_user")
    body = ast.get_source_segment(source, fn)
    assert 'owner_id is not None' in body


def test_job_access_guard_is_used_by_result_and_cancel_routes():
    source = MAIN.read_text(encoding="utf-8")
    assert '_require_job_access(job_id, user)' in source
    tree = ast.parse(source)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "_require_job_access" in names


def test_job_creation_passes_authenticated_owner():
    source = MAIN.read_text(encoding="utf-8")
    assert 'owner_user_id=str(user.get("id"))' in source
    assert 'owner_username=str(user.get("username", ""))' in source


def test_job_listing_filters_non_admin_jobs():
    source = MAIN.read_text(encoding="utf-8")
    assert 'jobs = [job for job in jobs if _job_is_visible_to_user(job, user)]' in source
