"""Golden computations isolate ephemeris data and restore caller state."""

import json
import os
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.almanac import get_solar_terms_for_year
from tests.golden import runner


def test_golden_clears_the_actual_qimen_derived_cache_on_entry_and_exit():
    from fatebridge.core.metaphysics.qimen import (
        _qimen_build_yinyangdun_map_from_seeds as cached,
    )

    cached((), ())
    assert cached.cache_info().currsize > 0
    with runner.golden_ephemeris():
        assert cached.cache_info().currsize == 0
        cached((), ())
        assert cached.cache_info().currsize > 0
    assert cached.cache_info().currsize == 0


def test_golden_still_rejects_an_actual_cache_without_clear(monkeypatch):
    from fatebridge.core.metaphysics import qimen

    monkeypatch.setattr(
        qimen, "_qimen_build_yinyangdun_map_from_seeds", lambda a, b: {}
    )
    with pytest.raises(RuntimeError, match="no callable cache_clear"):
        runner._clear_ephemeris_dependent_caches()


@pytest.mark.parametrize("caller_policy", [None, "analytic"])
@pytest.mark.parametrize("fail", [False, True])
def test_golden_pins_actual_solar_model_and_restores_caller_policy(
    monkeypatch, tmp_path, caller_policy, fail
):
    from fatebridge.core.fengshui.calendar import solar_term_resolution

    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    if caller_policy is None:
        monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    else:
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", caller_policy)
    before = solar_term_resolution(2026, "立春", "UTC")
    with (
        pytest.raises(RuntimeError, match="fixture failure") if fail else nullcontext()
    ):
        with runner.golden_ephemeris():
            actual = solar_term_resolution(2026, "立春", "UTC")
            assert actual["ephemeris_model"] == "moshier"
            assert actual["provider"] == "swisseph"
            assert os.environ["FATEBRIDGE_SOLAR_TERM_MODEL"] == "native"
            if fail:
                raise RuntimeError("fixture failure")
    assert os.environ.get("FATEBRIDGE_SOLAR_TERM_MODEL") == caller_policy
    after = solar_term_resolution(2026, "立春", "UTC")
    assert after["ephemeris_model"] == before["ephemeris_model"]
    assert after["provider"] == before["provider"]


@pytest.mark.parametrize("original_env", [None, "", "/operator/ephe"])
@pytest.mark.parametrize("fail", [False, True])
@pytest.mark.parametrize("configured", [None, "local"])
def test_compute_outputs_forces_moshier_and_restores_state(
    monkeypatch, tmp_path, original_env, fail, configured
):
    swe = pytest.importorskip("swisseph")
    original_path = runtime.configured_ephemeris_path()
    local_ephe = tmp_path / "ephe"
    local_ephe.mkdir()
    (local_ephe / "sepl_18.se1").write_bytes(b"local-data-must-not-be-read")
    monkeypatch.setattr(runtime, "_PROJECT_ROOT", tmp_path)
    if original_env is None:
        monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    else:
        monkeypatch.setenv("SE_EPHE_PATH", original_env)
    previous_configured = str(local_ephe) if configured else None
    monkeypatch.setattr(runtime, "_configured_path", previous_configured)
    calls = []
    real_set_path = swe.set_ephe_path

    def set_path(path):
        calls.append(path)
        return real_set_path(path)

    monkeypatch.setattr(swe, "set_ephe_path", set_path)
    monkeypatch.setattr(runner, "REST_POST_CASES", {"/probe": lambda: {}})
    monkeypatch.setattr(runner, "_MCP_ONLY_CASES", {})
    isolated_paths = []

    class Client:
        def __init__(self, app):
            pass

        def post(self, path, json):
            directory = runtime.configured_ephemeris_path()
            isolated_paths.append(directory)
            assert directory == os.environ["SE_EPHE_PATH"]
            assert directory != str(local_ephe)
            assert list(Path(directory).iterdir()) == []
            assert get_solar_terms_for_year.cache_info().currsize == 0
            # Real C-library return flags prove the actual model, not just config.
            _, flag = runtime.ephemeris_call(
                "calc_ut", 2451545.0, swe.SUN, swe.FLG_SWIEPH
            )
            assert runtime.ephemeris_model_from_retflag(flag) == "moshier"
            get_solar_terms_for_year(2026)
            return SimpleNamespace(
                status_code=500 if fail else 200,
                text="probe error",
                json=lambda: {"model": "moshier"},
            )

    monkeypatch.setattr(runner, "TestClient", Client)
    # Pre-existing terms must be invalidated, as must terms built inside golden.
    prime = tmp_path / "empty-prime"
    prime.mkdir()
    with monkeypatch.context() as priming:
        priming.setenv("SE_EPHE_PATH", str(prime))
        runtime.configure_ephemeris_path(str(prime))
        get_solar_terms_for_year(2025)
        assert get_solar_terms_for_year.cache_info().currsize > 0
    # The intentionally corrupt local file cannot prime a successful cache.
    # Restore the original selectors before testing golden's isolation.
    runtime._configured_path = previous_configured
    try:
        if fail:
            with pytest.raises(AssertionError, match="probe error"):
                runner.compute_outputs()
        else:
            assert json.loads(runner.compute_outputs()["probe"]) == {"model": "moshier"}
        assert os.environ.get("SE_EPHE_PATH") == original_env
        assert runtime._configured_path == previous_configured
        effective = original_env or previous_configured
        assert runtime.configured_ephemeris_path() == effective
        assert calls[-1] == (effective or "")
        assert get_solar_terms_for_year.cache_info().currsize == 0
        assert all(not Path(path).exists() for path in isolated_paths)
    finally:
        # Our local-path probe is fake; restore the real C path for sibling tests.
        monkeypatch.undo()
        with runtime._EPHEMERIS_LOCK:
            real_set_path(original_path or "")
