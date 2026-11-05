"""Fractional ISO offsets must not move a casting across the late-Zi boundary."""

import asyncio
from datetime import datetime

import pytest

from fatebridge.core.local_techniques.chart import (
    _build_metaphysics_seed,
    parse_local_datetime,
)
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

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
    key, clock, expected_clock, day, hour, rest, tmp_path, capsys
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
    response = rest.post(
        spec.rest_path,
        json=payload,
        params={"fields": fields, "strict_fields": True},
    )
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, flags=("--fields", *fields, "--strict-fields")
    )
    protocol = asyncio.run(native(spec, payload, fields=fields, strict_fields=True))
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
