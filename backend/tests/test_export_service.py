import csv
import io
import json

from export_service import csv_stream, json_stream, safe_export_filename


def sample_result():
    return {
        "success": True,
        "columns": ["meter_id", "reading", "meta"],
        "rows": [
            {"meter_id": "M-1", "reading": 12.5, "meta": {"phase": "R"}},
            {"meter_id": "M-2", "reading": None, "meta": [1, 2]},
        ],
        "total_rows": 2,
        "returned_rows": 2,
    }


def test_csv_stream_preserves_columns_rows_and_nested_values():
    content = "".join(csv_stream(sample_result()))
    rows = list(csv.reader(io.StringIO(content)))
    assert rows[0] == ["meter_id", "reading", "meta"]
    assert rows[1][0:2] == ["M-1", "12.5"]
    assert json.loads(rows[1][2]) == {"phase": "R"}
    assert json.loads(rows[2][2]) == [1, 2]


def test_json_stream_produces_valid_report_envelope():
    payload = json.loads("".join(json_stream(sample_result())))
    assert payload["success"] is True
    assert payload["columns"] == ["meter_id", "reading", "meta"]
    assert payload["total_rows"] == 2
    assert payload["returned_rows"] == 2
    assert payload["rows"][0]["meter_id"] == "M-1"


def test_streams_are_incremental_not_single_full_payload():
    assert len(list(csv_stream(sample_result()))) == 3  # header + two rows
    assert len(list(json_stream(sample_result()))) > 3


def test_safe_export_filename_removes_path_and_reserved_characters():
    assert safe_export_filename("../Monthly:Report?.csv", "csv") == "Monthly_Report_.csv"
    assert safe_export_filename("", "json") == "report.json"
