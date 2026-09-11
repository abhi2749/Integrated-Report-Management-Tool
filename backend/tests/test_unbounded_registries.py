import import_service
import lineage_service


class MemoryRepository:
    def __init__(self, records=None):
        self.records = list(records or [])

    def read(self):
        return list(self.records)

    def write(self, records):
        self.records = list(records)


def test_imported_data_registry_does_not_truncate_records():
    repo = MemoryRepository([{"id": f"dataset-{i}"} for i in range(1001)])
    registry = import_service.ImportedDataRegistry(repo)
    registry.save({"id": "dataset-new"})
    assert len(repo.records) == 1002
    assert repo.records[0]["id"] == "dataset-new"


def test_lineage_registry_does_not_truncate_records():
    repo = MemoryRepository([{"id": f"report:{i}"} for i in range(1001)])
    registry = lineage_service.LineageRegistry(repo)
    graph = {"target": {"type": "report", "id": "new"}, "nodes": [], "edges": []}
    registry.save(graph, {"id": "u1", "username": "tester"})
    assert len(repo.records) == 1002
    assert repo.records[0]["id"] == "report:new"
