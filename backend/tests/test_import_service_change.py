from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from import_service import _infer_type, _parse_csv, _safe_filename, import_file, preview_import


class TestImportServiceA13C(unittest.TestCase):
    def test_safe_filename(self):
        self.assertEqual(_safe_filename("../meter data?.csv"), "meter data_.csv")

    def test_type_inference(self):
        self.assertEqual(_infer_type([1, 2, 3]), "integer")
        self.assertEqual(_infer_type([1.2, 3]), "number")
        self.assertEqual(_infer_type(["a", "b"]), "string")

    def test_csv_parser_handles_duplicate_headers(self):
        from config import DATA_DIR
        with tempfile.TemporaryDirectory(dir=DATA_DIR) as directory:
            path = Path(directory) / "data.csv"
            path.write_text("A,A\n1,2\n3,4\n", encoding="utf-8")
            columns, rows = _parse_csv(path)
            self.assertEqual(columns, ["A", "A_2"])
            self.assertEqual(rows[0], {"A": "1", "A_2": "2"})

    def test_import_and_preview_roundtrip(self):
        from config import DATA_DIR
        with tempfile.TemporaryDirectory(dir=DATA_DIR) as directory:
            from import_service import IMPORT_ROOT, IMPORTED_DATA_REGISTRY
            original_root = IMPORT_ROOT
            # import_file uses the module constant; this test only checks the
            # returned contract with a temporary repository by monkey-patching
            # the root and registry.
            import import_service
            import_service.IMPORT_ROOT = Path(directory) / "imports"
            from metadata_repository import JsonMetadataRepository
            import_service.IMPORTED_DATA_REGISTRY = import_service.ImportedDataRegistry(
                JsonMetadataRepository(Path(directory) / "metadata.json")
            )
            try:
                item = import_file(BytesIO(b"name,value\nA,10\nB,20\n"), "sample.csv", None, {"id": "u1", "username": "tester"})
                self.assertEqual(item["row_count"], 2)
                result = preview_import(item)
                self.assertEqual(result["rows"][0]["name"], "A")
            finally:
                import_service.IMPORT_ROOT = original_root


if __name__ == "__main__":
    unittest.main()
