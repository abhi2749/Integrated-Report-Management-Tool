import importlib
import sys
import types
from pathlib import Path


def _module():
    pymongo_module = types.ModuleType("pymongo")
    class FakeClientBase:
        pass
    pymongo_module.MongoClient = FakeClientBase
    errors_module = types.ModuleType("pymongo.errors")
    errors_module.PyMongoError = Exception
    sys.modules.setdefault("pymongo", pymongo_module)
    sys.modules.setdefault("pymongo.errors", errors_module)

    package = types.ModuleType("connectors")
    package.__path__ = [str(Path(__file__).parents[1] / "connectors")]
    sys.modules.setdefault("connectors", package)

    base_path = Path(__file__).parents[1] / "connectors" / "base.py"
    base_spec = importlib.util.spec_from_file_location("connectors.base", base_path)
    base_module = importlib.util.module_from_spec(base_spec)
    sys.modules["connectors.base"] = base_module
    base_spec.loader.exec_module(base_module)

    pushdown_path = Path(__file__).parents[1] / "mongodb_pushdown.py"
    push_spec = importlib.util.spec_from_file_location("mongodb_pushdown", pushdown_path)
    push_module = importlib.util.module_from_spec(push_spec)
    sys.modules["mongodb_pushdown"] = push_module
    push_spec.loader.exec_module(push_module)

    module_path = Path(__file__).parents[1] / "connectors" / "mongodb.py"
    spec = importlib.util.spec_from_file_location("connectors.mongodb", module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["connectors.mongodb"] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeCursor:
    def __iter__(self):
        return iter([
            {"_id": "a", "status": "OPEN"},
            {"_id": "b", "status": "CLOSED"},
        ])


class FakeCollection:
    def __init__(self):
        self.pipeline = None
        self.kwargs = None

    def aggregate(self, pipeline, **kwargs):
        self.pipeline = pipeline
        self.kwargs = kwargs
        return FakeCursor()


class FakeDatabase:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, name):
        assert name == "orders"
        return self.collection


class FakeClient:
    def __init__(self):
        self.collection = FakeCollection()
        self.database = FakeDatabase(self.collection)
        self.closed = False

    def __getitem__(self, name):
        assert name == "sales"
        return self.database

    def close(self):
        self.closed = True


def test_mongodb_connector_executes_dataset_with_pushdown(monkeypatch):
    mod = _module()
    client = FakeClient()
    monkeypatch.setattr(mod.MongoClient, "__new__", lambda cls, *a, **k: client)

    dataset = {
        "id": "ds1",
        "host": "localhost",
        "port": 27017,
        "username": "u",
        "password": "p",
        "database": "sales",
        "table": "orders",
    }
    rows = mod.MongoDBConnector(
        "localhost", 27017, "u", "p"
    ).execute_dataset(
        dataset,
        required_columns=["ds1._id", "ds1.status"],
        pushdown_filters=[{"field": "status", "operator": "=", "value": "OPEN"}],
    )

    assert rows == [
        {"ds1._id": "a", "ds1.status": "OPEN"},
        {"ds1._id": "b", "ds1.status": "CLOSED"},
    ]
    assert client.collection.kwargs["allowDiskUse"] is True
    assert client.collection.kwargs["batchSize"] == 5000
    assert client.closed is True


def test_mongodb_connector_rejects_missing_table():
    mod = _module()
    connector = mod.MongoDBConnector("localhost", 27017, "u", "p")
    dataset = {"id": "ds1", "host": "localhost", "port": 27017, "database": "sales"}
    try:
        connector.execute_dataset(dataset)
    except ValueError as exc:
        assert "database and table" in str(exc)
    else:
        raise AssertionError("Missing table should be rejected")


def test_database_mongodb_fetch_is_compatibility_adapter():
    source = Path(__file__).parents[1].joinpath("database.py").read_text(encoding="utf-8")
    start = source.index("def _fetch_mongodb")
    end = source.index("def _fetch_dataset", start)
    body = source[start:end]
    assert "connector.execute_dataset(" in body
    assert "create_mongo_connection(" not in body


def test_database_registers_connector_owned_mongodb_handler():
    source = Path(__file__).parents[1].joinpath("database.py").read_text(encoding="utf-8")
    assert "def _execute_mongodb_dataset(" in source
    assert 'register_execution_handler("mongodb", _execute_mongodb_dataset)' in source
