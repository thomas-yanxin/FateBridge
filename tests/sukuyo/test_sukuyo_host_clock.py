"""Host-clock boundaries preserve textual halves and directed candidates."""

import asyncio
from datetime import date, timedelta
from pathlib import Path

import pytest

from fatebridge.core.sukuyo.calendar import calendar_mansion
from tests.support.transports import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest_client,
    three_surfaces,
)

BASIS = "japanese_naoj_historical_utc09"


@pytest.mark.parametrize(
    "calendar_basis,host_midnight_utc_hour",
    [("chinese_hko_utc08", 16), ("japanese_hutime_1002_1_utc09", 15)],
)
@pytest.mark.parametrize(
    "local_date,start_utc,end_utc,duration_hours",
    [
        ("2026-03-08", "2026-03-08T05:00:00+00:00", "2026-03-09T04:00:00+00:00", 23),
        ("2026-11-01", "2026-11-01T04:00:00+00:00", "2026-11-02T05:00:00+00:00", 25),
    ],
)
def test_dst_unknown_clock_preserves_both_declared_host_dates(
    calendar_basis: str,
    host_midnight_utc_hour: int,
    local_date: str,
    start_utc: str,
    end_utc: str,
    duration_hours: int,
) -> None:
    """US second-March/first-November Sundays have 23/25 hours, not a noon point."""
    result = calendar_mansion(
        local_date, zone="America/New_York", calendar_basis=calendar_basis
    )
    support = result["date_support"]
    assert support["civil_support_seconds"] == duration_hours * 3600
    assert not support["birth_time_imputed"]
    intervals = support["utc_support_intervals"]
    assert len(intervals) == 2
    assert intervals[0]["start_utc_inclusive"] == start_utc
    assert (
        intervals[0]["end_utc_exclusive"]
        == intervals[1]["start_utc_inclusive"]
        == (f"{local_date}T{host_midnight_utc_hour}:00:00+00:00")
    )
    assert intervals[1]["end_utc_exclusive"] == end_utc
    assert [branch["calendar_date"] for branch in result["calendar_candidates"]] == [
        local_date,
        (date.fromisoformat(local_date) + timedelta(days=1)).isoformat(),
    ]
    assert result["input_datetime"] is None and result["calendar_date"] is None
    assert not result["birth_time_known"]


@pytest.mark.parametrize("clock", ["00:00:00", "12:00:00", "23:59:59"])
def test_known_clock_does_not_guess_historical_textual_half(clock: str) -> None:
    """A civil clock alone cannot choose the textual half after a short month."""
    result = calendar_mansion(
        "0806-09-20",
        clock,
        "+09:00",
        calendar_basis=BASIS,
        calendar_profile="hinoo_t1299_host27",
    )
    assert result["calendar_date"] == "0806-09-20"
    assert result["birth_time_known"] and result["calendar_day_part"] is None
    assert result["candidate_su27s"] == ["轸", "角"]
    assert result["natal_su27"] is None
    assert result["resolution_reason"] == "hinoo_short_month_day_part_unresolved"


@pytest.mark.parametrize(
    "tool_name,reverse",
    [
        ("suzhan", False),
        ("sukuyo_compatibility", False),
        ("sukuyo_compatibility", True),
    ],
)
def test_historical_half_candidates_and_directed_relations_across_three_surfaces(
    tool_name: str,
    reverse: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    if tool_name == "suzhan":
        payload = {"date": "0806-09-20", "timezone": "+09:00"}
        fields = ["sukuyo.calendar", "validation"]
    else:
        payload = {
            "person1_date": "0806-09-21" if reverse else "0806-09-20",
            "person1_zone": "+09:00",
            "person2_date": "0806-09-20" if reverse else "0806-09-21",
            "person2_zone": "+09:00",
        }
        fields = [
            "person1",
            "person2",
            "pair",
            "person1_to_person2",
            "person2_to_person1",
            "candidate_relation_analysis",
        ]
    payload.update(calendar_basis=BASIS, calendar_profile="hinoo_t1299_host27")
    spec = SPECS[tool_name]
    response = rest_client(monkeypatch).post(
        spec.rest_path, json=payload, params={"as_of": AS_OF, "include": "*"}
    )
    protocol = asyncio.run(native(spec, payload, include=["*"]))
    exit_code, cli = call_cli(spec, payload, tmp_path, capsys, flags=["--include", "*"])
    assert response.status_code == 200 and exit_code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(protocol.structured_content)
        == business(cli)
    )
    result = three_surfaces(spec, payload, fields, AS_OF, tmp_path, monkeypatch, capsys)
    if tool_name == "suzhan":
        assert result["sukuyo"]["calendar"]["candidate_su27s"] == ["轸", "角"]
        assert result["sukuyo"]["calendar"]["natal_su27"] is None
    else:
        assert (
            result["pair"]
            is result["person1_to_person2"]
            is result["person2_to_person1"]
            is None
        )
        rows = result["candidate_relation_analysis"]["rows"]
        assert len(rows) == 2 and all(not row["applied_to_primary"] for row in rows)
        assert [
            (
                row["person1_to_person2"]["relation"],
                row["person2_to_person1"]["relation"],
            )
            for row in rows
        ] == ([("友", "衰"), ("親", "栄")] if reverse else [("衰", "友"), ("栄", "親")])
        assert [
            (row["person1_to_person2"]["offset"], row["person2_to_person1"]["offset"])
            for row in rows
        ] == ([(25, 2), (26, 1)] if reverse else [(2, 25), (1, 26)])


def test_host_midnight_selects_leap_month_without_replacing_unknown_clock() -> None:
    """The same UTC instant crosses Japan's midnight an hour before China's."""
    china = calendar_mansion("2023-03-21", "15:30:00", "UTC")
    japan = calendar_mansion(
        "2023-03-21",
        "15:30:00",
        "UTC",
        calendar_basis="japanese_hutime_1002_1_utc09",
    )
    unknown = calendar_mansion(
        "2023-03-21",
        zone="+08:00",
        calendar_basis="japanese_hutime_1002_1_utc09",
    )
    assert china["calendar_date"] == "2023-03-21" and not china["is_leap_month"]
    assert japan["calendar_date"] == "2023-03-22" and japan["is_leap_month"]
    assert japan["natal_su27"] is None
    assert japan["resolution_reason"] == "leap_month_policy_unresolved"
    assert [
        (branch["calendar_date"], branch["is_leap_month"])
        for branch in unknown["calendar_candidates"]
    ] == [("2023-03-21", False), ("2023-03-22", True)]
    assert unknown["input_datetime"] is None and unknown["natal_su27"] is None


@pytest.mark.parametrize("tool_name", ["suzhan", "sukuyo_compatibility"])
@pytest.mark.parametrize(
    "calendar_basis,host_midnight_utc_hour",
    [("chinese_hko_utc08", 16), ("japanese_hutime_1002_1_utc09", 15)],
)
def test_unknown_leap_boundary_date_candidates_across_three_surfaces(
    tool_name: str,
    calendar_basis: str,
    host_midnight_utc_hour: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    if tool_name == "suzhan":
        payload = {"date": "2023-03-21", "timezone": "UTC"}
        fields = ["sukuyo.calendar"]
    else:
        payload = {
            "person1_date": "2023-03-21",
            "person1_zone": "UTC",
            "person2_date": "2023-03-23",
            "person2_zone": "+09:00" if host_midnight_utc_hour == 15 else "+08:00",
        }
        fields = ["person1", "candidate_relation_analysis", "pair"]
    payload["calendar_basis"] = calendar_basis
    result = three_surfaces(
        SPECS[tool_name], payload, fields, AS_OF, tmp_path, monkeypatch, capsys
    )
    calendar = (
        result["sukuyo"]["calendar"]
        if tool_name == "suzhan"
        else result["person1"]["calendar"]
    )
    assert [
        (branch["calendar_date"], branch["is_leap_month"])
        for branch in calendar["calendar_candidates"]
    ] == [("2023-03-21", False), ("2023-03-22", True)]
    assert calendar["input_datetime"] is None and not calendar["birth_time_known"]
    assert calendar["natal_su27"] is None
    assert (
        calendar["date_support"]["utc_support_intervals"][0]["end_utc_exclusive"]
        == f"2023-03-21T{host_midnight_utc_hour}:00:00+00:00"
    )
    if tool_name == "sukuyo_compatibility":
        assert result["pair"] is None
        rows = result["candidate_relation_analysis"]["rows"]
        assert len(rows) == 2
        assert all(not row["applied_to_primary"] for row in rows)
    else:
        pass


@pytest.mark.parametrize(
    "local_date,clock", [("2026-03-08", "02:30:00"), ("2026-11-01", "01:30:00")]
)
def test_dst_invalid_clock_fails_on_all_public_surfaces(
    local_date: str,
    clock: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spec = SPECS["sukuyo_compatibility"]
    payload = {
        "person1_date": local_date,
        "person1_time": clock,
        "person1_zone": "America/New_York",
        "person2_date": "2026-03-09",
        "calendar_basis": "japanese_hutime_1002_1_utc09",
    }
    response = rest_client(monkeypatch).post(
        spec.rest_path, json=payload, params={"as_of": AS_OF}
    )
    protocol = asyncio.run(native(spec, payload))
    exit_code, cli = call_cli(spec, payload, tmp_path, capsys)
    assert response.status_code == 400 and protocol.is_error and exit_code != 0
    assert cli["error_code"] == "validation_error"
    reason = "nonexistent local time" if clock == "02:30:00" else "ambiguous local time"
    assert (
        reason in response.text
        and reason in str(protocol.content)
        and reason in cli["error"]
    )


def test_known_clock_without_coordinates_stays_calendar_only() -> None:
    from fatebridge.core.local_techniques.suzhan import build_suzhan_result
    from fatebridge.core.sukuyo.suzhan_clock_input import require_clock_input_binding

    result = build_suzhan_result(date="2025-01-28", time="16:00:00", timezone="UTC")
    require_clock_input_binding(result)
    assert result["sukuyo"]["calendar"]["calendar_date"] == "2025-01-29"
    assert result["params"]["calculationMode"] == "calendar_with_clock"
    assert result["chart"] is result["astronomy"] is None
    assert (
        result["validation"]["calculation_layers"]["chart"]
        == "not_computed_missing_coordinates"
    )
    for chart_options in ({"chart_requested": True}, {"latitude": 0}):
        with pytest.raises(ValueError, match="完整经纬度"):
            build_suzhan_result(
                date="2025-01-28", time="16:00:00", timezone="UTC", **chart_options
            )
