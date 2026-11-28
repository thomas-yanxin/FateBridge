"""Fractional ISO offsets must not move a casting across the late-Zi boundary."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.local_techniques.chart import (
    _build_metaphysics_seed,
    parse_local_datetime,
)
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.iso_clock import parse_iso_datetime
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
    suffix: str, microseconds
) -> None:
    moment = parse_iso_datetime("2026-11-03T23:00:00" + suffix)
    assert moment.utcoffset() == timedelta(microseconds=microseconds)
    assert moment.replace(tzinfo=None) == datetime(2026, 11, 3, 23)


@pytest.mark.parametrize(
    "clock", ["2000-01-01T00:00:00.000360", "2000-01-01+00.000360"]
)
def test_naive_fractional_clock_is_not_promoted_to_an_offset(clock: str) -> None:
    moment = parse_iso_datetime(clock)
    assert moment == datetime(2000, 1, 1, microsecond=360)
    assert moment.tzinfo is None


@pytest.mark.parametrize("clock,expected_clock,day,hour", CASES)
def test_shared_divination_parser_preserves_the_actual_offset(
    clock, expected_clock, day, hour
) -> None:
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


@pytest.mark.parametrize(
    "date,clock,zone,utc,local",
    [
        pytest.param(
            "0001-01-01",
            "00:00:00+00:00:00.000001",
            "+08:00",
            "0000-12-31T23:59:59.999999+00:00",
            "0001-01-01T07:59:59.999999+08:00",
            id="utc-year-zero",
        ),
        pytest.param(
            "9999-12-31",
            "23:59:59.9999997-00:00:00.0000003",
            "-08:00",
            "+010000-01-01T00:00:00+00:00",
            "9999-12-31T16:00:00-08:00",
            id="carry-to-utc-year-10000",
        ),
    ],
)
def test_exact_local_projection_survives_utc_datetime_range(
    date: str, clock: str, zone: str, utc: str, local: str
) -> None:
    moment = parse_local_datetime(date, clock, zone, validate_wall=True)
    assert moment.isoformat() == local
    assert utc_calendar(moment).isoformat() == utc
    with pytest.raises(
        ValidationError, match="UTC instant is outside the datetime range"
    ):
        ExecutionOptions(as_of=f"{date}T{clock}")


def test_exact_iso_offset_selects_the_second_dst_fold() -> None:
    moment = parse_local_datetime(
        "2026-11-01",
        "01:29:59.9999999-05:00:00.0000001",
        "America/New_York",
        validate_wall=True,
    )
    assert moment.fold == 1
    assert moment.isoformat() == "2026-11-01T01:30:00-05:00"
    assert moment.astimezone(timezone.utc) == datetime(
        2026, 11, 1, 6, 30, tzinfo=timezone.utc
    )


@pytest.mark.parametrize(
    "clock, utc",
    [
        ("23.5+00:15", "2026-11-03T23:15:00Z"),
        ("22:59,99999999+00:00:00.0000004", "2026-11-03T22:59:59.999999Z"),
    ],
)
def test_reduced_wall_clock_fraction_uses_the_last_time_unit(
    clock: str, utc: str
) -> None:
    assert ExecutionOptions(as_of=f"2026-11-03T{clock}").as_of == utc
    moment = parse_local_datetime("2026-11-03", clock, "UTC", validate_wall=True)
    assert moment == datetime.fromisoformat(utc.replace("Z", "+00:00"))


@pytest.mark.parametrize(
    "tool,extra",
    [
        ("liuyao", {"gua_code": "111111"}),
        ("sanshi_combined_chart", {"use_true_solar_time": False}),
    ],
)
def test_explicit_instant_requires_defined_target_local_time(
    tool: str, extra, surface_calls
) -> None:
    payload = {
        "date": "1994-06-01",
        "time": "12:34:56.123456+00:00",
        "timezone": "Antarctica/Vostok",
        **extra,
    }
    response, protocol, code, local = surface_calls(SPECS[tool], payload)
    assert response.status_code == 422 and code != 0 and protocol.is_error
    for output in (response.json(), protocol.structured_content, local):
        assert output["error_code"] == "validation_error"
        assert output["retryable"] is False
        assert output["issues"] == [
            {"path": "request", "code": "unresolved_timezone_offset"}
        ]


@pytest.mark.parametrize("key", ["liuyao", "sanshi_combined_chart"])
@pytest.mark.parametrize("clock,expected_clock,day,hour", CASES)
def test_fractional_offset_and_day_pillars_agree_across_transports(
    key: str, clock, expected_clock, day, hour, surface_calls
) -> None:
    spec = SPECS[key]
    payload = {"date": "2026-11-03", "time": clock, "timezone": "UTC"}
    if key == "liuyao":
        payload["gua_code"] = "111111"
        fields = ["nongli.solar_datetime", "nongli.day_ganzhi", "nongli.time"]
    else:
        payload["use_true_solar_time"] = False
        fields = [
            "liuren.calendar_policy.corrected_clock",
            *[
                f"subresults.{tool}.four_pillars.{pillar}"
                for tool in ("qimen", "taiyi", "liuren")
                for pillar in ("day", "hour")
            ],
        ]
    response, protocol, code, cli = surface_calls(
        spec,
        payload,
        params={"fields": fields},
        options={"fields": fields},
        flags=("--fields", *fields),
    )
    assert response.status_code == 200, response.text
    assert code == 0
    assert not protocol.is_error
    expected = business(response.json())
    assert expected == business(cli) == business(protocol.structured_content)
    wall = (
        datetime.fromisoformat(expected_clock).replace(tzinfo=None).isoformat(sep=" ")
    )
    if key == "liuyao":
        assert expected["nongli"] == {
            "solar_datetime": wall,
            "day_ganzhi": day,
            "time": hour,
        }
    else:
        assert (
            expected["liuren"]["calendar_policy"]["corrected_clock"] == expected_clock
        )
        for tool in ("qimen", "taiyi", "liuren"):
            pillars = expected["subresults"][tool]["four_pillars"]
            assert pillars["day"] == {"stem": day[0], "branch": day[1]}
            assert pillars["hour"] == {"stem": hour[0], "branch": hour[1]}
