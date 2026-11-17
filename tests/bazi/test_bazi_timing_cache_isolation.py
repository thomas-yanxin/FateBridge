"""Caller mutation cannot change cached metadata or any numeric calculation."""

from copy import deepcopy
from datetime import datetime

import pytest

from fatebridge.core.timing import TimingAnalysis, _copy_timing_info


def mutable_ids(value):
    found = set()
    if isinstance(value, dict):
        found.add(id(value))
        for v in value.values():
            found.update(mutable_ids(v))
    elif isinstance(value, (list, tuple)):
        if isinstance(value, list):
            found.add(id(value))
        for v in value:
            found.update(mutable_ids(v))
    return found


@pytest.mark.parametrize(
    "nested",
    [
        {"solver": {"precision": {"verified": False}}},
        {"retflags": [1, 2, 4]},
        {"solver": [{"samples": [1.25, 2.5]}, {"versions": ["v1"]}]},
        {"tuple": ({"a": [1, {"b": 2}]},)},
    ],
)
def test_each_return_and_cache_own_every_nested_mutable_container(nested):
    source = {
        "pillar": "甲子",
        "solar_term_window": {
            "start_term": {"solar_model_details": nested},
            "next_term": {"solar_model_details": deepcopy(nested)},
            "days_since_start": 1.25,
        },
    }
    expected = deepcopy(source)
    first, second = _copy_timing_info(source), _copy_timing_info(source)
    assert first == second == expected
    assert not mutable_ids(source) & mutable_ids(first)
    assert not mutable_ids(source) & mutable_ids(second)
    assert not mutable_ids(first) & mutable_ids(second)
    first["solar_term_window"]["start_term"]["solar_model_details"].clear()
    assert source == second == expected


def test_no_window_scalar_cache_payload_is_also_a_new_caller_owned_dictionary():
    source = {"pillar": "甲子", "hour": 3}
    first, second = _copy_timing_info(source), _copy_timing_info(source)
    first.clear()
    assert source == second == {"pillar": "甲子", "hour": 3}


@pytest.mark.parametrize(
    "zone,utc,wall,pillar",
    [
        (
            "America/Goose_Bay",
            "1988-04-03T04:01:00+00:00",
            "1988-04-03 02:01:00",
            "癸丑",
        ),
        ("Pacific/Chatham", "2024-09-28T14:05:00+00:00", "2024-09-29 03:50:00", "庚寅"),
        (
            "Australia/Lord_Howe",
            "2024-10-05T15:35:00+00:00",
            "2024-10-06 02:35:00",
            "癸丑",
        ),
        ("Asia/Kathmandu", "1985-12-31T18:40:00+00:00", "1986-01-01 00:25:00", "丙子"),
    ],
)
def test_liushi_retains_actual_clock_after_nonexistent_nominal_hour(
    zone, utc, wall, pillar
):
    # Frozen native C TZif projection and lunar-python 1645ad3 (23:00 rollover).
    # The valid query's xx:00 label is inside a timezone gap in each case.
    result = TimingAnalysis.calculate_liushi(datetime.fromisoformat(utc), zone)
    expected = datetime.fromisoformat(wall)
    assert [result[key] for key in ("year", "month", "day", "hour")] == [
        expected.year,
        expected.month,
        expected.day,
        expected.hour,
    ]
    assert result["analysis_datetime"] == wall
    assert result["pillar"] == pillar


def test_same_hour_queries_share_pillar_without_sharing_query_timestamp():
    first = TimingAnalysis.calculate_liushi(
        datetime.fromisoformat("2024-09-28T14:05:00+00:00"), "Pacific/Chatham"
    )
    second = TimingAnalysis.calculate_liushi(
        datetime.fromisoformat("2024-09-28T14:12:23+00:00"), "Pacific/Chatham"
    )
    assert first["pillar"] == second["pillar"] == "庚寅"
    assert first["analysis_datetime"] == "2024-09-29 03:50:00"
    assert second["analysis_datetime"] == "2024-09-29 03:57:23"
