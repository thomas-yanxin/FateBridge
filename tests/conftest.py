"""Explicit native-engine fault tests run inside their own fresh exec process.

Production isolation deliberately excludes parent monkeypatches. Marked tests
exercise internal source guards/spies with the injection installed *inside* a
fresh native context. Their bodies and assertions are unchanged. Unmarked
reference and transport tests exercise the production dispatcher normally.
"""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    if pyfuncitem.get_closest_marker("native_engine_fault") is None:
        return None
    from fatebridge.core.astro.native_execution import in_native_worker

    if in_native_worker():
        return None
    worker = Path(__file__).with_name("native_engine_test_worker.py")
    completed = subprocess.run(
        [sys.executable, "-I", str(worker), pyfuncitem.nodeid],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "1 passed" in completed.stdout, completed.stdout + completed.stderr
    return True
