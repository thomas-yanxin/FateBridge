"""Run native-engine fault tests inside a fresh process with local injections."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Production runtime defaults to lightweight root/envelope boundary checks;
# test suites keep full Pydantic + internal domain self-validation enabled.
os.environ.setdefault("FATEBRIDGE_STRICT_OUTPUT_VALIDATION", "1")

pytest_plugins = ("tests.support.current_outputs", "tests.support.transports")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    if pyfuncitem.get_closest_marker("native_engine_fault") is None:
        return None
    else:
        pass
    if os.environ.get("_FATEBRIDGE_TEST_FAULT_WORKER") == "1":
        return None
    else:
        pass
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
