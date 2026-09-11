from types import SimpleNamespace

from execution_contract import PreparedExecution
from execution_engine import execute_prepared_execution


def _prepared(strategy="SINGLE_SOURCE", joins=0):
    query = SimpleNamespace(
        datasets=[SimpleNamespace(model_dump=lambda exclude_none=True: {"id": "d1", "source_type": "mysql", "host": "h", "port": 3306, "database": "db", "table": "t"})],
        joins=[],
        columns=[],
        filters=[],
        sorts=[],
        group_by=[],
        aggregations=[],
        calculations=[],
        limit=0,
    )
    plan = SimpleNamespace(execution_strategy=strategy, join_count=joins)
    return PreparedExecution(query=query, plan=plan, payload={}, fingerprint="x")


def test_engine_uses_stream_for_simple_single_source(monkeypatch):
    captured = {}

    def fake_execute_report_query(**kwargs):
        captured.update(kwargs)
        return {"success": True}

    monkeypatch.setattr("database.execute_report_query", fake_execute_report_query)
    result = execute_prepared_execution(_prepared())
    assert result["success"] is True
    assert captured["stream"] is True
    assert captured["execution_plan"].execution_strategy == "SINGLE_SOURCE"


def test_engine_keeps_streaming_for_join(monkeypatch):
    captured = {}

    def fake_execute_report_query(**kwargs):
        captured.update(kwargs)
        return {"success": True}

    monkeypatch.setattr("database.execute_report_query", fake_execute_report_query)
    result = execute_prepared_execution(_prepared(strategy="SOURCE_JOIN", joins=1))
    assert result["success"] is True
    assert captured["stream"] is True
    assert captured["cancel_event"] is None
