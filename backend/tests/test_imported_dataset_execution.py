import json
import tempfile
import unittest
from pathlib import Path

import database
import import_service


class TestImportedDatasetExecutionA13D(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_data_dir = import_service.DATA_DIR
        self.old_registry = import_service.IMPORTED_DATA_REGISTRY
        import_service.DATA_DIR = self.root
        from metadata_repository import JsonMetadataRepository
        import_service.IMPORTED_DATA_REGISTRY = import_service.ImportedDataRegistry(
            JsonMetadataRepository(self.root / "metadata.json")
        )
        database.IMPORTED_DATA_REGISTRY = import_service.IMPORTED_DATA_REGISTRY
        dataset_dir = self.root / "imports" / "import_test"
        dataset_dir.mkdir(parents=True)
        (dataset_dir / "data.jsonl").write_text(
            json.dumps({"id": 1, "zone": "A", "value": 10}) + "\n"
            + json.dumps({"id": 2, "zone": "B", "value": 20}) + "\n",
            encoding="utf-8",
        )
        self.item = import_service.IMPORTED_DATA_REGISTRY.save({
            "id": "import_test",
            "name": "Imported Values",
            "source_type": "imported",
            "database": "local_imports",
            "object_name": "Imported Values",
            "object_type": "file",
            "storage_path": "imports/import_test/data.jsonl",
            "original_path": "imports/import_test/source.csv",
            "columns": [{"name": "id", "type": "integer"}, {"name": "zone", "type": "string"}, {"name": "value", "type": "integer"}],
            "owner_id": "u1",
            "owner_username": "tester",
            "status": "ready",
        })

    def tearDown(self):
        import_service.DATA_DIR = self.old_data_dir
        import_service.IMPORTED_DATA_REGISTRY = self.old_registry
        database.IMPORTED_DATA_REGISTRY = self.old_registry
        self.temp.cleanup()

    def test_imported_rows_are_qualified(self):
        rows = import_service.read_import_rows(self.item, ["id", "zone"])
        self.assertEqual(rows[0], {"import_test.id": 1, "import_test.zone": "A"})

    def test_imported_dataset_can_participate_in_existing_join_execution(self):
        other = dict(self.item)
        other["id"] = "import_other"
        other["name"] = "Other"
        other_dir = self.root / "imports" / "import_other"
        other_dir.mkdir(parents=True)
        (other_dir / "data.jsonl").write_text(json.dumps({"id": 1, "label": "one"}) + "\n", encoding="utf-8")
        other["storage_path"] = "imports/import_other/data.jsonl"
        other["original_path"] = "imports/import_other/source.csv"
        import_service.IMPORTED_DATA_REGISTRY.save(other)

        result = database._execute_report_query_unbounded(
            [self.item, other],
            [{"left_dataset": "import_test", "right_dataset": "import_other", "left_column": "id", "right_column": "id", "join_type": "INNER"}],
            [{"field": "import_test.zone", "alias": "zone"}, {"field": "import_other.label", "alias": "label"}],
            [], [], [], [], [], 100,
        )
        self.assertTrue(result["success"], result.get("message"))
        self.assertEqual(result["rows"][0]["zone"], "A")
        self.assertEqual(result["rows"][0]["label"], "one")


if __name__ == "__main__":
    unittest.main()
