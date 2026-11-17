"""Model-specific tests restore the real native path and derived caches."""

import os
from contextlib import nullcontext

import pytest

from fatebridge.core import ephemeris_runtime as runtime
from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.de441_solar import MODEL_ID as DE441_MODEL
from fatebridge.core.de441_solar import PROVIDER as DE441_PROVIDER
from tests.support.ephemeris_context import empty_ephemeris_path


@pytest.mark.parametrize("caller_policy", [None, "analytic"])
@pytest.mark.parametrize("fail", [False, True])
def test_moshier_model_and_caller_state_are_isolated(monkeypatch, caller_policy, fail):
    swe = pytest.importorskip("swisseph")
    from fatebridge.core.metaphysics.qimen import (
        _qimen_build_yinyangdun_map_from_seeds as cached,
    )

    if caller_policy is None:
        monkeypatch.delenv("FATEBRIDGE_SOLAR_TERM_MODEL", raising=False)
    else:
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", caller_policy)
    previous_path = runtime.configured_ephemeris_path()
    previous_configured = runtime._configured_path
    previous_env = os.environ.get("SE_EPHE_PATH")
    cached((), ())
    assert cached.cache_info().currsize > 0
    with (
        pytest.raises(RuntimeError, match="fixture failure") if fail else nullcontext()
    ):
        with empty_ephemeris_path():
            assert cached.cache_info().currsize == 0
            _, flags = runtime.ephemeris_call(
                "calc_ut", 2451545.0, swe.SUN, swe.FLG_SWIEPH
            )
            assert runtime.ephemeris_model_from_retflag(flags) == "moshier"
            get_solar_terms_for_year(2026)
            cached((), ())
            if fail:
                raise RuntimeError("fixture failure")
    assert runtime.configured_ephemeris_path() == previous_path
    assert runtime._configured_path == previous_configured
    assert os.environ.get("SE_EPHE_PATH") == previous_env
    assert os.environ.get("FATEBRIDGE_SOLAR_TERM_MODEL") == caller_policy
    assert get_solar_terms_for_year.cache_info().currsize == 0
    assert cached.cache_info().currsize == 0


def test_empty_path_does_not_make_calendar_solar_terms_moshier(monkeypatch):
    swe = pytest.importorskip("swisseph")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    with empty_ephemeris_path():
        _, flags = runtime.ephemeris_call(
            "calc", 2451545.0, swe.SUN, swe.FLG_SWIEPH | swe.FLG_SPEED
        )
        terms = get_solar_terms_for_year(2026, "UTC")
        assert runtime.ephemeris_model_from_retflag(flags) == "moshier"
        assert {term.resolution_provider for term in terms} == {DE441_PROVIDER}
        assert {term.ephemeris_model for term in terms} == {DE441_MODEL}
