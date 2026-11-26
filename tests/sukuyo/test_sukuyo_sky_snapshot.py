"""Native catalogue snapshots must clean up temporary dirs and restore operator path."""

import os
import shutil
from contextlib import contextmanager, nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro import runtime
from fatebridge.core.guolao import guolao

pytestmark = pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")


@pytest.fixture
def catalogue(tmp_path, monkeypatch):
    previous = ephemeris_runtime.configured_ephemeris_path()
    target = tmp_path / "catalogue"
    target.mkdir()
    for name in ("sefstars.txt", "sources.json"):
        shutil.copyfile(guolao.DATA / name, target / name)
    monkeypatch.setattr(guolao, "DATA", target)
    monkeypatch.setattr(ephemeris_runtime, "_configured_path", str(tmp_path / "no-se1"))
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    try:
        yield target
    finally:
        monkeypatch.undo()
        runtime.swe.close()
        ephemeris_runtime.configure_ephemeris_path(previous or "")


@pytest.mark.parametrize("fail_inside", [False, True])
def test_catalogue_snapshot_closes_before_cleanup_and_restores_operator_path(
    catalogue, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_inside: bool
) -> None:
    from fatebridge.core import fixed_star_paths

    operator = tmp_path / "operator"
    operator.mkdir()
    captured_bytes = (catalogue / "sefstars.txt").read_bytes()
    cwd = Path.cwd()
    environment = str(operator)
    monkeypatch.setenv("SE_EPHE_PATH", environment)
    set_ephe_path = runtime.swe.set_ephe_path
    applied = []
    captured_path = None

    @contextmanager
    def observe_cleanup(**kwargs):
        with TemporaryDirectory(**kwargs) as directory:
            nonlocal captured_path
            captured_path = Path(directory)
            yield directory
            assert (captured_path / "sefstars.txt").read_bytes() == captured_bytes
            assert applied[-1] == (environment, environment)

    def observe_path(path):
        applied.append((path, os.environ.get("SE_EPHE_PATH")))
        return set_ephe_path(path)

    monkeypatch.setattr(fixed_star_paths, "TemporaryDirectory", observe_cleanup)
    monkeypatch.setattr(runtime.swe, "set_ephe_path", observe_path)
    error_context = (
        pytest.raises(RuntimeError, match="synthetic") if fail_inside else nullcontext()
    )
    with error_context:
        with fixed_star_paths.fixed_star_catalogue(runtime.swe, captured_bytes):
            assert applied[0] == (str(captured_path), None)
            assert captured_path is not None and not captured_path.exists()
            if fail_inside:
                raise RuntimeError("synthetic native failure")
            else:
                pass
    assert captured_path is not None and not captured_path.exists()
    assert Path.cwd() == cwd
    assert os.environ.get("SE_EPHE_PATH") == environment
