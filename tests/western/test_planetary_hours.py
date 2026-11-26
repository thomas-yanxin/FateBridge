"""Phase 3b (part 1) tests: planetary hours (行星时).

The sunrise→sunset / sunset→sunrise arc division uses
the physical solar horizon solver (Moshier fallback in its supported range). Pure
hour-sequence chaining is tested directly; the arc geometry + weekday ruler are
pinned against the Dec-2000 natal chart (a Sunday → Sun day-ruler, 4th day hour
→ Moon).

Fixed stars (the other half of Phase 3b) are deferred: they need the
``sefstars.txt`` catalog, an optional-AGPL data file the repo never ships.
"""

from __future__ import annotations

import pytest

from fatebridge.core.astro import classical
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import resolve_ut1_from_tt
from fatebridge.core.classical_western import planetary_hour_sequence
from fatebridge.core.ephemeris_runtime import swe
from fatebridge.services.astrology import calculate_core_chart_analysis
from tests.support.solar_events import fixed_crossings

_SWE_AVAILABLE = swe is not None
_requires_swe = pytest.mark.skipif(
    not _SWE_AVAILABLE, reason="swisseph 不可用：行星时需要太阳视位置"
)

_NATAL = dict(
    birth_year=2000,
    birth_month=12,
    birth_day=10,
    birth_hour=9,
    birth_minute=55,
    birth_timezone="Asia/Shanghai",
    birth_longitude=120.4667,
    birth_latitude=32.5417,
    name="左右",
    birth_place="海安",
)


# ── pure: Chaldean hour chaining ──────────────────────────────────────────────


def test_hour_sequence_starts_at_day_ruler_and_steps_chaldean() -> None:
    # Sun day → Sun, then Chaldean order from there.
    seq = planetary_hour_sequence("Sun")
    assert seq[:4] == ["Sun", "Venus", "Mercury", "Moon"]
    assert len(seq) == 24


def test_hour_chain_rolls_into_next_weekday_ruler() -> None:
    # Continuing one hour past the 24 returns to hour 1 of the *next* day, whose
    # ruler must be the next weekday's planet — this is why the week runs
    # Sun→Mon→Tue…. Sunday(Sun)'s hour-25 ruler is Monday's Moon.
    order = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]
    hour_25_ruler = order[(order.index("Sun") + 24) % 7]
    assert hour_25_ruler == "Moon"
    # And the day's own 24 hours never skip a Chaldean step.
    seq = planetary_hour_sequence("Sun")
    for earlier, later in zip(seq, seq[1:]):
        assert (order.index(later) - order.index(earlier)) % 7 == 1


def test_hour_sequence_rejects_non_traditional_ruler() -> None:
    assert planetary_hour_sequence("Uranus") == []
    assert planetary_hour_sequence("North Node") == []


# ── integration: real arc geometry on the natal chart ─────────────────────────


@pytest.fixture(scope="module")
def natal_hours():
    info = build_astro_birth_info(use_true_solar_time=True, **_NATAL)
    return build_core_chart_payload(info, "hellen_chart")["planetary_hours"]


@_requires_swe
def test_dec_10_2000_is_a_daytime_sunday_sun_ruled_chart(natal_hours) -> None:
    assert natal_hours is not None
    assert natal_hours["is_day"] is True
    # 2000-12-10 is a Sunday → planetary day ruler is the Sun.
    assert natal_hours["day_ruler"] == "Sun"


@_requires_swe
def test_birth_falls_in_the_fourth_day_hour_ruled_by_the_moon(natal_hours) -> None:
    # ~3h after sunrise → 4th unequal day hour. From Sun: Sun→Venus→Mercury→Moon.
    assert natal_hours["hour_number"] == 4
    assert natal_hours["hour_ruler"] == "Moon"


@_requires_swe
def test_hour_number_is_within_one_to_twelve(natal_hours) -> None:
    assert 1 <= natal_hours["hour_number"] <= 12


@_requires_swe
def test_polar_latitude_without_a_sunrise_degrades_to_none() -> None:
    # Deep polar winter: the Sun never rises → the day/night arc is undefined.
    info = build_astro_birth_info(
        birth_year=2000,
        birth_month=12,
        birth_day=21,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0.0,
        birth_latitude=89.0,
        name="polar",
        birth_place="north pole",
    )
    chart = build_core_chart_payload(info, "hellen_chart")
    assert chart["planetary_hours"] is None


@_requires_swe
def test_chart13_uses_declared_solar_weekday() -> None:
    """The Saturday sunrise at 150°E still falls on Friday in UTC."""
    chart = calculate_core_chart_analysis(
        chart_variant="chart13",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_clock_basis="local_mean_solar",
        birth_longitude=150.0,
        birth_latitude=40.0,
        hsys=0,
    )

    hours = chart["planetary_hours"]
    assert hours["planetary_day_start_utc"].startswith("1999-12-31T")
    assert hours["weekday_opening_sunrise_label"].startswith("2000-01-01T")
    assert hours["weekday_clock_basis"] == "local_mean_solar"
    assert hours["day_ruler"] == "Saturn"


@_requires_swe
def test_solar_weekday_retains_opening_sunrise_in_a_utc_leap_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The UTC sunrise label can contain second 60 while solar time is Sunday."""
    # note (planetary hours): The midpoint TT is from the frozen SOFA UTC reference.
    sunrise_ut1 = resolve_ut1_from_tt(2457754.5007949537).as_float()
    assert PhysicalEpoch.from_ut1(sunrise_ut1).utc_is_leap_second
    monkeypatch.setattr(
        classical,
        "solar_crossings_in_window",
        fixed_crossings((sunrise_ut1,), (sunrise_ut1 + 0.5,)),
    )

    hours = classical._planetary_hours(
        sunrise_ut1 + 0.02, 150.0, 40.0, "UTC", weekday_clock_basis="local_mean_solar"
    )

    assert hours is not None
    assert hours["planetary_day_start_utc"].startswith("2016-12-31T23:59:60")
    assert hours["weekday_opening_sunrise_label"].startswith("2017-01-01T")
    assert hours["day_ruler"] == "Sun"


@_requires_swe
def test_hellen_chart_computes_planetary_hours() -> None:
    payload = calculate_core_chart_analysis(
        chart_variant="hellen_chart", use_true_solar_time=True, **_NATAL
    )
    assert payload["planetary_hours"]["hour_ruler"]
    assert payload["planetary_hours"]["day_ruler"]
