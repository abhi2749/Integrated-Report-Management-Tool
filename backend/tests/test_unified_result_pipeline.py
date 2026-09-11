from __future__ import annotations

from result_pipeline import UnifiedResultPipeline
from result_store import ExecutionResultStore


def test_pipeline_ingests_and_pages_without_full_result_materialization(tmp_path):
    store = ExecutionResultStore(tmp_path / "results.sqlite3")
    pipeline = UnifiedResultPipeline(store)

    rows = ({"id": index, "value": f"v{index}"} for index in range(2501))
    stored = pipeline.ingest("job-1", rows, columns=["id", "value"])

    assert stored["total_rows"] == 2501
    page = pipeline.page("job-1", offset=1000, limit=500)
    assert page is not None
    assert len(page["rows"]) == 500
    assert page["rows"][0]["id"] == 1000
    assert page["rows"][-1]["id"] == 1499
    assert page["has_more"] is True


def test_pipeline_iterator_is_lazy(tmp_path):
    store = ExecutionResultStore(tmp_path / "results.sqlite3")
    pipeline = UnifiedResultPipeline(store)
    pipeline.ingest("job-2", ({"id": i} for i in range(3000)), columns=["id"])

    iterator = pipeline.iter_rows("job-2")
    assert next(iterator)["id"] == 0
    assert next(iterator)["id"] == 1
    assert next(iterator)["id"] == 2
