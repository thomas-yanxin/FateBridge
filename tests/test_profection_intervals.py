"""Profection boundaries retain elapsed-time partitions and original birthdays."""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from fatebridge.core.predictive.profections import (
    monthly_profection_index,
    monthly_profection_segment,
)
from fatebridge.utils.timezones import parse_timezone_name
from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest


@pytest.mark.parametrize("zone", ["UTC", "America/New_York", "Australia/Lord_Howe"])
def test_month_segments_partition_elapsed_time_across_offset_changes(zone):
    tz = parse_timezone_name(zone)
    start = datetime(2023, 3, 1, 12, tzinfo=tz)
    end = datetime(2024, 3, 1, 12, tzinfo=tz)
    utc_start, utc_end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    previous_end = utc_start
    for index in range(12):
        left, right = monthly_profection_segment(start, end, index)
        left, right = left.astimezone(timezone.utc), right.astimezone(timezone.utc)
        assert left == previous_end
        assert left == utc_start + (utc_end - utc_start) * index / 12
        assert right == utc_start + (utc_end - utc_start) * (index + 1) / 12
        assert monthly_profection_index(start, end, left) == index
        assert (
            monthly_profection_index(start, end, right - timedelta(microseconds=1))
            == index
        )
        previous_end = right
    assert previous_end == utc_end


def test_index_uses_the_same_representable_boundaries_as_the_timeline():
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=365, microseconds=5)
    for index in range(1, 12):
        boundary, _ = monthly_profection_segment(start, end, index)
        assert monthly_profection_index(start, end, boundary) == index
        assert (
            monthly_profection_index(start, end, boundary - timedelta(microseconds=1))
            == index - 1
        )


@pytest.mark.parametrize(
    "analysis_year,analysis_day,expected_start,expected_end",
    [
        (2024, 28, "2023-02-28", "2024-02-29"),
        (2024, 29, "2024-02-29", "2025-02-28"),
        (2025, 28, "2025-02-28", "2026-02-28"),
    ],
)
@pytest.mark.parametrize("return_timezone", ["UTC", "America/New_York"])
def test_leap_birth_year_and_active_month_agree_on_all_transports(
    rest,
    tmp_path,
    capsys,
    analysis_year,
    analysis_day,
    expected_start,
    expected_end,
    return_timezone,
):
    spec = SPECS["givenyear"]
    payload = {
        "name": "Leap boundary reference",
        "birth_year": 2000,
        "birth_month": 2,
        "birth_day": 29,
        "birth_hour": 10,
        "birth_minute": 30,
        "birth_place": "Greenwich",
        "birth_timezone": "UTC",
        "birth_longitude": 0,
        "birth_latitude": 0,
        "analysis_year": analysis_year,
        "analysis_month": 2,
        "analysis_day": analysis_day,
        "return_timezone": return_timezone,
    }
    fields = [
        "givenyear.year_start",
        "givenyear.year_end",
        "givenyear.monthly_profections",
        "givenyear.annual_profection",
        "givenyear.analysis_datetime",
    ]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", field) for field in fields],
    )
    code, local = call_cli(spec, payload, tmp_path, capsys, ["--fields", *fields])
    protocol = asyncio.run(native(spec, payload, fields=fields))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert json.loads(protocol.content[0].text) == protocol.structured_content
    outputs = [response.json(), local, protocol.structured_content]
    results = [output["givenyear"] for output in outputs]
    assert results[0] == results[1] == results[2]
    result = results[0]
    zone = parse_timezone_name(return_timezone)
    expected_start = datetime.fromisoformat(expected_start + "T10:30:00+00:00")
    expected_end = datetime.fromisoformat(expected_end + "T10:30:00+00:00")
    assert result["year_start"] == expected_start.astimezone(zone).isoformat()
    assert result["year_end"] == expected_end.astimezone(zone).isoformat()
    target = datetime(analysis_year, 2, analysis_day, 10, 30, tzinfo=timezone.utc)
    assert datetime.fromisoformat(result["analysis_datetime"]) == target
    months = result["monthly_profections"]
    assert months[0]["start"] == result["year_start"]
    assert months[-1]["end"] == result["year_end"]
    for row in months:
        duration = datetime.fromisoformat(row["end"]) - datetime.fromisoformat(
            row["start"]
        )
        assert abs(duration - (expected_end - expected_start) / 12) <= timedelta(
            microseconds=1
        )
    active = [row for row in months if row["active"]]
    assert len(active) == 1
    assert active[0]["house"] == result["annual_profection"]["monthly_house"]
