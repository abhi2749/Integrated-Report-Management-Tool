def test_full_export_reexecutes_with_unbounded_limit(monkeypatch):
    import main

    captured = {}

    class FakeManager:
        def get_query_payload(self, job_id):
            assert job_id == "job-test"
            return {"datasets": [], "limit": 5000}

    monkeypatch.setattr(main, "EXECUTION_MANAGER", FakeManager())
    monkeypatch.setattr(
        main,
        "_prepare_report_query",
        lambda payload: type(
            "Canonical",
            (),
            {
                "datasets": [],
                "normalized": lambda self: payload,
            },
        )(),
    )

    def fake_execute(payload):
        captured["payload"] = payload
        return {
            "success": True,
            "columns": [],
            "rows": [],
            "total_rows": 0,
        }

    monkeypatch.setattr(main, "_execute_report_payload", fake_execute)

    result = main._execute_full_export(
        "job-test",
        {"id": "u1", "role": "admin"},
    )

    assert result["success"] is True
    assert captured["payload"]["limit"] == 0
