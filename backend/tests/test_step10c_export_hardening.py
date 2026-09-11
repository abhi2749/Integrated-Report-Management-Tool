from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from report_export_service import write_pdf


def test_pdf_export_consumes_large_input_in_bounded_chunks(tmp_path):
    rows = ({"value": index} for index in range(2505))
    output = tmp_path / "report.pdf"
    processed = write_pdf(output, "Large Report", ["value"], rows, lambda: False)
    assert processed == 2505
    assert output.exists()
    assert output.stat().st_size > 0


def test_pdf_export_honors_cancellation_before_materializing_next_chunk(tmp_path):
    calls = {"count": 0}

    def cancelled():
        calls["count"] += 1
        return calls["count"] > 2

    rows = ({"value": index} for index in range(5000))
    output = tmp_path / "cancelled.pdf"
    try:
        write_pdf(output, "Cancelled", ["value"], rows, cancelled)
    except InterruptedError as exc:
        assert str(exc) == "Export cancelled."
    else:
        raise AssertionError("Expected PDF export cancellation")
