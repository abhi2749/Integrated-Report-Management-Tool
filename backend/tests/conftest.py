"""
Reporting Tool - regression test configuration.

These tests are intentionally lightweight. They validate contracts and
security primitives without requiring a running database or changing the
application's runtime configuration.
"""

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
