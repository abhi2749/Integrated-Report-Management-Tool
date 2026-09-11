from pathlib import Path
import ast

MAIN = Path(__file__).parents[1] / "main.py"


def _tree():
    return ast.parse(MAIN.read_text(encoding="utf-8"))


def _functions(tree, name):
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]


def test_report_query_normalizes_through_canonical_contract():
    source = MAIN.read_text(encoding="utf-8")
    assert "canonical_query_from_payload(request.model_dump())" in source


def test_execution_job_uses_canonical_contract():
    source = MAIN.read_text(encoding="utf-8")
    fn = _functions(_tree(), "_run_report_job_payload")[0]
    body = ast.get_source_segment(source, fn)
    assert "canonical_query_from_payload(payload)" in body


def test_query_plan_endpoint_uses_same_canonical_contract():
    source = MAIN.read_text(encoding="utf-8")
    assert '@app.post("/report/query/plan"' in source
    fn = _functions(_tree(), "report_query_plan")[0]
    body = ast.get_source_segment(source, fn)
    assert "canonical_query_from_payload(payload)" in body


def test_execution_transform_endpoint_reuses_stored_query_definition():
    source = Path(__file__).resolve().parents[1].joinpath("main.py").read_text(encoding="utf-8")
    assert '@app.post("/execution/jobs/{job_id}/transform"' in source
    assert 'EXECUTION_MANAGER.get_query_payload(job_id)' in source
    assert 'transformed.update(updates)' in source
    assert 'query_payload=canonical_payload' in source


def test_legacy_report_query_uses_execution_manager():
    source = MAIN.read_text(encoding="utf-8")
    start = source.index('@app.post("/report/query"')
    end = source.index('@app.post("/report/query/plan"', start)
    body = source[start:end]
    assert 'EXECUTION_MANAGER.submit(' in body
    assert 'EXECUTION_MANAGER.result_page(' in body
    assert 'execute_report_query(' not in body
