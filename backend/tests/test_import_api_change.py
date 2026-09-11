import ast
from pathlib import Path
import unittest

MAIN = Path(__file__).resolve().parents[1] / "main.py"


class TestImportApiA13C(unittest.TestCase):
    def test_import_routes_exist_and_are_protected(self):
        tree = ast.parse(MAIN.read_text(encoding="utf-8"))
        paths = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    text = ast.unparse(decorator)
                    if "/data/import" in text:
                        paths.add(text)
        joined = "\n".join(paths)
        self.assertIn("/data/import", joined)
        self.assertIn("require_app_access", joined)

    def test_import_permissions_are_explicit(self):
        source = MAIN.read_text(encoding="utf-8")
        self.assertIn('has_permission(user, "datasets.create")', source)
        self.assertIn('has_permission(user, "datasets.view")', source)


if __name__ == "__main__":
    unittest.main()
