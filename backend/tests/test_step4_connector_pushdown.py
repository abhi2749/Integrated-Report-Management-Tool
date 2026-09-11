from pathlib import Path
from connectors.mysql import MySQLConnector
from connectors.clickhouse import ClickHouseConnector
from mysql_pushdown import build_group_aggregation

def test_mysql_group_aggregation_builder():
    projection, groups, aliases = build_group_aggregation("ds", ["zone"], [{"function":"COUNT","field":"*","alias":"rows"}])
    assert "`zone` AS `ds.zone`" in projection and "COUNT(*) AS `rows`" in projection
    assert groups == ["zone"] and aliases == ["ds.zone", "rows"]

def test_mysql_stream_pushes_group_and_sort(monkeypatch):
    captured={}
    class Cursor:
        def execute(self,q,params=None): captured["query"]=q
        def fetchmany(self,size):
            if captured.get("done"):
                return []
            captured["done"] = True
            return [{"ds.zone":"WEST","rows":2}]
        def close(self): pass
    cur=Cursor()
    class Conn:
        def cursor(self,**kwargs): return cur
        def is_connected(self): return True
        def close(self): pass
    monkeypatch.setattr(MySQLConnector,"_connect",lambda self,db: Conn())
    rows=list(MySQLConnector("h",3306).execute_dataset_stream({"id":"ds","database":"db","table":"t"},pushdown_group_by=["ds.zone"],pushdown_aggregations=[{"function":"COUNT","field":"*","alias":"rows"}],pushdown_sorts=[{"field":"ds.zone","direction":"ASC"}]))
    assert rows == [{"ds.zone":"WEST","rows":2}]
    assert "GROUP BY `zone`" in captured["query"] and "ORDER BY `zone` ASC" in captured["query"]

def test_clickhouse_stream_pushes_group_and_qualified_sort(monkeypatch):
    captured={}
    class Stream:
        source=type("S",(),{"column_names":["ds.zone","rows"]})()
        def __enter__(self): return self
        def __iter__(self): return iter([[('WEST',2)]])
        def __exit__(self,*a): return False
    class Client:
        def query_row_block_stream(self,q,parameters=None): captured["query"]=q; return Stream()
        def close(self): pass
    monkeypatch.setattr(ClickHouseConnector,"_client",lambda self,database=None: Client())
    list(ClickHouseConnector("h",8123).execute_dataset_stream({"id":"ds","database":"db","table":"t"},pushdown_group_by=["ds.zone"],pushdown_aggregations=[{"function":"COUNT","field":"*","alias":"rows"}],pushdown_sorts=[{"field":"ds.zone","direction":"DESC"}]))
    assert "GROUP BY `zone`" in captured["query"] and "ORDER BY `zone` DESC" in captured["query"]
    assert "ORDER BY `zone` DESC" in captured["query"]

def test_mongodb_schema_discovery_uses_independent_sample_cap():
    text=(Path(__file__).parents[1]/"connectors"/"mongodb.py").read_text()
    assert "SCHEMA_SAMPLE_ROWS = 1000" in text and "limit(SCHEMA_SAMPLE_ROWS)" in text

def test_mysql_native_join_builder(monkeypatch):
    captured={}
    class Cursor:
        def execute(self,q,params=None): captured["query"]=q
        def fetchmany(self,size): return []
        def close(self): pass
    class Conn:
        def cursor(self,**kwargs): return Cursor()
        def is_connected(self): return True
        def close(self): pass
    monkeypatch.setattr(MySQLConnector,"_connect",lambda self,db: Conn())
    l={"id":"l","database":"db","table":"a"}; r={"id":"r","database":"db","table":"b"}
    list(MySQLConnector("h",3306).execute_join_stream(l,r,{"left_dataset":"l","right_dataset":"r","left_column":"id","right_column":"id"}))
    assert "INNER JOIN" in captured["query"]
