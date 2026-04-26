from pathlib import Path
import os
import sys

import pytest


ROOT = Path(__file__).resolve().parent
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)


def pytest_collection_modifyitems(items):
    """Skip snapshot assertion tests when running in CI."""
    if os.environ.get("CI", "").lower() not in ("1", "true"):
        return
    skip_marker = pytest.mark.skip(reason="Snapshot tests are skipped in CI")
    for item in items:
        if "snapshot" in item.fixturenames:
            item.add_marker(skip_marker)
