import importlib
import sys
import types
from pathlib import Path


def _module():
    if "mysql.connector" not in sys.modules:
        connector_module = types.ModuleType("mysql.connector")
        connector_module.connect = lambda **kwargs: None
        connector_module.Error = Exception
        mysql_module = types.ModuleType("mysql")
        mysql_module.connector = connector_module
        sys.modules["mysql"] = mysql_module
        sys.modules["mysql.connector"] = connector_module

    package = types.ModuleType("connectors")
    package.__path__ = [str(Path(__file__).parents[1] / "connectors")]
    sys.modules.setdefault("connectors", package)

    base_path = Path(__file__).parents[1] / "connectors" / "base.py"
    base_spec = importlib.util.spec_from_file_location("connectors.base", base_path)
    base_module = importlib.util.module_from_spec(base_spec)
    sys.modules["connectors.base"] = base_module
    base_spec.loader.exec_module(base_module)

    module_path = Path(__file__).parents[1] / "connectors" / "mysql.py"
    spec = importlib.util.spec_from_file_location("connectors.mysql", module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["connectors.mysql"] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeCursor:
    def __init__(self):
        self.executed = None
        self.closed = False
        self.batches = [
            [{"ds1.id": 1, "ds1.name": "A"}],
            [{"ds1.id": 2, "ds1.name": "B"}],
            [],
        ]

    def execute(self, query, params):
        self.executed = (query, params)

    def fetchmany(self, size):
        return self.batches.pop(0)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.closed = False

    def cursor(self, **kwargs):
        assert kwargs == {"dictionary": True, "buffered": False}
        return self.cursor_obj

    def is_connected(self):
        return not self.closed

    def close(self):
        self.closed = True


def test_mysql_connector_executes_dataset_with_pushdown(monkeypatch):
    mod = _module()
    connection = FakeConnection()
    monkeypatch.setattr(mod.mysql.connector, "connect", lambda **kwargs: connection)

    dataset = {
        "id": "ds1",
        "host": "localhost",
        "port": 3306,
        "username": "u",
        "password": "p",
        "database": "sales",
        "table": "orders",
    }
    rows = mod.execute_dataset(
        dataset,
        required_columns=["ds1.id", "ds1.name"],
        pushdown_filters=[{"field": "status", "operator": "=", "value": "OPEN"}],
    )

    assert rows == [
        {"ds1.id": 1, "ds1.name": "A"},
        {"ds1.id": 2, "ds1.name": "B"},
    ]
    query, params = connection.cursor_obj.executed
    assert "SELECT" in query
    assert "`ds1.id`" in query
    assert "`ds1.name`" in query
    assert "`status` = %s" in query
    assert params == ["OPEN"]
    assert connection.closed is True
    assert connection.cursor_obj.closed is True


def test_mysql_connector_rejects_missing_table():
    mod = _module()
    dataset = {"id": "ds1", "host": "localhost", "port": 3306, "database": "sales"}
    try:
        mod.execute_dataset(dataset)
    except ValueError as exc:
        assert "database and table" in str(exc)
    else:
        raise AssertionError("Missing table should be rejected")


def test_database_mysql_fetch_is_compatibility_adapter():
    source = Path(__file__).parents[1].joinpath("database.py").read_text(encoding="utf-8")
    start = source.index("def _fetch_mysql")
    end = source.index("def _fetch_mongodb", start)
    body = source[start:end]
    assert "execute_mysql_dataset(" in body
    assert "create_mysql_connection(" not in body


def test_database_registers_connector_owned_mysql_handler():
    source = Path(__file__).parents[1].joinpath("database.py").read_text(encoding="utf-8")
    assert 'register_execution_handler("mysql", execute_mysql_dataset)' in source


def test_mysql_connector_stream_pushes_sort_and_limit(monkeypatch):
    mod = _module()
    connection = FakeConnection()
    monkeypatch.setattr(mod.mysql.connector, "connect", lambda **kwargs: connection)

    rows = list(mod.MySQLConnector("localhost", 3306, "u", "p").execute_dataset_stream(
        {"id": "ds1", "database": "sales", "table": "orders"},
        required_columns=["ds1.id", "ds1.name"],
        pushdown_sorts=[{"field": "ds1.name", "direction": "DESC"}],
        pushdown_limit=25,
    ))

    query, params = connection.cursor_obj.executed
    assert "ORDER BY `name` DESC" in query
    assert query.endswith(" LIMIT 25")
    assert params == []
    assert len(rows) == 2


def test_mysql_connector_nonstream_pushes_sort_and_limit(monkeypatch):
    mod = _module()
    connection = FakeConnection()
    monkeypatch.setattr(mod.mysql.connector, "connect", lambda **kwargs: connection)

    mod.MySQLConnector("localhost", 3306, "u", "p").execute_dataset(
        {"id": "ds1", "database": "sales", "table": "orders"},
        required_columns=["ds1.id", "ds1.name"],
        pushdown_sorts=[{"field": "ds1.name", "direction": "DESC"}],
        pushdown_limit=25,
    )

    query, params = connection.cursor_obj.executed
    assert "ORDER BY `name` DESC" in query
    assert query.endswith(" LIMIT 25")
    assert params == []


def test_mysql_preview_uses_configured_preview_capacity(monkeypatch):
    mod = _module()
    source = Path(__file__).parents[1].joinpath("connectors", "mysql.py").read_text(encoding="utf-8")
    assert "max(1, int(sample_limit))" in source
    assert "min(int(sample_limit), 100)" not in source
