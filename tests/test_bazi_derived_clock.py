"""Derived uncertainty instants keep microseconds without rewriting records."""

from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.solar_time import normalize_birth_time


@pytest.mark.parametrize("solar", [False, True])
def test_rebase_keeps_a_fractional_actual_instant_on_both_sides_of_a_fold(solar):
    from fatebridge.utils.solar_time import rebase_birth_clock

    person = PersonInfo(
        birth_year=1991,
        birth_month=9,
        birth_day=15,
        birth_hour=1,
        birth_minute=59,
        birth_second=59,
        birth_timezone="Asia/Shanghai",
        birth_utc_offset="+09:00",
        birth_longitude=120,
        use_true_solar_time=solar,
    )
    template = normalize_birth_time(person)
    instant = datetime(1991, 9, 14, 17, 0, 0, 123456, tzinfo=timezone.utc)
    later = rebase_birth_clock(template, instant)
    assert later.input_datetime.astimezone(timezone.utc) == instant
    assert (
        later.input_datetime.fold == 1
        and later.input_datetime.tzinfo.key == "Asia/Shanghai"
    )
    # Compare the established normalization at exactly the same integer second.
    control = normalize_birth_time(
        person.model_copy(
            update={"birth_minute": 0, "birth_second": 0, "birth_utc_offset": "+08:00"}
        )
    )
    assert (
        later.corrected_datetime.replace(tzinfo=None)
        - control.corrected_datetime.replace(tzinfo=None)
    ).total_seconds() == pytest.approx(0.123456, abs=0.0001)
    assert (
        later.timezone == template.timezone
        and later.timezone_source == template.timezone_source
    )
    assert person.birth_utc_offset == "+09:00" and person.birth_second == 59
    assert template.input_datetime.fold == 0


def test_derived_instant_requires_a_physical_timezone_and_preserves_raw_precision():
    from fatebridge.utils.solar_time import rebase_birth_clock

    template = normalize_birth_time(
        PersonInfo(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=1,
            birth_minute=0,
            birth_second=0,
            birth_timezone="UTC",
            use_true_solar_time=False,
        )
    )
    with pytest.raises(ValueError):
        rebase_birth_clock(template, datetime(2000, 1, 1, 1))
    earlier = datetime(2000, 1, 1, 0, 59, 59, 999999, tzinfo=timezone.utc)
    later = rebase_birth_clock(template, earlier)
    assert later.corrected_datetime == earlier
    assert later.corrected_datetime.microsecond == 999999


def test_default_true_solar_fallback_does_not_acquire_a_made_up_longitude():
    from fatebridge.utils.solar_time import rebase_birth_clock

    template = normalize_birth_time(
        PersonInfo(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=1,
            birth_minute=0,
            birth_timezone="UTC",
            use_true_solar_time=True,
            true_solar_explicit=False,
        )
    )
    assert template.applied is False
    instant = datetime(2000, 1, 1, 1, 0, 0, 500000, tzinfo=timezone.utc)
    later = rebase_birth_clock(template, instant)
    assert later.applied is False and later.longitude is None
    assert later.corrected_datetime == instant
    assert later.resolution_advisory == template.resolution_advisory


def test_apparent_and_longitude_only_derived_clocks_keep_their_declared_strategy():
    from fatebridge.utils.solar_time import (
        SOLAR_TIME_STRATEGY_LONGITUDE_ONLY,
        rebase_birth_clock,
    )

    person = PersonInfo(
        birth_year=2000,
        birth_month=12,
        birth_day=10,
        birth_hour=9,
        birth_minute=55,
        birth_second=0,
        birth_timezone="Asia/Shanghai",
        birth_longitude=120.47,
        use_true_solar_time=True,
    )
    apparent = normalize_birth_time(person)
    longitude = normalize_birth_time(
        person, solar_time_strategy=SOLAR_TIME_STRATEGY_LONGITUDE_ONLY
    )
    actual = datetime(2000, 12, 10, 2, 55, 0, 654321, tzinfo=timezone.utc)
    a, b = rebase_birth_clock(apparent, actual), rebase_birth_clock(longitude, actual)
    assert a.corrected_datetime != b.corrected_datetime
    assert b.equation_of_time_minutes == 0
    assert a.solar_time_strategy == apparent.solar_time_strategy
    assert b.solar_time_strategy == SOLAR_TIME_STRATEGY_LONGITUDE_ONLY
    assert (
        a.input_datetime.astimezone(timezone.utc)
        == b.input_datetime.astimezone(timezone.utc)
        == actual
    )
