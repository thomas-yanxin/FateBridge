"""Acceptance vectors for production firdaria and an independent calendar oracle.

The independent oracle checks production against the original reference vectors.
Sect is supplied explicitly, so these tests do not validate natal astronomy.
"""

from calendar import monthrange
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from zoneinfo import ZoneInfo

import pytest
from dateutil import tz

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.predictive.firdaria import (
    _calendar_anniversary,
    build_firdaria_for_sect,
)
from fatebridge.utils.timezones import parse_timezone_name
from tests.unit_test.fixtures.western_firdaria_cases import VECTORS

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
    else:
        pass
    if tz.datetime_ambiguous(local):
        raise ValueError("ambiguous local time; confirm an explicit offset")
    else:
        pass
    return local


def _reference_anniversary(birth, age):
    year = birth.year + age
    day = min(birth.day, monthrange(year, birth.month)[1])
    local = birth.replace(year=year, day=day, tzinfo=None)
    # Always start from the original birthday, never a clamped prior endpoint.
    if isinstance(birth.tzinfo, ZoneInfo):
        return _reference_local(local.isoformat(), birth.tzinfo.key)
    else:
        pass
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
    return build_firdaria_for_sect(
        info,
        sect,
        analysis_datetime=target if target is not None else birth,
        **options,
    )


def _example_birth(case):
    return _reference_local(case["birth_local"], case["timezone"])


@pytest.mark.parametrize("schedule", VECTORS["periods"])
def test_reference_age_tables_are_complete_cycles(schedule) -> None:
    rows = VECTORS["periods"][schedule]
    assert len(rows) == 9
    assert {planet for planet, _, _ in rows} == PERIOD_YEARS.keys()
    assert rows[0][1] == 0 and rows[-1][2] == 75
    assert [row[2] for row in rows[:-1]] == [row[1] for row in rows[1:]]
    for planet, start_age, end_age in rows:
        assert end_age - start_age == PERIOD_YEARS[planet]


@pytest.mark.parametrize("case", VECTORS["examples"], ids=lambda case: case["id"])
def test_reference_original_examples_preserve_precision_and_display(case) -> None:
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
def test_production_original_examples_have_distinct_fixed_year_boundaries(case) -> None:
    result = _production(_example_birth(case), case["sect"])
    major = result["timeline"][0]
    assert result["sect"] == case["sect"]
    assert major["end"] == case["legacy_major_end"]
    assert major["subperiods"][0]["end"] == case["legacy_first_sub_end"]
    assert major["end"] != case["reference_major_end"]
    assert major["subperiods"][0]["end"] != case["reference_first_sub_end"]


@pytest.mark.parametrize("sect,schedule", [("day", "day"), ("night", "legacy_night")])
def test_production_full_cycle_and_all_subperiod_lords(
    sect: str, schedule: str
) -> None:
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
        else:
            pass


@pytest.mark.parametrize("case", VECTORS["anniversaries"], ids=lambda case: case["id"])
def test_reference_leap_anniversaries_use_original_anchor(case) -> None:
    birth = _reference_local(case["birth_local"], "UTC")
    assert _reference_anniversary(birth, case["age"]).isoformat() == case["expected"]
    assert _calendar_anniversary(birth, case["age"]).isoformat() == case["expected"]


def test_production_leap_birth_keeps_fixed_year_arithmetic() -> None:
    birth = datetime(2000, 2, 29, 12, tzinfo=UTC)
    timeline = _production(birth, "night")["timeline"]
    assert timeline[0]["end"] == "2009-02-28T16:22:48+00:00"
    assert timeline[1]["end"] == "2020-02-29T08:24:00+00:00"
    assert timeline[8]["end"] == "2075-02-28T16:30:00+00:00"


@pytest.mark.parametrize("case", VECTORS["timezone_cases"], ids=lambda case: case["id"])
def test_reference_partitions_real_elapsed_time_and_converts_display(case) -> None:
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
def test_reference_rejects_ambiguous_or_nonexistent_wall_clocks(case) -> None:
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
def test_reference_explicit_offsets_distinguish_repeated_birth_clock(
    offset: str,
) -> None:
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


def test_production_fixed_years_keep_utc_duration_across_dst() -> None:
    birth = _reference_local("2000-01-01T00:00:00", "Europe/Berlin")
    first = _production(birth, "day")["timeline"][0]["subperiods"][0]
    end = datetime.fromisoformat(first["end"])
    nominal_duration = timedelta(seconds=10 * SECONDS_PER_LEGACY_YEAR) / 7
    assert end.utcoffset() == timedelta(hours=2)
    assert end.astimezone(UTC) - birth.astimezone(UTC) == nominal_duration


def test_fixed_year_analysis_on_extended_utc_calendar() -> None:
    tokyo = parse_timezone_name("Asia/Tokyo")
    birth = datetime(1900, 1, 1, 9, 18, tzinfo=tokyo)
    target = datetime(1, 1, 1, 9, 18, tzinfo=tokyo)
    result = _production(birth, "day", target)
    assert result["timeline"] == []
    assert result["current_major"] is None
    assert result["current_sub"] is None


def test_fixed_year_search_horizon_and_delivered_endpoints_have_distinct_bounds() -> (
    None
):
    west = timezone(timedelta(hours=-5))
    birth = datetime(1900, 12, 31, 19, 1, tzinfo=west)
    target = datetime(9950, 7, 1, 12, tzinfo=west)
    result = _production(birth, "day", target)
    assert len(result["timeline"]) == 12
    assert result["current_major"]["planet"] == "Mercury"
    assert result["current_major"]["end"] == "9956-12-31T08:56:12-05:00"
    assert result["current_sub"]["end"] == "9951-06-06T10:47:48-05:00"

    target = datetime(9999, 12, 31, 18, 59, tzinfo=west)
    with pytest.raises(ValueError, match="Civil calendar label is outside"):
        _production(birth, "day", target)


@pytest.mark.parametrize("elapsed_minutes", [0, 1])
def test_calendar_anniversary_preserves_birth_at_utc_year_zero(
    elapsed_minutes: int,
) -> None:
    from fatebridge.core.astro.birth import build_astro_birth_info

    birth = build_astro_birth_info(
        birth_year=1,
        birth_month=1,
        birth_day=1,
        birth_hour=13,
        birth_minute=59,
        birth_timezone="Etc/GMT-14",
        birth_longitude=180,
        birth_latitude=0,
    )
    assert birth.utc_datetime is None
    analysis = birth.local_datetime + timedelta(minutes=elapsed_minutes)
    result = build_firdaria_for_sect(
        birth,
        "day",
        analysis_datetime=analysis,
        firdaria_year_basis="calendar_anniversary",
    )
    assert result["current_major"]["start"] == "0001-01-01T13:59:00+14:00"
    assert result["current_sub"]["end"] == "0002-06-07T07:07:34.285714+14:00"
    assert result["current_sub"]["end_display"] == "0002-06-07 07:07+14:00"


def test_calendar_anniversary_orders_extended_utc_analysis_before_birth() -> None:
    east = parse_timezone_name("Etc/GMT-14")
    birth = datetime(1, 1, 1, 14, tzinfo=east)
    target = datetime(1, 1, 1, 13, 59, tzinfo=east)
    with pytest.raises(ValueError, match="不能早于出生时刻"):
        _production(birth, "day", target, firdaria_year_basis="calendar_anniversary")


def test_calendar_anniversary_distinguishes_horizon_from_required_local_endpoint() -> (
    None
):
    west = parse_timezone_name("Etc/GMT+5")
    birth = datetime(1974, 12, 31, 23, tzinfo=west)
    boundary = datetime(9999, 12, 31, 23, tzinfo=west)
    for hour in (18, 22):
        target = boundary.replace(hour=hour, minute=59)
        result = _production(
            birth, "day", target, firdaria_year_basis="calendar_anniversary"
        )
        assert len(result["timeline"]) == 12
        assert result["current_major"]["planet"] == "South Node"
        assert result["current_major"]["end"] == "9999-12-31T23:00:00-05:00"
        assert result["current_sub"] is None
    with pytest.raises(ValueError, match="Civil calendar label is outside"):
        _production(birth, "day", boundary, firdaria_year_basis="calendar_anniversary")


@pytest.mark.parametrize("sect", ["day", "night"])
def test_production_exact_boundaries_nodes_and_75_year_restart(sect: str) -> None:
    birth = datetime(2000, 1, 1, tzinfo=UTC)
    timeline = _production(birth, sect)["timeline"]
    for major in timeline[:10]:
        start = datetime.fromisoformat(major["start"])
        selected = _production(birth, sect, start)
        assert selected["current_major"]["planet"] == major["planet"]
        subs = major["subperiods"]
        if not subs:
            assert selected["current_sub"] is None
        else:
            pass
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
def test_reference_cycle_boundaries_subdivision_and_restart(schedule: str) -> None:
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
            else:
                pass
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
        else:
            pass
        active = _production(birth, sect, start, **options)
        assert active["current_major"]["planet"] == planet
        if not major["subperiods"]:
            assert active["current_sub"] is None
        else:
            pass
        if start > birth:
            previous = _production(birth, sect, start - MICROSECOND, **options)
            assert previous["current_major"]["end"] == start.isoformat()
        else:
            pass
    assert production["timeline"][8]["nominal_end_age"] == 75
    assert (
        _production(birth, sect, periods[9][1], **options)["current_major"]["planet"]
        == periods[0][0]
    )


@pytest.mark.parametrize("sect", ["day", "night"])
@pytest.mark.parametrize("basis", ["fixed_365_2425", "calendar_anniversary"])
@pytest.mark.parametrize("night_order", ["nodes_at_end", "nodes_after_mars"])
def test_production_options_are_independent(
    sect: str, basis: str, night_order: str
) -> None:
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
    else:
        pass
    assert result["calculation_options"] == {
        "night_order": night_order,
        "year_basis": basis,
        "subperiod_basis": "utc_elapsed",
        "timezone": "UTC",
    }


@pytest.mark.parametrize("second,microsecond", [(0, 1), (34, 285714), (59, 999999)])
def test_reference_minute_display_always_truncates_without_mutating_instant(
    second: int, microsecond: int
) -> None:
    exact = datetime(2003, 3, 18, 4, 48, second, microsecond, tzinfo=UTC)
    original = exact.isoformat()
    assert _display_minute(exact, UTC) == "2003-03-18 04:48+00:00"
    assert _display_minute(exact, timezone(timedelta(hours=8))) == (
        "2003-03-18 12:48+08:00"
    )
    assert exact.isoformat() == original


@pytest.mark.parametrize("hour,sect", [(6, "day"), (0, "night")])
def test_native_horizon_sect_feeds_the_explicit_calendar_arithmetic(
    hour: int, sect: str
) -> None:
    from fatebridge.core.astro.birth import build_astro_birth_info
    from fatebridge.core.predictive._common import build_natal_subject
    from fatebridge.core.predictive.firdaria import build_firdaria_payload

    info = build_astro_birth_info(
        birth_year=2024,
        birth_month=3,
        birth_day=20,
        birth_hour=hour,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=51.5,
    )
    subject = build_natal_subject(info, house_system="W")
    assert build_firdaria_payload(
        info, subject, analysis_datetime=info.local_datetime
    ) == build_firdaria_for_sect(info, sect, analysis_datetime=info.local_datetime)


@pytest.mark.parametrize(
    "case",
    VECTORS["third_party"]["morinus_cases"],
    ids=lambda case: case["date"] + "-" + case["schedule"],
)
def test_pinned_morinus_calendar_dates_and_all_displayed_sub_lords(case) -> None:
    birth = datetime.fromisoformat(case["date"]).replace(tzinfo=UTC)
    result = _production(
        birth,
        "day" if case["schedule"] == "day" else "night",
        birth + timedelta(days=40 * 365),
        firdaria_night_order=(
            "nodes_after_mars"
            if case["schedule"] == "night_nodes_after_mars"
            else "nodes_at_end"
        ),
        firdaria_year_basis="calendar_anniversary",
    )
    for major, expected in zip(result["timeline"], case["majors"], strict=True):
        assert major["planet"] == expected["planet"]
        assert major["years"] == expected["years"]
        assert major["start"][:10] == expected["start"]
        assert (
            datetime.fromisoformat(major["end"]) - timedelta(days=1)
        ).date().isoformat() == expected["inclusive_end"]
        for sub, reference in zip(
            major["subperiods"], expected["subperiods"], strict=True
        ):
            assert sub["planet"] == reference["planet"]
            assert sub["start"][:10] == reference["start"]


@pytest.mark.parametrize(
    "case",
    VECTORS["third_party"]["temporal_cases"],
    ids=lambda case: case["schedule"] + "-" + case["basis"],
)
def test_frozen_temporal_leap_clock_boundaries_and_active_intervals(case) -> None:
    birth = datetime.fromisoformat(case["birth"]["local"]).replace(tzinfo=UTC)
    target = datetime.fromisoformat(case["target"]["local"]).replace(tzinfo=UTC)
    options = dict(
        firdaria_night_order=case["night_order"],
        firdaria_year_basis=case["basis"],
    )
    result = _production(birth, case["sect"], target, **options)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    for major, reference in zip(result["timeline"], case["timeline"], strict=True):
        assert major["planet"] == reference["planet"]
        assert major["years"] == reference["years"]
        pairs = [
            (major, reference),
            *zip(major["subperiods"], reference["subperiods"], strict=True),
        ]
        for period, expected in pairs:
            assert period["planet"] == expected["planet"]
            for field in ("start", "end"):
                boundary = datetime.fromisoformat(period[field])
                assert (
                    str((boundary - epoch) // MICROSECOND * 1000)
                    == expected[field]["instant_ns"]
                )
                assert (
                    boundary.replace(tzinfo=None).isoformat(timespec="microseconds")
                    == expected[field]["local"]
                )
                assert boundary.utcoffset() == timedelta(0)
    for probe in case["probes"]:
        instant = epoch + timedelta(microseconds=int(probe["instant_ns"]) // 1000)
        active = _production(birth, case["sect"], instant, **options)
        assert active["current_major"]["planet"] == probe["major"]
        assert (active["current_sub"] or {}).get("planet") == probe["sub"]


@pytest.mark.parametrize(
    "case",
    VECTORS["third_party"]["birchfield_tables"],
    ids=lambda case: case["schedule"],
)
def test_literal_paper_table_disagreements_with_governing_order_are_retained(
    case,
) -> None:
    birth = datetime(2000, 1, 1, tzinfo=UTC)
    result = _production(
        birth,
        "day" if case["schedule"] == "day" else "night",
        firdaria_night_order=(
            "nodes_after_mars"
            if case["schedule"] == "night_nodes_after_mars"
            else "nodes_at_end"
        ),
    )
    differences = []
    for major, literal in zip(result["timeline"][:9], case["rows"], strict=True):
        assert (major["planet"], major["years"]) == (
            literal["planet"],
            literal["years"],
        )
        for index, (sub, paper) in enumerate(
            zip(major["subperiods"], literal["subperiods"], strict=True)
        ):
            if sub["planet"] != paper:
                differences.append(
                    dict(
                        major=major["planet"],
                        sub_index=index,
                        literal_paper=paper,
                        governing_rule=sub["planet"],
                    )
                )
            else:
                pass
    assert differences == case["literal_discrepancies"]
