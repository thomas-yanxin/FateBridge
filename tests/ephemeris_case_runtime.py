"""Bind numerical references to their required file runtime, then restore it."""

from contextlib import contextmanager
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as runtime


@contextmanager
def _file_runtime():
    directory = str(Path(__file__).resolve().parents[1] / "ephe")
    previous = runtime.configured_ephemeris_path()
    try:
        with pytest.MonkeyPatch.context() as changed:
            changed.setenv("SE_EPHE_PATH", directory)
            changed.delenv("FATEBRIDGE_JPL_FILE", raising=False)
            runtime.configure_ephemeris_path()
            yield
    finally:
        runtime.configure_ephemeris_path(previous if previous is not None else "")


@pytest.fixture
def native_ephemeris_files():
    with _file_runtime():
        yield


@pytest.fixture(scope="module")
def native_ephemeris_files_module():
    with _file_runtime():
        yield
