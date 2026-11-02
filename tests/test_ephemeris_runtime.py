"""Unit tests for the shared Swiss Ephemeris runtime helpers."""

from concurrent.futures import ThreadPoolExecutor
from threading import local
from types import SimpleNamespace

import pytest

from fatebridge.core import ephemeris_runtime
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    ephemeris_model_from_retflag,
)


@pytest.fixture(autouse=True)
def preserve_configured_path(monkeypatch):
    # Unit tests mock set_ephe_path; their fake paths must not become the path
    # that later real calculations restore after a Kerykeion call.
    monkeypatch.setattr(
        ephemeris_runtime, "_configured_path", ephemeris_runtime._configured_path
    )
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    monkeypatch.setattr(ephemeris_runtime, "verified_user_ephemeris_dir", lambda: None)


def test_configure_ephemeris_path_uses_explicit_argument(monkeypatch):
    swe = pytest.importorskip("swisseph")
    captured = {}
    monkeypatch.setattr(
        swe, "set_ephe_path", lambda path: captured.setdefault("path", path)
    )

    applied = configure_ephemeris_path("/tmp/fatebridge-ephe")

    assert applied == "/tmp/fatebridge-ephe"
    assert captured["path"] == "/tmp/fatebridge-ephe"


def test_configure_ephemeris_path_reads_env(monkeypatch):
    swe = pytest.importorskip("swisseph")
    captured = {}
    monkeypatch.setattr(
        swe, "set_ephe_path", lambda path: captured.setdefault("path", path)
    )
    monkeypatch.setenv("SE_EPHE_PATH", "/data/ephe")

    applied = configure_ephemeris_path()

    assert applied == "/data/ephe"
    assert captured["path"] == "/data/ephe"


def test_configure_ephemeris_path_initialises_default_without_custom_path(monkeypatch):
    swe = pytest.importorskip("swisseph")
    calls = []
    monkeypatch.setattr(swe, "set_ephe_path", lambda path: calls.append(path))
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    monkeypatch.setattr(ephemeris_runtime, "default_ephe_dir", lambda: None)

    assert configure_ephemeris_path() is None
    assert calls == [""]


def test_configure_ephemeris_path_falls_back_to_default_dir(monkeypatch):
    swe = pytest.importorskip("swisseph")
    captured = {}
    monkeypatch.setattr(
        swe, "set_ephe_path", lambda path: captured.setdefault("path", path)
    )
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    monkeypatch.setattr(ephemeris_runtime, "default_ephe_dir", lambda: "/proj/ephe")

    assert configure_ephemeris_path() == "/proj/ephe"
    assert captured["path"] == "/proj/ephe"


def test_nonempty_env_is_reported_as_the_library_override(monkeypatch):
    swe = pytest.importorskip("swisseph")
    captured = {}
    monkeypatch.setattr(
        swe, "set_ephe_path", lambda path: captured.setdefault("path", path)
    )
    monkeypatch.setenv("SE_EPHE_PATH", "/env/ephe")
    monkeypatch.setattr(ephemeris_runtime, "default_ephe_dir", lambda: "/proj/ephe")

    # The real C library ignores the explicit argument when the env is nonempty.
    # Report its actual selection rather than only what a mock setter received.
    assert configure_ephemeris_path("/explicit/ephe") == "/env/ephe"
    assert captured["path"] == "/env/ephe"


def test_default_ephe_dir_detects_se1_files(tmp_path, monkeypatch):
    ephe = tmp_path / "ephe"
    ephe.mkdir()
    (ephe / "sepl_18.se1").write_bytes(b"SWdata")
    monkeypatch.setattr(ephemeris_runtime, "_PROJECT_ROOT", tmp_path)

    assert ephemeris_runtime.default_ephe_dir() == str(ephe)


def test_default_ephe_dir_ignores_empty_dir(tmp_path, monkeypatch):
    (tmp_path / "ephe").mkdir()
    monkeypatch.setattr(ephemeris_runtime, "_PROJECT_ROOT", tmp_path)

    # A directory with no .se1 files must not mask the Moshier fallback.
    assert ephemeris_runtime.default_ephe_dir() is None


def test_default_ephe_dir_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(ephemeris_runtime, "_PROJECT_ROOT", tmp_path)

    assert ephemeris_runtime.default_ephe_dir() is None


def test_ephemeris_model_from_retflag_maps_known_flags():
    swe = pytest.importorskip("swisseph")

    assert ephemeris_model_from_retflag(swe.FLG_SWIEPH) == "swieph"
    assert ephemeris_model_from_retflag(swe.FLG_MOSEPH) == "moshier"
    assert ephemeris_model_from_retflag(swe.FLG_JPLEPH) == "jpl"


def test_ephemeris_model_from_retflag_flags_errors():
    pytest.importorskip("swisseph")

    assert ephemeris_model_from_retflag(-1) == "error"


def test_ephemeris_model_from_retflag_unavailable(monkeypatch):
    monkeypatch.setattr(ephemeris_runtime, "swe", None)

    assert ephemeris_model_from_retflag(2) == "unavailable"
    assert configure_ephemeris_path("/whatever") is None


def test_direct_calls_initialise_each_worker_and_changed_path_once(monkeypatch):
    state = local()
    applied = []

    def set_path(path):
        state.path = path
        applied.append(path)

    def delta_t(*args):
        assert hasattr(
            state, "path"
        ), "worker called time conversion before initialisation"
        return state.path

    monkeypatch.setattr(
        ephemeris_runtime,
        "swe",
        SimpleNamespace(set_ephe_path=set_path, deltat_ex=delta_t),
    )
    monkeypatch.setattr(ephemeris_runtime, "_configured_path", "/first")
    with ThreadPoolExecutor(max_workers=1) as pool:
        for _ in range(3):
            assert (
                pool.submit(
                    ephemeris_runtime.ephemeris_call, "deltat_ex", 2451545, 2
                ).result()
                == "/first"
            )
        assert applied == ["/first"]
        monkeypatch.setattr(ephemeris_runtime, "_configured_path", "/second")
        assert (
            pool.submit(
                ephemeris_runtime.ephemeris_call, "deltat_ex", 2451545, 2
            ).result()
            == "/second"
        )
        assert applied == ["/first", "/second"]
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert (
            pool.submit(
                ephemeris_runtime.ephemeris_call, "deltat_ex", 2451545, 2
            ).result()
            == "/second"
        )
    assert applied == ["/first", "/second", "/second"]


def test_time_scale_conversion_succeeds_as_first_call_in_fresh_thread(monkeypatch):
    swe = pytest.importorskip("swisseph")
    monkeypatch.setattr(ephemeris_runtime, "_configured_path", None)
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    with ThreadPoolExecutor(max_workers=1) as pool:
        value = pool.submit(
            ephemeris_runtime.ephemeris_call, "deltat_ex", 2451545.0, swe.FLG_SWIEPH
        ).result()
    assert 60 < value * 86400 < 70  # J2000 Delta-T, seconds, not a placeholder.
