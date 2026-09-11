from pathlib import Path
import ast
import unittest

MAIN = Path(__file__).resolve().parents[1] / "main.py"


class TestDatasetManagementAPIA13D(unittest.TestCase):
    def test_catalog_and_imported_crud_routes_exist(self):
        source = MAIN.read_text(encoding="utf-8")
        for route in ["/datasets/catalog", "/data/imported/{dataset_id}"]:
            self.assertIn(route, source)
        self.assertIn("datasets.edit", source)
        self.assertIn("datasets.delete", source)

    def test_query_and_execution_validate_imported_dataset_access(self):
        tree = ast.parse(MAIN.read_text(encoding="utf-8"))
        source = MAIN.read_text(encoding="utf-8")
        self.assertIn("_require_dataset_access", source)
        self.assertGreaterEqual(source.count("_require_dataset_access(dataset"), 2)
        self.assertTrue(any(isinstance(node, ast.FunctionDef) and node.name == "_require_dataset_access" for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
