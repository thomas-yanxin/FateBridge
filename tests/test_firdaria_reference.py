"""Acceptance vectors for production firdaria and an independent calendar oracle.

The independent oracle checks production against the original reference vectors.
Sect is supplied explicitly, so these tests do not validate natal astronomy.
"""

import json
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from dateutil import tz

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.predictive.firdaria import (
    _calendar_anniversary,
    build_firdaria_payload,
)

VECTORS = json.loads(
    (Path(__file__).parent / "fixtures" / "firdaria-reference.json").read_text(
        encoding="utf-8"
    )
)
UTC = timezone.utc
MICROSECOND = timedelta(microseconds=1)
# Independent specification values, deliberately not imported from the engine.
SECONDS_PER_LEGACY_YEAR = 31_556_952
PERIOD_YEARS = {
    "Sun": 10,
    "Venus": 8,
    "Mercury": 13,
    "Moon": 9,
    "Saturn": 11,
    "Jupiter": 12,
    "Mars": 7,
    "North Node": 3,
    "South Node": 2,
}


def _reference_local(raw, timezone_name):
    """Reject wall-clock ambiguity instead of guessing a DST offset."""
    naive = datetime.fromisoformat(raw)
    assert naive.tzinfo is None
    if timezone_name.startswith(("+", "-")):
        zone = datetime.fromisoformat("2000-01-01T00:00:00" + timezone_name).tzinfo
    else:
        zone = ZoneInfo(timezone_name)
    local = naive.replace(tzinfo=zone)
    if not tz.datetime_exists(local):
        raise ValueError("nonexistent local time; confirm a valid instant")
    if tz.datetime_ambiguous(local):
        raise ValueError("ambiguous local time; confirm an explicit offset")
    return local


def _reference_anniversary(birth, age):
    year = birth.year + age
    day = min(birth.day, monthrange(year, birth.month)[1])
    local = birth.replace(year=year, day=day, tzinfo=None)
    # Always start from the original birthday, never a clamped prior endpoint.
    if isinstance(birth.tzinfo, ZoneInfo):
        return _reference_local(local.isoformat(), birth.tzinfo.key)
    return local.replace(tzinfo=birth.tzinfo)


def _reference_sub_boundaries(start, end):
    start_utc, end_utc = start.astimezone(UTC), end.astimezone(UTC)
    ticks = (end_utc - start_utc) // MICROSECOND
    return [
        (start_utc + round(Fraction(ticks * k, 7)) * MICROSECOND).astimezone(
            start.tzinfo
        )
        for k in range(8)
    ]


def _display_minute(moment, display_timezone):
    local = moment.astimezone(display_timezone).replace(second=0, microsecond=0)
    return local.isoformat(sep=" ", timespec="minutes").replace("T", " ")


def _production(birth, sect, target=None, **options):
    """Use the real arithmetic with a supplied sect, not an invented birthplace."""
    info = AstroBirthInfo(
        name="法达时间测试",
        birth_place="UTC arithmetic fixture; not a natal observation",
        timezone=str(birth.tzinfo),
        longitude=0.0,
        latitude=0.0,
        local_datetime=birth,
        utc_datetime=birth.astimezone(UTC),
    )
    sun_house = "Tenth_House" if sect == "day" else "Fifth_House"
    subject = SimpleNamespace(sun=SimpleNamespace(house=sun_house))
    return build_firdaria_payload(
        info,
        subject,
        analysis_datetime=target if target is not None else birth,
        **options,
    )


def _example_birth(case):
    return _reference_local(case["birth_local"], case["timezone"])


@pytest.mark.parametrize("schedule", VECTORS["periods"])
def test_reference_age_tables_are_complete_cycles(schedule):
    rows = VECTORS["periods"][schedule]
    assert len(rows) == 9
    assert {planet for planet, _, _ in rows} == PERIOD_YEARS.keys()
    assert rows[0][1] == 0 and rows[-1][2] == 75
    assert [row[2] for row in rows[:-1]] == [row[1] for row in rows[1:]]
    for planet, start_age, end_age in rows:
        assert end_age - start_age == PERIOD_YEARS[planet]


@pytest.mark.parametrize("case", VECTORS["examples"], ids=lambda case: case["id"])
def test_reference_original_examples_preserve_precision_and_display(case):
    birth = _example_birth(case)
    end = _reference_anniversary(birth, case["years"])
    first = _reference_sub_boundaries(birth, end)[1]
    assert end.isoformat() == case["reference_major_end"]
    assert (end.astimezone(UTC) - birth.astimezone(UTC)) == timedelta(
        minutes=case["calendar_minutes"]
    )
    assert first.isoformat() == case["reference_first_sub_end"]
    # ISO puts the offset immediately after the clock; the fixture separates it.
    assert _display_minute(first, birth.tzinfo) == case[
        "display_first_sub_end"
    ].replace(" +", "+")
    assert first.second > 0  # Display truncation must not erase the exact boundary.
    production = _production(
        birth,
        case["sect"],
        firdaria_night_order="nodes_after_mars",
        firdaria_year_basis="calendar_anniversary",
    )
    major = production["timeline"][0]
    assert major["end"] == case["reference_major_end"]
    assert major["subperiods"][0]["end"] == case["reference_first_sub_end"]
    assert major["subperiods"][0]["end_display"] == case[
        "display_first_sub_end"
    ].replace(" +", "+")


@pytest.mark.parametrize("case", VECTORS["examples"], ids=lambda case: case["id"])
def test_production_original_examples_have_distinct_fixed_year_boundaries(case):
    result = _production(_example_birth(case), case["sect"])
    major = result["timeline"][0]
    assert result["sect"] == case["sect"]
    assert major["end"] == case["legacy_major_end"]
    assert major["subperiods"][0]["end"] == case["legacy_first_sub_end"]
    assert major["end"] != case["reference_major_end"]
    assert major["subperiods"][0]["end"] != case["reference_first_sub_end"]


@pytest.mark.parametrize("sect,schedule", [("day", "day"), ("night", "legacy_night")])
def test_production_full_cycle_and_all_subperiod_lords(sect, schedule):
    birth = datetime(2000, 1, 1, tzinfo=UTC)
    result = _production(birth, sect)
    for major, (planet, start_age, end_age) in zip(
        result["timeline"][:9], VECTORS["periods"][schedule], strict=True
    ):
        assert major["planet"] == planet
        assert major["years"] == PERIOD_YEARS[planet]
        assert datetime.fromisoformat(major["start"]) == birth + timedelta(
            seconds=start_age * SECONDS_PER_LEGACY_YEAR
        )
        assert datetime.fromisoformat(major["end"]) == birth + timedelta(
            seconds=end_age * SECONDS_PER_LEGACY_YEAR
        )
        subs = major["subperiods"]
        assert [sub["planet"] for sub in subs] == VECTORS["subperiods"][planet]
        if subs:
            assert subs[0]["start"] == major["start"]
            assert subs[-1]["end"] == major["end"]
            assert [sub["end"] for sub in subs[:-1]] == [
                sub["start"] for sub in subs[1:]
            ]


@pytest.mark.parametrize("case", VECTORS["anniversaries"], ids=lambda case: case["id"])
def test_reference_leap_anniversaries_use_original_anchor(case):
    birth = _reference_local(case["birth_local"], "UTC")
    assert _reference_anniversary(birth, case["age"]).isoformat() == case["expected"]
    assert _calendar_anniversary(birth, case["age"]).isoformat() == case["expected"]


def test_production_leap_birth_keeps_fixed_year_arithmetic():
    birth = datetime(2000, 2, 29, 12, tzinfo=UTC)
    timeline = _production(birth, "night")["timeline"]
    assert timeline[0]["end"] == "2009-02-28T16:22:48+00:00"
    assert timeline[1]["end"] == "2020-02-29T08:24:00+00:00"
    assert timeline[8]["end"] == "2075-02-28T16:30:00+00:00"


@pytest.mark.parametrize("case", VECTORS["timezone_cases"], ids=lambda case: case["id"])
def test_reference_partitions_real_elapsed_time_and_converts_display(case):
    birth = _example_birth(case)
    end = _reference_anniversary(birth, case["age"])
    first = _reference_sub_boundaries(birth, end)[1]
    assert end.isoformat() == case["major_end"]
    assert first.isoformat() == case["first_sub_end"]
    assert first.astimezone(UTC).isoformat() == case["first_sub_utc"]
    assert datetime.fromisoformat(case["first_sub_utc"]) == first
    major = _production(birth, "day", firdaria_year_basis="calendar_anniversary")[
        "timeline"
    ][0]
    assert major["end"] == case["major_end"]
    assert major["subperiods"][0]["end"] == case["first_sub_end"]


@pytest.mark.parametrize(
    "case", VECTORS["invalid_local_times"], ids=lambda case: case["id"]
)
def test_reference_rejects_ambiguous_or_nonexistent_wall_clocks(case):
    with pytest.raises(ValueError, match=case["reason"]):
        birth = _example_birth(case)
        _reference_anniversary(birth, case["age"])
    # Deliberately attach the zone without the oracle's validation, so production
    # has to reject the original input or the independently generated anniversary.
    birth = datetime.fromisoformat(case["birth_local"]).replace(
        tzinfo=ZoneInfo(case["timezone"])
    )
    with pytest.raises(ValueError, match=case["reason"]):
        _production(birth, "night", firdaria_year_basis="calendar_anniversary")


@pytest.mark.parametrize("offset", ["+01:00", "+02:00"])
def test_reference_explicit_offsets_distinguish_repeated_birth_clock(offset):
    birth = _reference_local("2023-10-29T02:30:00", offset)
    expected_hour = 1 if offset == "+01:00" else 0
    assert birth.astimezone(UTC) == datetime(
        2023, 10, 29, expected_hour, 30, tzinfo=UTC
    )
    assert (
        _production(birth, "night", firdaria_year_basis="calendar_anniversary")[
            "timeline"
        ][0]["start"]
        == birth.isoformat()
    )


def test_production_dst_behavior_is_local_wall_addition_not_utc_addition():
    birth = _reference_local("2000-01-01T00:00:00", "Europe/Berlin")
    first = _production(birth, "day")["timeline"][0]["subperiods"][0]
    end = datetime.fromisoformat(first["end"])
    nominal_duration = timedelta(seconds=10 * SECONDS_PER_LEGACY_YEAR) / 7
    assert end.utcoffset() == timedelta(hours=2)
    assert end.astimezone(UTC) - birth.astimezone(UTC) == (
        nominal_duration - timedelta(hours=1)
    )


@pytest.mark.parametrize("sect", ["day", "night"])
def test_production_exact_boundaries_nodes_and_75_year_restart(sect):
    birth = datetime(2000, 1, 1, tzinfo=UTC)
    timeline = _production(birth, sect)["timeline"]
    for major in timeline[:10]:
        start = datetime.fromisoformat(major["start"])
        selected = _production(birth, sect, start)
        assert selected["current_major"]["planet"] == major["planet"]
        subs = major["subperiods"]
        if not subs:
            assert selected["current_sub"] is None
        for sub in subs:
            target = datetime.fromisoformat(sub["start"])
            active = _production(birth, sect, target)["current_sub"]
            assert active["planet"] == sub["planet"]
            assert active["start"] == sub["start"]
    restart = birth + timedelta(seconds=75 * SECONDS_PER_LEGACY_YEAR)
    assert (
        _production(birth, sect, restart - MICROSECOND)["current_major"]["planet"]
        == "South Node"
    )
    assert _production(birth, sect, restart)["current_major"]["planet"] == (
        "Sun" if sect == "day" else "Moon"
    )


@pytest.mark.parametrize("schedule", ["day", "reference_night"])
def test_reference_cycle_boundaries_subdivision_and_restart(schedule):
    birth = _reference_local("2000-02-29T12:00:00", "UTC")
    periods = []
    for cycle in range(2):
        for planet, start_age, end_age in VECTORS["periods"][schedule]:
            start = _reference_anniversary(birth, start_age + 75 * cycle)
            end = _reference_anniversary(birth, end_age + 75 * cycle)
            periods.append((planet, start, end))
            if VECTORS["subperiods"][planet]:
                bounds = _reference_sub_boundaries(start, end)
                assert bounds[0] == start and bounds[-1] == end
                ticks = [
                    (right.astimezone(UTC) - left.astimezone(UTC)) // MICROSECOND
                    for left, right in zip(bounds, bounds[1:])
                ]
                assert max(ticks) - min(ticks) <= 1
                assert sum(ticks) == (end - start) // MICROSECOND
                for k, boundary in enumerate(bounds[1:-1], start=1):
                    # Full precision, not displayed minutes, assigns the sub-lord.
                    assert bounds[k - 1] <= boundary - MICROSECOND < bounds[k]
                    assert bounds[k] <= boundary < bounds[k + 1]
    for index, (_, start, end) in enumerate(periods[:-1]):
        assert end == periods[index + 1][1]
        assert [row[0] for row in periods if row[1] <= end < row[2]] == [
            periods[index + 1][0]
        ]
        assert [row[0] for row in periods if row[1] <= end - MICROSECOND < row[2]] == [
            periods[index][0]
        ]
    assert periods[8][2] == datetime(2075, 2, 28, 12, tzinfo=UTC)
    assert periods[9][0] == periods[0][0]
    sect = "day" if schedule == "day" else "night"
    options = {
        "firdaria_night_order": "nodes_after_mars",
        "firdaria_year_basis": "calendar_anniversary",
    }
    production = _production(birth, sect, **options)
    for major, (planet, start, end) in zip(production["timeline"], periods):
        assert (major["planet"], major["start"], major["end"]) == (
            planet,
            start.isoformat(),
            end.isoformat(),
        )
        assert [sub["planet"] for sub in major["subperiods"]] == VECTORS["subperiods"][
            planet
        ]
        if major["subperiods"]:
            expected_bounds = _reference_sub_boundaries(start, end)
            assert [sub["start"] for sub in major["subperiods"]] == [
                bound.isoformat() for bound in expected_bounds[:-1]
            ]
            assert major["subperiods"][-1]["end"] == major["end"]
            for sub in major["subperiods"]:
                instant = datetime.fromisoformat(sub["start"])
                active = _production(birth, sect, instant, **options)
                assert active["current_sub"]["planet"] == sub["planet"]
        active = _production(birth, sect, start, **options)
        assert active["current_major"]["planet"] == planet
        if not major["subperiods"]:
            assert active["current_sub"] is None
        if start > birth:
            previous = _production(birth, sect, start - MICROSECOND, **options)
            assert previous["current_major"]["end"] == start.isoformat()
    assert production["timeline"][8]["nominal_end_age"] == 75
    assert (
        _production(birth, sect, periods[9][1], **options)["current_major"]["planet"]
        == periods[0][0]
    )


@pytest.mark.parametrize("sect", ["day", "night"])
@pytest.mark.parametrize("basis", ["fixed_365_2425", "calendar_anniversary"])
@pytest.mark.parametrize("night_order", ["nodes_at_end", "nodes_after_mars"])
def test_production_options_are_independent(sect, basis, night_order):
    birth = datetime(2000, 1, 1, tzinfo=UTC)
    result = _production(
        birth, sect, firdaria_night_order=night_order, firdaria_year_basis=basis
    )
    schedule = (
        "day"
        if sect == "day"
        else ("legacy_night" if night_order == "nodes_at_end" else "reference_night")
    )
    for major, (planet, start_age, end_age) in zip(
        result["timeline"][:9], VECTORS["periods"][schedule], strict=True
    ):
        assert major["planet"] == planet
        expected = (
            _reference_anniversary(birth, end_age)
            if basis == "calendar_anniversary"
            else birth + timedelta(seconds=end_age * SECONDS_PER_LEGACY_YEAR)
        )
        assert major["end"] == expected.isoformat()
    if (night_order, basis) == ("nodes_at_end", "fixed_365_2425"):
        assert result == _production(birth, sect)
        assert "calculation_options" not in result
    else:
        assert result["calculation_options"]["night_order"] == night_order
        assert result["calculation_options"]["year_basis"] == basis


@pytest.mark.parametrize("second,microsecond", [(0, 1), (34, 285714), (59, 999999)])
def test_reference_minute_display_always_truncates_without_mutating_instant(
    second, microsecond
):
    exact = datetime(2003, 3, 18, 4, 48, second, microsecond, tzinfo=UTC)
    original = exact.isoformat()
    assert _display_minute(exact, UTC) == "2003-03-18 04:48+00:00"
    assert _display_minute(exact, timezone(timedelta(hours=8))) == (
        "2003-03-18 12:48+08:00"
    )
    assert exact.isoformat() == original
