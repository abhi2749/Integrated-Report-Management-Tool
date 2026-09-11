import json
import tempfile
import unittest
from pathlib import Path

import import_service


class TestSavedImportedDatasetManagementA13D(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original_root = import_service.DATA_DIR
        self.original_registry = import_service.IMPORTED_DATA_REGISTRY
        import_service.DATA_DIR = self.root
        from metadata_repository import JsonMetadataRepository
        import_service.IMPORTED_DATA_REGISTRY = import_service.ImportedDataRegistry(
            JsonMetadataRepository(self.root / "metadata.json")
        )

    def tearDown(self):
        import_service.DATA_DIR = self.original_root
        import_service.IMPORTED_DATA_REGISTRY = self.original_registry
        self.temp.cleanup()

    def _item(self):
        dataset_dir = self.root / "imports" / "import_test"
        dataset_dir.mkdir(parents=True)
        (dataset_dir / "source.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        normalized = dataset_dir / "data.jsonl"
        normalized.write_text(json.dumps({"a": 1, "b": 2}) + "\n", encoding="utf-8")
        return import_service.IMPORTED_DATA_REGISTRY.save({
            "id": "import_test",
            "name": "Source",
            "source_type": "imported",
            "database": "local_imports",
            "object_name": "Source",
            "object_type": "file",
            "storage_path": "imports/import_test/data.jsonl",
            "original_path": "imports/import_test/source.csv",
            "columns": [{"name": "a", "type": "integer"}, {"name": "b", "type": "integer"}],
            "owner_id": "u1",
            "owner_username": "tester",
            "status": "ready",
        })

    def test_update_is_owner_scoped(self):
        item = self._item()
        updated = import_service.IMPORTED_DATA_REGISTRY.update(item["id"], {"name": "Renamed"}, {"id": "u1", "role": "user"})
        self.assertEqual(updated["name"], "Renamed")
        self.assertIsNone(import_service.IMPORTED_DATA_REGISTRY.update(item["id"], {"name": "Nope"}, {"id": "u2", "role": "user"}))

    def test_delete_removes_metadata_and_storage_for_owner(self):
        item = self._item()
        self.assertTrue(import_service.IMPORTED_DATA_REGISTRY.delete(item["id"], {"id": "u1", "role": "user"}))
        self.assertIsNone(import_service.IMPORTED_DATA_REGISTRY.get(item["id"], {"id": "u1", "role": "user"}))
        self.assertFalse((self.root / "imports" / "import_test").exists())


if __name__ == "__main__":
    unittest.main()
