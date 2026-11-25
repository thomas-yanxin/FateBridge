"""Shared pinned JPL kernel fixture for native source checks."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e

FIXTURES = Path(__file__).parents[2] / "data/astrodice/tables"
KERNEL = "de441-j2000.eph"


@pytest.fixture
def jpl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    previous = e.configured_ephemeris_path()
    kernel = tmp_path / KERNEL
    kernel.write_bytes((FIXTURES / KERNEL).read_bytes())
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_JPL_FILE", KERNEL)
    e.configure_ephemeris_path()
    try:
        yield kernel
    finally:
        # The tests also change these variables. Restore the whole shared
        # monkeypatch stack before restoring the runtime, in the same order.
        monkeypatch.undo()
        e.configure_ephemeris_path(previous if previous is not None else "")
