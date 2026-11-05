"""Canonical fixed-offset labels must preserve already-supported exact seconds."""

from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.civil_clock import format_utc_offset
from fatebridge.utils.solar_time import normalize_birth_time
from fatebridge.utils.timezones import parse_timezone_name

OFFSETS = [
    ("UTC+00:19:32", 1172),
    ("+05:21:10", 19270),
    ("GMT-00:44:30", -2670),
    ("-00:43:08", -2588),
]


@pytest.mark.parametrize("label,seconds", OFFSETS)
def test_canonical_seconds_label_round_trips_exact_fixed_clock(label, seconds):
    zone = parse_timezone_name(label)
    offset = timedelta(seconds=seconds)
    assert zone.utcoffset(None) == offset
    assert parse_timezone_name(format_utc_offset(offset)).utcoffset(None) == offset
    local = datetime(1965, 8, 26, 19, 34, 8, tzinfo=zone)
    assert (
        local.astimezone(timezone.utc)
        == datetime(1965, 8, 26, 19, 34, 8, tzinfo=timezone.utc) - offset
    )


@pytest.mark.parametrize("second", [None, 0, 32])
@pytest.mark.parametrize("label,seconds", [OFFSETS[0], OFFSETS[2]])
def test_canonical_birth_clock_equals_existing_decimal_fixed_clock_without_inventing_seconds(
    label, seconds, second
):
    common = dict(
        birth_year=1965,
        birth_month=8,
        birth_day=26,
        birth_hour=19,
        birth_minute=34,
        birth_second=second,
        gender="男",
        use_true_solar_time=False,
    )
    person = PersonInfo(**common, birth_timezone=label)
    original = person.model_dump()
    canonical = normalize_birth_time(person)
    decimal = normalize_birth_time(
        PersonInfo(**common, birth_timezone=f"{seconds / 3600:.15f}")
    )
    assert canonical.input_datetime == decimal.input_datetime
    assert canonical.corrected_datetime == decimal.corrected_datetime
    assert person.model_dump() == original
    assert person.birth_second is second

    def pillars(clock):
        return BaZiCalendar.get_four_pillars(
            clock.corrected_datetime,
            timezone_name=clock.timezone,
            civil_datetime=clock.input_datetime,
        )

    assert pillars(canonical) == pillars(decimal)
    timelines = [
        TimingAnalysis.calculate_dayun_timeline(
            clock.input_datetime, "男", pillars(clock)["month"], clock.timezone
        )
        for clock in [canonical, decimal]
    ]
    assert datetime.fromisoformat(timelines[0]["start_at"]) == datetime.fromisoformat(
        timelines[1]["start_at"]
    )
    assert timelines[0]["calendar_offset"] == timelines[1]["calendar_offset"]


@pytest.mark.parametrize(
    "label",
    [
        "UTC+15:00:01",
        "+00:60:00",
        "+00:00:60",
        "+16:00:00",
        "UTC+8:9:32",
        "819:32",
        "0500:30",
    ],
)
def test_invalid_seconds_offsets_do_not_bypass_existing_bounds(label):
    with pytest.raises(ValueError):
        parse_timezone_name(label)
