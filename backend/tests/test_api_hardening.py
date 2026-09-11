from __future__ import annotations

import ast
from pathlib import Path


MAIN_FILE = Path(__file__).resolve().parents[1] / "main.py"


def _main_source() -> str:
    return MAIN_FILE.read_text(encoding="utf-8")


def _tree() -> ast.Module:
    return ast.parse(_main_source(), filename=str(MAIN_FILE))


def _routes():
    routes = []
    for node in _tree().body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute):
                continue
            if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id != "app":
                continue
            if decorator.func.attr not in {"get", "post", "put", "delete", "patch"}:
                continue
            if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                continue
            dependencies = []
            for keyword in decorator.keywords:
                if keyword.arg == "dependencies" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                    dependencies = [ast.unparse(item) for item in keyword.value.elts]
            routes.append((decorator.func.attr.upper(), decorator.args[0].value, node.name, dependencies, node))
    return routes


def _route(path: str, method: str = "GET"):
    matches = [item for item in _routes() if item[0] == method and item[1] == path]
    assert len(matches) == 1, f"Expected exactly one {method} {path} route, found {len(matches)}"
    return matches[0]


def test_sensitive_execution_routes_are_auth_protected():
    for method, path in [
        ("POST", "/execution/jobs"),
        ("GET", "/execution/jobs"),
        ("GET", "/execution/jobs/{job_id}"),
        ("GET", "/execution/jobs/{job_id}/result"),
        ("GET", "/execution/jobs/{job_id}/export/csv"),
        ("GET", "/execution/jobs/{job_id}/export/json"),
        ("GET", "/execution/jobs/{job_id}/dashboard"),
        ("POST", "/execution/jobs/{job_id}/cancel"),
    ]:
        dependencies = _route(path, method)[3]
        assert any("require_app_access" in item for item in dependencies)


def test_export_routes_have_unique_contracts():
    csv_route = _route("/execution/jobs/{job_id}/export/csv")
    json_route = _route("/execution/jobs/{job_id}/export/json")
    assert csv_route[0] == "GET" and json_route[0] == "GET"
    assert csv_route[2] == "export_report_job_csv"
    assert json_route[2] == "export_report_job_json"
    assert csv_route[2] != json_route[2]


def test_result_endpoint_has_bounded_page_size():
    route = _route("/execution/jobs/{job_id}/result")
    source = ast.get_source_segment(_main_source(), route[4]) or ""
    assert "limit > 10000" not in source
    assert "limit < 1" in source
    assert "result_page" in source


def test_result_endpoint_rejects_negative_offsets():
    route = _route("/execution/jobs/{job_id}/result")
    source = ast.get_source_segment(_main_source(), route[4]) or ""
    assert "offset < 0" in source
    assert "offset must be non-negative" in source


def test_dashboard_endpoint_has_no_artificial_browser_row_bound():
    route = _route("/execution/jobs/{job_id}/dashboard")
    source = ast.get_source_segment(_main_source(), route[4]) or ""
    assert "limit > 500" not in source
    assert "limit must be between 1 and 500" not in source
    assert "build_visualization_from_row_stream" in source


def test_export_endpoints_require_completed_jobs():
    for path in [
        "/execution/jobs/{job_id}/export/csv",
        "/execution/jobs/{job_id}/export/json",
    ]:
        route = _route(path)
        source = ast.get_source_segment(_main_source(), route[4]) or ""
        assert 'status") != "completed"' in source
        assert "Report job is not completed" in source


def test_export_endpoints_use_safe_filenames_and_streaming():
    for path, expected_function in [
        ("/execution/jobs/{job_id}/export/csv", "csv_stream"),
        ("/execution/jobs/{job_id}/export/json", "json_stream"),
    ]:
        route = _route(path)
        source = ast.get_source_segment(_main_source(), route[4]) or ""
        assert "safe_export_filename" in source
        assert expected_function in source
        assert "StreamingResponse" in source


def test_dashboard_uses_visualization_boundary():
    route = _route("/execution/jobs/{job_id}/dashboard")
    source = ast.get_source_segment(_main_source(), route[4]) or ""
    assert "build_visualization_response" in source
    assert "visualization=visualization" in source
    assert "category_field=category_field" in source
    assert "value_field=value_field" in source


def test_export_job_routes_exist_and_are_protected():
    for method, path in [
        ("POST", "/execution/jobs/{job_id}/export"),
        ("GET", "/execution/exports/{export_id}"),
        ("GET", "/execution/exports/{export_id}/download"),
        ("POST", "/execution/exports/{export_id}/cancel"),
    ]:
        dependencies = _route(path, method)[3]
        assert any("require_app_access" in item for item in dependencies)


def test_export_job_routes_use_background_manager():
    create_route = _route("/execution/jobs/{job_id}/export", "POST")
    source = ast.get_source_segment(_main_source(), create_route[4]) or ""
    assert "EXPORT_MANAGER.submit" in source
    assert "iter_result_rows" in source

    download_route = _route("/execution/exports/{export_id}/download")
    source = ast.get_source_segment(_main_source(), download_route[4]) or ""
    assert "path_for_completed" in source
    assert "FileResponse" in source
