"""Phase 3b (part 1) tests: planetary hours (行星时).

The sunrise→sunset / sunset→sunrise arc division runs on swisseph's
``rise_trans`` (works on the Moshier model, so it's available everywhere). Pure
hour-sequence chaining is tested directly; the arc geometry + weekday ruler are
pinned against the Dec-2000 natal chart (a Sunday → Sun day-ruler, 4th day hour
→ Moon).

Fixed stars (the other half of Phase 3b) are deferred: they need the
``sefstars.txt`` catalog, an optional-AGPL data file the repo never ships.
"""

from __future__ import annotations

import pytest

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.classical_western import planetary_hour_sequence
from fatebridge.core.ephemeris_runtime import swe
from fatebridge.services.astrology import calculate_core_chart_analysis

_SWE_AVAILABLE = swe is not None
_requires_swe = pytest.mark.skipif(
    not _SWE_AVAILABLE, reason="swisseph 不可用：行星时需要 rise_trans"
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


def test_hour_sequence_starts_at_day_ruler_and_steps_chaldean():
    # Sun day → Sun, then Chaldean order from there.
    seq = planetary_hour_sequence("Sun")
    assert seq[:4] == ["Sun", "Venus", "Mercury", "Moon"]
    assert len(seq) == 24


def test_hour_chain_rolls_into_next_weekday_ruler():
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


def test_hour_sequence_rejects_non_traditional_ruler():
    assert planetary_hour_sequence("Uranus") == []
    assert planetary_hour_sequence("North Node") == []


# ── integration: real arc geometry on the natal chart ─────────────────────────


@pytest.fixture(scope="module")
def natal_hours():
    info = build_astro_birth_info(use_true_solar_time=True, **_NATAL)
    return build_core_chart_payload(info, "hellen_chart")["planetary_hours"]


@_requires_swe
def test_dec_10_2000_is_a_daytime_sunday_sun_ruled_chart(natal_hours):
    assert natal_hours is not None
    assert natal_hours["is_day"] is True
    # 2000-12-10 is a Sunday → planetary day ruler is the Sun.
    assert natal_hours["day_ruler"] == "Sun"


@_requires_swe
def test_birth_falls_in_the_fourth_day_hour_ruled_by_the_moon(natal_hours):
    # ~3h after sunrise → 4th unequal day hour. From Sun: Sun→Venus→Mercury→Moon.
    assert natal_hours["hour_number"] == 4
    assert natal_hours["hour_ruler"] == "Moon"


@_requires_swe
def test_hour_number_is_within_one_to_twelve(natal_hours):
    assert 1 <= natal_hours["hour_number"] <= 12


@_requires_swe
def test_polar_latitude_without_a_sunrise_degrades_to_none():
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
def test_snapshot_renders_planetary_hours_section():
    payload = calculate_core_chart_analysis(
        chart_variant="hellen_chart", use_true_solar_time=True, **_NATAL
    )
    text = payload["snapshot_text"]
    assert "[行星时]" in text
    assert "生时主星：" in text
    assert "当日主星：" in text
