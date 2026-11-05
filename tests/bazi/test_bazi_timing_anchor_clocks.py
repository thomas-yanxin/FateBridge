"""Replay anchors must obey public local-clock validation, not only formatting."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import fatebridge.core.timing as timing
from fatebridge.core.almanac import SolarTerm
from fatebridge.core.timing import TimingAnalysis
from fatebridge.utils.timezones import parse_timezone_name, validate_local_clock
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

rest = _shared_rest


@pytest.mark.parametrize(
    "zone,wall,expected",
    [
        ("America/New_York", "2025-03-09 01:59:30", "2025-03-09T03:00:00-04:00"),
        ("America/New_York", "2025-11-02 00:59:30", "2025-11-02T02:00:00-05:00"),
        ("Asia/Shanghai", "1900-12-31 23:59:30", "1901-01-01T00:00:00+08:00"),
    ],
)
def test_anchor_skips_unrepresentable_gap_repeat_and_historical_clock(
    zone, wall, expected
):
    moment = datetime.fromisoformat(wall).replace(tzinfo=parse_timezone_name(zone))
    anchor = TimingAnalysis._next_supported_analysis_anchor(moment, zone)
    assert anchor.isoformat() == expected
    validate_local_clock(anchor)
    assert anchor.second == 0 and anchor.microsecond == 0
    assert anchor.astimezone(timezone.utc) > moment.astimezone(timezone.utc)
    # The previous whole local minute is either before the event or cannot be
    # sent through the public IANA/minute contract without ambiguity.
    previous = anchor - timedelta(minutes=1)
    if previous.astimezone(timezone.utc) > moment.astimezone(timezone.utc):
        with pytest.raises(ValueError):
            validate_local_clock(previous)


def test_exact_term_minute_keeps_the_documented_strictly_after_policy():
    moment = datetime(2028, 4, 4, 14, 4, tzinfo=timezone(timedelta(hours=8)))
    anchor = TimingAnalysis._next_supported_analysis_anchor(moment, "+08:00")
    assert anchor == moment + timedelta(minutes=1)


def test_repeated_hour_anchor_never_replays_before_its_source_instant():
    zone = parse_timezone_name("America/New_York")
    # A fully specified UTC instant is the second 01:30 local occurrence.
    moment = datetime(2025, 11, 2, 6, 30, 30, tzinfo=timezone.utc).astimezone(zone)
    assert moment.fold == 1
    anchor = TimingAnalysis._next_supported_analysis_anchor(moment, "America/New_York")
    assert anchor.isoformat() == "2025-11-02T02:00:00-05:00"
    assert anchor.astimezone(timezone.utc) > moment.astimezone(timezone.utc)


def test_timeline_window_does_not_floor_a_fractional_computed_boundary(monkeypatch):
    zone = parse_timezone_name("Asia/Shanghai")
    first = datetime(2028, 1, 6, 3, 54, 38, 700247, tzinfo=zone)
    second = datetime(2028, 2, 4, 15, 30, 0, 123456, tzinfo=zone)
    terms = [
        SolarTerm("小寒", first, "20280106", day_ganzhi=""),
        SolarTerm("立春", second, "20280204", day_ganzhi=""),
    ]

    def source(year, timezone_name):
        return (
            terms
            if year == 2028
            else [
                SolarTerm(
                    "小寒",
                    datetime(2029, 1, 5, 1, tzinfo=zone),
                    "20290105",
                    day_ganzhi="",
                )
            ]
        )

    monkeypatch.setattr(timing, "get_solar_terms_for_year", source)
    # This synthetic event tests serialization, not a claimed astronomical
    # reference or an accuracy score for its manually assigned date. Isolate
    # the provider check instead of labelling manually assigned terms Swiss.
    monkeypatch.setattr(timing, "require_calculated_solar_term", lambda term: None)
    result = TimingAnalysis.calculate_liuyue_timeline(2028)
    window = result[0]["gregorian_window"]
    assert datetime.fromisoformat(window["start"]) == first.replace(tzinfo=None)
    assert datetime.fromisoformat(window["end"]) == second.replace(tzinfo=None)
    assert window["start"] == result[0]["start_term"]["datetime"]


def test_actual_provider_lidong_replays_new_month_on_rest_native_mcp_and_cli(
    rest, tmp_path, capsys
):
    # Under the pinned IANA rules and the configured provider, the 2083
    # Halifax 立冬 lies in the second 01:xx occurrence. This is an integration
    # regression against the provider, not an independent future observation.
    spec = SPECS["jieqi_timeline_analysis"]
    args = {
        "birth_year": 1990,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_minute": 30,
        "gender": "男",
        "birth_timezone": "America/Halifax",
        "use_true_solar_time": False,
        "target_year": 2083,
    }
    response = rest.post(spec.rest_path, json=args)
    protocol = asyncio.run(native(spec, args))
    code, local = call_cli(
        spec, args, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    item = next(r for r in outputs[0]["jieqi_timeline"] if r["jieqi"]["name"] == "立冬")
    anchor = datetime.fromisoformat(item["analysis_anchor"]).replace(
        tzinfo=parse_timezone_name("America/Halifax")
    )
    validate_local_clock(anchor)
    assert anchor.hour == 2 and anchor.minute == 0
    assert item["liuyue"]["branch"] == "亥"
