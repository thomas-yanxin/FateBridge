"""Timing cache isolation and fractional-timezone hour regressions."""

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from fatebridge.core import almanac, timing
from fatebridge.core.almanac import (
    SolarTerm,
    elapsed_days_between,
    localize_datetime,
)
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.timing import TimingAnalysis


def _mutate_all_containers(value):
    if isinstance(value, dict):
        for child in tuple(value.values()):
            _mutate_all_containers(child)
        value.clear()
        value["caller_mutation"] = True
    elif isinstance(value, list):
        for child in value:
            _mutate_all_containers(child)
        value.clear()


@pytest.mark.parametrize("kind", ["liuyue", "liuri", "liushi"])
def test_timing_cache_results_remain_detached_after_recursive_mutation(kind):
    moment = datetime(2024, 2, 4, 23, 45)
    calls = {
        "liuyue": lambda: TimingAnalysis.calculate_liuyue(
            2024, 2, 4, target_date=moment
        ),
        "liuri": lambda: TimingAnalysis.calculate_liuri(moment),
        "liushi": lambda: TimingAnalysis.calculate_liushi(moment),
    }
    first = calls[kind]()
    original = deepcopy(first)
    _mutate_all_containers(first)
    assert calls[kind]() == original


@pytest.mark.parametrize(
    "call",
    [
        TimingAnalysis.calculate_liuyue_timeline,
        TimingAnalysis.calculate_jieqi_transition_timeline,
    ],
)
def test_timeline_mutations_do_not_pollute_cached_pillars(call):
    first = call(2024)
    original = deepcopy(first)
    _mutate_all_containers(first)
    assert call(2024) == original


@pytest.mark.parametrize(
    "moment,target_zone",
    [
        (datetime(2026, 1, 1, 1, 50, tzinfo=timezone.utc), "Asia/Kathmandu"),
        (datetime(2026, 1, 1, 17, 40, tzinfo=timezone.utc), "Asia/Kathmandu"),
        (datetime(2026, 1, 1, 1, 50, tzinfo=timezone.utc), "Asia/Kolkata"),
        (datetime(2026, 1, 2, 2, 45, tzinfo=timezone.utc), "America/St_Johns"),
    ],
)
def test_liushi_truncates_hour_after_converting_to_target_timezone(moment, target_zone):
    local = localize_datetime(moment, target_zone)
    result = TimingAnalysis.calculate_liushi(moment, target_zone)
    assert result == TimingAnalysis.calculate_liushi(local, target_zone)
    assert result == TimingAnalysis.calculate_liushi(
        local.replace(tzinfo=None), target_zone
    )
    assert result["hour"] == local.hour
    assert result["analysis_datetime"] == local.replace(
        minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%d %H:%M:%S")
    assert (result["stem"], result["branch"]) == BaZiCalendar.calculate_hour_pillar(
        local.year, local.month, local.day, local.hour
    )


@pytest.mark.parametrize(
    "start,end,zone,expected_hours",
    [
        (datetime(2026, 3, 7, 12), datetime(2026, 3, 9, 12), "America/New_York", 47),
        (datetime(2026, 10, 31, 12), datetime(2026, 11, 2, 12), "America/New_York", 49),
        (datetime(2026, 3, 7, 12), datetime(2026, 3, 9, 12), "Asia/Shanghai", 48),
    ],
)
def test_solar_durations_measure_elapsed_hours_across_dst(
    start, end, zone, expected_hours
):
    assert (
        elapsed_days_between(
            localize_datetime(start, zone), localize_datetime(end, zone)
        )
        == expected_hours / 24
    )


@pytest.mark.parametrize(
    "start,end,current,since_hours,until_hours",
    [
        (
            datetime(2026, 3, 5, 9),
            datetime(2026, 4, 5, 9),
            datetime(2026, 3, 15, 9),
            239,
            504,
        ),
        (
            datetime(2026, 10, 5, 9),
            datetime(2026, 11, 5, 9),
            datetime(2026, 11, 3, 9),
            697,
            48,
        ),
    ],
)
def test_month_context_and_dayun_use_physical_solar_intervals(
    monkeypatch, start, end, current, since_hours, until_hours
):
    zone = "America/New_York"
    start_term = SolarTerm("惊蛰", localize_datetime(start, zone), "start", "甲子")
    end_term = SolarTerm("清明", localize_datetime(end, zone), "end", "乙丑")
    boundaries = lambda *args: (start_term, end_term, "卯", 1)
    monkeypatch.setattr(almanac, "get_bazi_month_boundaries", boundaries)
    monkeypatch.setattr(timing, "get_bazi_month_boundaries", boundaries)
    context = almanac.get_bazi_month_context(current, zone)
    assert context["days_since_start"] == round(since_hours / 24, 4)
    assert context["days_until_next"] == round(until_hours / 24, 4)
    dayun = TimingAnalysis.calculate_dayun_start_details(current, "女", zone)
    assert dayun["forward_direction"] is False  # 2026 丙年女命逆行。
    assert dayun["days_to_boundary"] == round(since_hours / 24, 4)
    assert dayun["start_age_precise"] == round(since_hours / 72, 2)


def test_solar_month_elapsed_lengths_are_timezone_invariant():
    new_york = TimingAnalysis.calculate_liuyue_timeline(2026, "America/New_York")
    utc = TimingAnalysis.calculate_liuyue_timeline(2026, "UTC")
    assert [row["gregorian_window"]["days"] for row in new_york] == [
        row["gregorian_window"]["days"] for row in utc
    ]
