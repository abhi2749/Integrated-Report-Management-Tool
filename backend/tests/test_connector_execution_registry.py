from connectors.execution_registry import ConnectorExecutionRegistry


def test_registry_normalizes_and_dispatches_registered_handler():
    registry = ConnectorExecutionRegistry()
    seen = {}

    def handler(dataset, **kwargs):
        seen["dataset"] = dataset
        seen["kwargs"] = kwargs
        return [{"id": 1}]

    registry.register("MySQL", handler)
    result = registry.execute(
        {"source_type": "MYSQL", "id": "ds1"},
        required_columns=["id"],
    )

    assert result == [{"id": 1}]
    assert seen["dataset"]["id"] == "ds1"
    assert seen["kwargs"]["required_columns"] == ["id"]


def test_registry_rejects_unknown_connector():
    registry = ConnectorExecutionRegistry()
    try:
        registry.register("postgresql", lambda dataset, **kwargs: [])
    except ValueError as exc:
        assert "Unsupported source_type" in str(exc)
    else:
        raise AssertionError("Unknown connector should be rejected")


def test_registry_requires_registered_handler():
    registry = ConnectorExecutionRegistry()
    try:
        registry.execute({"source_type": "mysql"})
    except RuntimeError as exc:
        assert "No execution handler" in str(exc)
    else:
        raise AssertionError("Missing handler should be rejected")


def test_registry_rejects_non_list_handler_result():
    registry = ConnectorExecutionRegistry()
    registry.register("mongodb", lambda dataset, **kwargs: {"rows": []})

    try:
        registry.execute({"source_type": "mongodb"})
    except TypeError as exc:
        assert "must return a list" in str(exc)
    else:
        raise AssertionError("Non-list handler result should be rejected")


def test_registry_reports_registered_execution_types():
    registry = ConnectorExecutionRegistry()
    registry.register("mongodb", lambda dataset, **kwargs: [])
    registry.register("mysql", lambda dataset, **kwargs: [])

    assert registry.supported_source_types() == ["mongodb", "mysql"]
    assert registry.has_handler("MYSQL") is True
