from pathlib import Path
import ast

MAIN = Path(__file__).resolve().parents[1] / "main.py"
SOURCE = MAIN.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def functions():
    return {node.name: node for node in ast.walk(TREE) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def route_paths():
    result = set()
    for node in ast.walk(TREE):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in {"get", "post", "put", "delete"}:
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        result.add(dec.args[0].value)
    return result


def test_lineage_service_is_imported():
    assert "from lineage_service import LINEAGE_REGISTRY, lineage_from_payload" in SOURCE


def test_lineage_routes_exist():
    paths = route_paths()
    assert "/lineage/reports/{report_id}" in paths
    assert "/lineage/jobs/{job_id}" in paths


def test_report_save_records_lineage():
    node = functions()["save_report"]
    text = ast.get_source_segment(SOURCE, node) or ""
    assert "LINEAGE_REGISTRY.save" in text
    assert "lineage_from_payload" in text


def test_job_creation_records_lineage_and_preserves_owner_acl():
    node = functions()["create_report_job"]
    text = ast.get_source_segment(SOURCE, node) or ""
    assert "owner_user_id" in text
    assert "owner_username" in text
    assert "LINEAGE_REGISTRY.save" in text


def test_lineage_job_route_reuses_job_acl():
    node = functions()["get_execution_job_lineage"]
    text = ast.get_source_segment(SOURCE, node) or ""
    assert "_require_job_access(job_id, user)" in text
