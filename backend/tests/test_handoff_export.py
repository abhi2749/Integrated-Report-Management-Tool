import main


def test_build_report_pdf_contains_pdf_signature():
    payload = main._build_report_pdf(
        {
            "columns": ["id", "zone"],
            "rows": [{"id": 1, "zone": "WEST"}],
        },
        "Synthetic Report",
    )
    assert payload.startswith(b"%PDF")
    assert len(payload) > 100


def test_full_export_preserves_unbounded_limit(monkeypatch):
    captured = {}

    class FakeManager:
        def get_query_payload(self, job_id):
            return {
                "datasets": [],
                "columns": [],
                "joins": [],
                "filters": [],
                "sorts": [],
                "group_by": [],
                "aggregations": [],
                "calculated_columns": [],
                "limit": 5000,
            }

    class Canonical:
        datasets = []

        @staticmethod
        def normalized():
            return captured["payload"]

    def fake_prepare(payload):
        captured["payload"] = payload
        return Canonical()

    monkeypatch.setattr(main, "EXECUTION_MANAGER", FakeManager())
    monkeypatch.setattr(main, "_prepare_report_query", fake_prepare)
    monkeypatch.setattr(
        main,
        "_execute_report_payload",
        lambda payload: {"success": True, "columns": [], "rows": [], "total_rows": 0},
    )

    result = main._execute_full_export("job-test", {"id": "u1", "role": "admin"})
    assert result["success"] is True
    assert captured["payload"]["limit"] == 0
