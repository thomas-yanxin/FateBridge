"""Native return searches must not inherit the optional linear offset fallback."""

import math

import pytest

from fatebridge.core.astro import geometry
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    preserve_ephemeris_path,
    swe,
)
from fatebridge.core.predictive.returns import _longitude_tt
from fatebridge.utils.errors import EphemerisSourceError


@pytest.mark.parametrize("failure", ["exception", "negative_flags", "nonfinite"])
def test_sidereal_return_offset_failure_never_becomes_linear_success(
    monkeypatch, failure
):
    original = geometry.runtime.ephemeris_call

    def unavailable(operation, *args, **kwargs):
        if operation not in {"get_ayanamsa_ex_ut", "get_ayanamsa_ex"}:
            return original(operation, *args, **kwargs)
        if failure == "exception":
            raise RuntimeError("Synthetic native offset failure")
        return (-1, 23.0) if failure == "negative_flags" else (2, math.nan)

    monkeypatch.setattr(geometry.runtime, "ephemeris_call", unavailable)
    with pytest.raises(RuntimeError, match="Native Lahiri ayanamsha unavailable"):
        _longitude_tt(swe.SUN, 2451545.0, sidereal=True)


def test_sidereal_return_preserves_source_integrity_failure(monkeypatch):
    original = geometry.runtime.ephemeris_call
    failure = EphemerisSourceError("physical_configuration_changed")

    def unavailable(operation, *args, **kwargs):
        if operation in {"get_ayanamsa_ex_ut", "get_ayanamsa_ex"}:
            raise failure
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(geometry.runtime, "ephemeris_call", unavailable)
    with pytest.raises(EphemerisSourceError) as caught:
        _longitude_tt(swe.SUN, 2451545.0, sidereal=True)
    assert caught.value is failure


@pytest.mark.parametrize("body", [swe.SUN, swe.MOON])
@pytest.mark.parametrize("tt", [2451545.0, 2460462.7708333335])
def test_return_longitude_matches_native_sidereal_coordinates_at_the_same_tt(body, tt):
    with preserve_ephemeris_path():
        swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
        coordinates, flags = ephemeris_call(
            "calc", tt, body, swe.FLG_SWIEPH | swe.FLG_SIDEREAL
        )
    assert flags >= 0
    actual = _longitude_tt(body, tt, sidereal=True)
    difference = (actual - coordinates[0] + 180) % 360 - 180
    assert abs(difference) < 1e-10
