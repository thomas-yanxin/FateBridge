"""House-kernel failures and unavailable civil labels keep distinct contracts.

Inject at the actual ARMC kernel and civil-label owner. Physical source/clock
failures still propagate; an optional civil label may make hours unavailable.
"""

from __future__ import annotations

import pytest

import fatebridge.core.astro.runtime as astrology_core
from fatebridge.core.astro import classical
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
    """A runtime house-kernel failure for Placidus raises a clear ValueError.

    Not a raw swisseph error, and crucially NOT a silent degrade to
    equal-from-ascendant cusps mislabeled as Placidus.
    """
    monkeypatch.setattr(astrology_core, "_SWE_RUNTIME_FAILURE_LOGGED", False)

    def _boom(*args, **kwargs):
        raise RuntimeError("swisseph houses_armc exploded")

    monkeypatch.setattr(astrology_core.swe, "houses_armc", _boom)
    info = build_astro_birth_info(**_NATAL)

    with pytest.raises(ValueError, match="placidus.*原生宫头.*RuntimeError") as caught:
        build_core_chart_payload(info, "chart", hsys="placidus")
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert str(caught.value.__cause__) == "swisseph houses_armc exploded"


@_requires_swe
def test_planetary_hours_degrades_to_none_when_civil_conversion_fails(monkeypatch):
    """A failed UT1-to-civil conversion yields the documented unavailable value."""
    monkeypatch.setattr(astrology_core, "_SWE_RUNTIME_FAILURE_LOGGED", False)
    info = build_astro_birth_info(**_NATAL)
    julian_day = _julian_day(info.utc_datetime)

    def _boom(*args, **kwargs):
        raise RuntimeError("civil conversion exploded")

    monkeypatch.setattr(classical, "datetime_from_ut1", _boom)

    result = _planetary_hours(
        julian_day, info.longitude, info.latitude, "Asia/Shanghai"
    )
    assert result is None
