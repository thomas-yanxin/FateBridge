"""Runtime guards for Swiss Ephemeris calls that were previously unprotected.

Two sibling call sites compute Swiss Ephemeris houses, but only one was guarded:
``_swisseph_angles`` wraps ``swe.houses_ex`` and degrades to the offline angle
engine, while ``_relative_house_layout`` (used by *every* core/relative chart
with a quadrant house system) called ``swe.houses_ex`` bare. A runtime swisseph
failure there leaked a raw, low-level error.

Per the project's fail-loud stance, a quadrant house system that swisseph cannot
compute must NOT silently degrade — ``_build_houses`` would anchor the cusps on
the ascendant and keep the "placidus" label, faking an approximation. So the
guard re-raises a *clear* error instead.

``_planetary_hours`` is different: ``None`` is its documented "unavailable"
contract, so a failed UT1-to-civil conversion there degrades to ``None`` rather than
crashing the whole chart.
"""

from __future__ import annotations

import pytest

import fatebridge.core.astro.runtime as astrology_core
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.classical import _planetary_hours
from fatebridge.core.astro.geometry import _julian_day

_requires_swe = pytest.mark.skipif(
    astrology_core.swe is None, reason="swisseph 不可用：运行时守卫测试需要 swe"
)

_NATAL = dict(
    name="守卫样例",
    birth_year=2000,
    birth_month=12,
    birth_day=10,
    birth_hour=9,
    birth_minute=55,
    birth_timezone="Asia/Shanghai",
    birth_longitude=120.4667,
    birth_latitude=32.5417,
)


@_requires_swe
def test_quadrant_house_swisseph_runtime_failure_fails_loud(monkeypatch):
    """A runtime swe.houses_ex failure for Placidus raises a clear ValueError.

    Not a raw swisseph error, and crucially NOT a silent degrade to
    equal-from-ascendant cusps mislabeled as Placidus.
    """
    monkeypatch.setattr(astrology_core, "_SWE_RUNTIME_FAILURE_LOGGED", False)

    def _boom(*args, **kwargs):
        raise RuntimeError("swisseph houses_ex exploded")

    monkeypatch.setattr(astrology_core.swe, "houses_ex", _boom)
    info = build_astro_birth_info(**_NATAL)

    with pytest.raises(ValueError, match="placidus.*原生宫头.*RuntimeError") as caught:
        build_core_chart_payload(info, "chart", hsys="placidus")
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert str(caught.value.__cause__) == "swisseph houses_ex exploded"


@_requires_swe
def test_planetary_hours_degrades_to_none_when_civil_conversion_fails(monkeypatch):
    """A failed UT1-to-civil conversion yields the documented unavailable value."""
    monkeypatch.setattr(astrology_core, "_SWE_RUNTIME_FAILURE_LOGGED", False)
    info = build_astro_birth_info(**_NATAL)
    julian_day = _julian_day(info.utc_datetime)

    def _boom(*args, **kwargs):
        raise RuntimeError("swisseph deltat_ex exploded")

    monkeypatch.setattr(astrology_core.swe, "deltat_ex", _boom)

    result = _planetary_hours(
        julian_day, info.longitude, info.latitude, "Asia/Shanghai"
    )
    assert result is None
