"""Fractional ISO offsets must not move a casting across the late-Zi boundary."""

from datetime import datetime, timedelta

import pytest

from fatebridge.core.local_techniques.chart import (
    _build_metaphysics_seed,
    parse_local_datetime,
)
from fatebridge.utils.civil_clock import parse_iso_datetime
from tests.support.transports import SPECS, business, rest, surface_calls

CASES = [
    (
        "23:00:00+00:00:00.5",
        "2026-11-03T22:59:59.500000+00:00",
        "辛巳",
        "己亥",
    ),
    (
        "22:59:59.750000-00:00:00.5",
        "2026-11-03T23:00:00.250000+00:00",
        "壬午",
        "庚子",
    ),
]


@pytest.mark.parametrize(
    "suffix,microseconds",
    [
        ("+00:00:00.5", 500000),
        ("-00:00:00.5", -500000),
        ("+00:00:00.000001", 1),
        ("+00:00:00.1234567", 123456),
        ("+00:00:00.0", 0),
    ],
)
def test_fractional_zero_offsets_keep_microseconds_on_supported_python_versions(
    suffix, microseconds
):
    moment = parse_iso_datetime("2026-11-03T23:00:00" + suffix)
    assert moment.utcoffset() == timedelta(microseconds=microseconds)
    assert moment.replace(tzinfo=None) == datetime(2026, 11, 3, 23)


@pytest.mark.parametrize(
    "clock", ["2000-01-01T00:00:00.000360", "2000-01-01+00.000360"]
)
def test_naive_fractional_clock_is_not_promoted_to_an_offset(clock):
    moment = parse_iso_datetime(clock)
    assert moment == datetime(2000, 1, 1, microsecond=360)
    assert moment.tzinfo is None


@pytest.mark.parametrize("clock,expected_clock,day,hour", CASES)
def test_shared_divination_parser_preserves_the_actual_offset(
    clock, expected_clock, day, hour
):
    expected = datetime.fromisoformat(expected_clock)
    assert parse_local_datetime("2026-11-03", clock, "UTC") == expected
    seed = _build_metaphysics_seed(
        date_text="2026-11-03",
        time_text=clock,
        timezone_name="UTC",
        use_true_solar_time=False,
    )
    assert seed.input_datetime == expected
    assert "".join(seed.pillars["day"]) == day
    assert "".join(seed.pillars["hour"]) == hour


@pytest.mark.parametrize("key", ["sixyao", "sanshiunited"])
@pytest.mark.parametrize("clock,expected_clock,day,hour", CASES)
def test_fractional_offset_and_day_pillars_agree_across_transports(
    key, clock, expected_clock, day, hour, surface_calls
):
    spec = SPECS[key]
    payload = {"date": "2026-11-03", "time": clock, "zone": "UTC"}
    if key == "sixyao":
        payload["gua_code"] = "111111"
        fields = ["nongli.birth", "nongli.dayGanZi", "nongli.time"]
    else:
        payload["use_true_solar_time"] = False
        fields = [
            "sources.calendar_context.solar_datetime",
            *[
                f"subresults.{tool}.four_pillars.{pillar}"
                for tool in ("qimen", "taiyi", "liureng_gods")
                for pillar in ("day", "hour")
            ],
        ]
    response, protocol, code, cli = surface_calls(
        spec,
        payload,
        params={"fields": fields, "strict_fields": True},
        options={"fields": fields, "strict_fields": True},
        flags=("--fields", *fields, "--strict-fields"),
    )
    assert response.status_code == 200, response.text
    assert code == 0
    assert not protocol.is_error
    expected = business(response.json())
    assert expected == business(cli) == business(protocol.structured_content)
    wall = (
        datetime.fromisoformat(expected_clock).replace(tzinfo=None).isoformat(sep=" ")
    )
    if key == "sixyao":
        assert expected["nongli"] == {"birth": wall, "dayGanZi": day, "time": hour}
    else:
        assert expected["sources"]["calendar_context"]["solar_datetime"] == wall
        for tool in ("qimen", "taiyi", "liureng_gods"):
            pillars = expected["subresults"][tool]["four_pillars"]
            assert pillars["day"] == {"stem": day[0], "branch": day[1]}
            assert pillars["hour"] == {"stem": hour[0], "branch": hour[1]}
