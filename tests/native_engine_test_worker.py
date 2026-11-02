"""Test-only bootstrap for faults/spies inside the native engine branch.

There is no environment switch or test hook in the production dispatcher.
Boundary behavior is separately tested through the actual production worker.
"""

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root)]

from fatebridge.core.astro import native_execution  # noqa: E402

native_execution._WORKER_ACTIVE = True

import pytest  # noqa: E402

raise SystemExit(pytest.main([sys.argv[1], "-q", "--override-ini=addopts="]))
