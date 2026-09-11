import tempfile
import unittest
from pathlib import Path

import import_service


class TestImportStreaming(unittest.TestCase):
    def test_csv_iterator_does_not_materialize_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.csv"
            path.write_text("id,value\n1,a\n2,b\n3,c\n", encoding="utf-8")
            columns, rows = import_service._iter_csv(path)
            self.assertEqual(columns, ["id", "value"])
            try:
                self.assertEqual(next(rows), {"id": "1", "value": "a"})
                self.assertEqual(next(rows), {"id": "2", "value": "b"})
            finally:
                rows.close()

    def test_xlsx_iterator_streams_rows(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["id", "value"])
            sheet.append([1, "a"])
            sheet.append([2, "b"])
            workbook.save(path)
            workbook.close()
            columns, rows = import_service._iter_xlsx(path)
            self.assertEqual(columns, ["id", "value"])
            try:
                self.assertEqual(next(rows), {"id": 1, "value": "a"})
                self.assertEqual(next(rows), {"id": 2, "value": "b"})
            finally:
                rows.close()

    def test_json_array_iterator_preserves_all_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            path.write_text('[{"id":1,"value":"a"},{"id":2,"value":"b"}]', encoding="utf-8")
            columns, rows = import_service._iter_json(path)
            self.assertEqual(columns, ["id", "value"])
            self.assertEqual(list(rows), [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}])

    def test_import_file_writes_streamed_rows_and_counts_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_root = import_service.IMPORT_ROOT
            old_data_dir = import_service.DATA_DIR
            old_registry = import_service.IMPORTED_DATA_REGISTRY
            import_service.DATA_DIR = root / "data"
            import_service.DATA_DIR.mkdir(parents=True)
            import_service.IMPORT_ROOT = import_service.DATA_DIR / "imports"
            from metadata_repository import JsonMetadataRepository
            import_service.IMPORTED_DATA_REGISTRY = import_service.ImportedDataRegistry(
                JsonMetadataRepository(root / "metadata.json")
            )
            try:
                from io import BytesIO
                item = import_service.import_file(
                    BytesIO(b"id,value\n1,a\n2,b\n3,c\n"),
                    "sample.csv",
                    None,
                    {"id": "u1", "username": "tester"},
                )
                self.assertEqual(item["row_count"], 3)
                stored = (import_service.DATA_DIR / item["storage_path"]).resolve()
                self.assertEqual(len(stored.read_text(encoding="utf-8").splitlines()), 3)
            finally:
                import_service.IMPORT_ROOT = old_root
                import_service.DATA_DIR = old_data_dir
                import_service.IMPORTED_DATA_REGISTRY = old_registry


if __name__ == "__main__":
    unittest.main()
