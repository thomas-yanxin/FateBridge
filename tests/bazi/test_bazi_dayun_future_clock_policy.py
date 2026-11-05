"""Calendar inverse properties and actual loaded-zone cache identity."""

from calendar import isleap
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from fatebridge.core.timing import DEFAULT_DAYUN_PERIODS, TimingAnalysis
from fatebridge.utils.clock_events import forward_clock_gaps_near_day


def test_decade_inverse_retains_every_leap_clipped_source_and_no_false_source():
    # Check a full Gregorian400-year cycle, all configured boundary indices,
    # and both sides of February clipping against the actual year operator.
    for year in range(1900, 2300):
        days = [(2, 27), (2, 28), (3, 1)] + ([(2, 29)] if isleap(year) else [])
        for month, day in days:
            original = datetime(year, month, day, 2, 59, 59, 123456)
            for index in range(DEFAULT_DAYUN_PERIODS + 1):
                offset = index * 10
                boundary = original + relativedelta(years=offset)
                sources = TimingAnalysis._dayun_wall_year_preimages(boundary, offset)
                assert original in sources
                assert all(s + relativedelta(years=offset) == boundary for s in sources)


def test_future_clock_cache_uses_loaded_data_object_even_when_zone_names_match():
    compiled = Path(__file__).parents[1] / "data/bazi_birth_fold_v1/compiled"
    with (compiled / "America/New_York").open("rb") as stream:
        new_york = ZoneInfo.from_file(stream, key="same-test-name")
    with (compiled / "Australia/Lord_Howe").open("rb") as stream:
        lord_howe = ZoneInfo.from_file(stream, key="same-test-name")
    day = date(2020, 3, 8)
    ny_gaps = forward_clock_gaps_near_day(new_york, day)
    assert len(ny_gaps) == 1
    assert ny_gaps[0].instant_utc == datetime(2020, 3, 8, 7, tzinfo=timezone.utc)
    assert ny_gaps[0].offset_after_seconds - ny_gaps[0].offset_before_seconds == 3600
    assert forward_clock_gaps_near_day(lord_howe, day) == ()
    assert forward_clock_gaps_near_day(new_york, day) is ny_gaps


def test_fixed_offset_clock_has_no_forward_gap():
    assert forward_clock_gaps_near_day(timezone.utc, date(2020, 3, 8)) == ()
