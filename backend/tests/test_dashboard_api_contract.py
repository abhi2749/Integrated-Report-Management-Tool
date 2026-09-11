from pathlib import Path
import re


def test_dashboard_frontend_contains_sharing_and_export_controls():
    source = Path(__file__).resolve().parents[2] / "frontend-ui" / "src" / "Dashboard.jsx"
    text = source.read_text(encoding="utf-8")

    # The dashboard has one Share entry point. Sharing management is intentionally
    # inside that panel; there is no separate "Shares" toolbar button.
    assert "Share" in text
    assert "Grant Access" in text
    assert "/shares" in text
    assert "/export/" in text
    assert "Export JSON" in text
    assert "Export CSV" in text
    assert "Export Excel" in text
    assert "Export PDF" in text
    assert "Download Package" in text

    # Do not reject the API route (/shares) or explanatory text containing the
    # word "shares". Only reject a standalone toolbar/button label "Shares".
    standalone_shares_button = re.search(
        r"<button[^>]*>\s*Shares\s*</button>", text, flags=re.IGNORECASE
    )
    assert standalone_shares_button is None
