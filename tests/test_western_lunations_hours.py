"""Independent lunation times and temporal-hour boundary counterexamples."""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core.astro import classical
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload
from fatebridge.core.astro.geometry import _julian_day
from fatebridge.core.astro.time_scales import (
    datetime_from_ut1,
    ephemeris_time,
    tt_from_ut1,
    ut1_from_tt,
)
from fatebridge.core.classical_western import planetary_hour_sequence
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
    swe,
)

FIXTURES = Path(__file__).parent / "fixtures"
LUNATIONS = json.loads((FIXTURES / "western-usno-lunations-2026.json").read_text())
SEQUENCE = json.loads(
    (FIXTURES / "western-planetary-hour-sequence-dio-1914.json").read_text()
)
pytestmark = pytest.mark.skipif(swe is None, reason="Swiss Ephemeris unavailable")


@pytest.fixture(autouse=True)
def empty_ephemeris_directory(tmp_path):
    previous = configured_ephemeris_path()
    configure_ephemeris_path(str(tmp_path))
    yield
    configure_ephemeris_path(previous)


@pytest.mark.parametrize("case", LUNATIONS["cases"])
def test_all_2026_new_and_full_moons_against_independent_usno_times(case):
    # USNO publishes UT1, not TT or civil UTC. The tzinfo here is a Gregorian
    # calendar-to-JD container; its components are explicitly nominal UT1.
    reference = datetime.fromisoformat(case["nominal_ut1"]).replace(tzinfo=timezone.utc)
    expected_ut1 = _julian_day(reference)
    result = classical._prenatal_syzygy(expected_ut1 + 0.5)
    assert result is not None
    assert result["type"] == case["type"]
    assert (
        abs(result["julian_day_ut1"] - expected_ut1) * 86400
        <= LUNATIONS["tolerance_seconds"]
    )
    assert result["solver"]["strictly_before_birth"] is True
    assert 0 <= result["solver"]["residual_degrees"] < 1e-6


@pytest.mark.parametrize("case", LUNATIONS["cases"])
def test_prenatal_selection_changes_only_after_representable_lunation(case):
    expected_ut1 = _julian_day(
        datetime.fromisoformat(case["nominal_ut1"]).replace(tzinfo=timezone.utc)
    )
    event = classical._prenatal_syzygy(expected_ut1 + 0.5)
    event_tt = event["julian_day_tt"]
    for at in (math.nextafter(event_tt, -math.inf), event_tt):
        previous = classical._prenatal_syzygy(ut1_from_tt(at), julian_day_tt=at)
        assert previous["type"] != event["type"]
        assert previous["julian_day_tt"] < at
        assert 10 < event_tt - previous["julian_day_tt"] < 18
    at = math.nextafter(event_tt, math.inf)
    after = classical._prenatal_syzygy(ut1_from_tt(at), julian_day_tt=at)
    assert after["julian_day_tt"] == event_tt


def test_sidereal_syzygy_keeps_event_and_uses_event_epoch_native_lahiri():
    times = ephemeris_time(datetime(2026, 1, 30, tzinfo=timezone.utc))
    tropical = classical._prenatal_syzygy(times.jd_ut1, julian_day_tt=times.jd_tt)
    sidereal = classical._prenatal_syzygy(
        times.jd_ut1, julian_day_tt=times.jd_tt, sidereal=True
    )
    assert sidereal["julian_day_tt"] == tropical["julian_day_tt"]
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    coordinates, _ = swe.calc(
        sidereal["julian_day_tt"], swe.SUN, swe.FLG_SWIEPH | swe.FLG_SIDEREAL
    )
    assert sidereal["longitude"] == coordinates[0]
    assert sidereal["tropical_longitude"] == tropical["longitude"]
    assert 23 < tropical["longitude"] - sidereal["longitude"] < 26
    info = build_astro_birth_info(
        birth_year=2026,
        birth_month=1,
        birth_day=30,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=51.5,
    )
    chart = build_core_chart_payload(info, "chart", zodiacal=1)
    assert chart["classical"]["syzygy"]["zodiac"] == "sidereal_lahiri"


def test_full_moon_figuris_point_is_not_labeled_as_new_moon():
    from fatebridge.services.astrology import _build_almuten_figuris_line

    info = build_astro_birth_info(
        birth_year=2026,
        birth_month=1,
        birth_day=4,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=51.5,
    )
    chart = build_core_chart_payload(info, "chart")
    assert chart["classical"]["syzygy"]["type"] == "full"
    text = _build_almuten_figuris_line(chart)
    assert "朔望：满月" in text and "朔望→" in text
    assert "朔→" not in text


@pytest.mark.parametrize(
    "date,ruler",
    [
        ("2026-04-15", "Mercury"),
        ("2026-06-01", "Moon"),
        ("2026-09-01", "Mars"),
        ("2026-12-01", "Mars"),
    ],
)
def test_real_sunrise_one_second_later_is_first_hour_of_current_day(date, ruler):
    jd = ephemeris_time(
        datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    ).jd_ut1
    rise = classical._sun_event(jd, 0, 51.5, True)
    result = classical._planetary_hours(rise + 1 / 86400, 0, 51.5, "UTC")
    assert result["hour_number"] == 1
    assert result["is_day"] is True
    assert result["day_ruler"] == result["hour_ruler"] == ruler
    before = classical._planetary_hours(rise - 1 / 86400, 0, 51.5, "UTC")
    assert before["is_day"] is False
    assert before["hour_number"] == 12
    assert before["day_ruler"] != ruler


@pytest.mark.parametrize("ruler,next_day", SEQUENCE["weekday_successors"].items())
def test_hour_cycle_matches_bounded_dio_primary_text(ruler, next_day):
    start = SEQUENCE["order"].index(ruler)
    expected = [SEQUENCE["order"][(start + hour) % 7] for hour in range(24)]
    assert planetary_hour_sequence(ruler) == expected
    assert SEQUENCE["order"][(start + 24) % 7] == next_day


@pytest.mark.parametrize("is_day", [True, False])
@pytest.mark.parametrize("hour", range(1, 12))
def test_unequal_hour_internal_boundaries_are_half_open(monkeypatch, is_day, hour):
    dawn = _julian_day(datetime(2026, 4, 15, 6, tzinfo=timezone.utc))
    # Synthetic consecutive events isolate the definition of a temporal hour
    # from rise_trans's own root tolerance, including one floating-point step.
    dusk = dawn + 0.6
    rises = (dawn, dawn + 1)
    sets = (dawn - 0.4, dusk) if is_day else (dusk, dusk + 1)
    monkeypatch.setattr(
        classical,
        "_bracket_sun_event",
        lambda *args, rising: rises if rising else sets,
    )
    start, end = (dawn, dusk) if is_day else (dusk, dawn + 1)
    boundary = start + (end - start) * hour / 12
    before = classical._planetary_hours(
        math.nextafter(boundary, -math.inf), 0, 51.5, "UTC"
    )
    exact = classical._planetary_hours(boundary, 0, 51.5, "UTC")
    after = classical._planetary_hours(
        math.nextafter(boundary, math.inf), 0, 51.5, "UTC"
    )
    assert before["hour_number"] == hour
    assert exact["hour_number"] == after["hour_number"] == hour + 1
    assert before["is_day"] is exact["is_day"] is after["is_day"] is is_day


def test_planetary_day_weekday_uses_civil_utc_not_ut1_calendar(monkeypatch):
    # At this future epoch the declared Delta T model places UT1 on Sunday
    # while the frozen civil UTC policy places this sunrise on Monday.
    dawn_utc = datetime(2099, 1, 5, 0, 0, 5, tzinfo=timezone.utc)
    dawn = ephemeris_time(dawn_utc).jd_ut1
    assert datetime_from_ut1(dawn).weekday() == 0
    assert swe.revjul(dawn)[2] == 4
    monkeypatch.setattr(
        classical,
        "_bracket_sun_event",
        lambda *args, rising: (dawn, dawn + 1) if rising else (dawn - 0.5, dawn + 0.5),
    )
    result = classical._planetary_hours(dawn + 1 / 86400, 0, 0, "UTC")
    assert result["day_ruler"] == "Moon"
    assert result["planetary_day_start_utc"].startswith("2099-01-05T00:00:05")


@pytest.mark.parametrize(
    "date", ["1900-01-01", "1961-06-01", "1972-01-02", "2017-01-02", "2099-01-05"]
)
def test_ut1_tt_civil_round_trip_preserves_time_policy(date):
    civil = datetime.fromisoformat(date).replace(tzinfo=timezone.utc) + timedelta(
        hours=12
    )
    times = ephemeris_time(civil)
    assert abs(tt_from_ut1(times.jd_ut1) - times.jd_tt) * 86400 < 0.0001
    assert ut1_from_tt(times.jd_tt) == times.jd_ut1
    assert abs((datetime_from_ut1(times.jd_ut1) - civil).total_seconds()) < 0.0001
