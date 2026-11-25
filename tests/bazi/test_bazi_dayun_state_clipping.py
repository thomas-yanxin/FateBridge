"""Frozen lost-state witnesses, decade clipping and fold-end inverse controls."""

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import fatebridge.services.dayun_birth_events as events
from fatebridge.core.contracts.output_timing import DayunBirthEventAnalysis
from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.timing_snapshots import _birth_range_snapshot_lines
from fatebridge.services.timing_uncertainty import analyze_birth_time_range
from fatebridge.utils.birth_input import PersonInfo
from tests.unit_test.fixtures.dayun_future_gap_reference import (
    INITIAL_BOUNDARY_CONTROLS,
)

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "tests/data/bazi/dayun-clipping"


def frozen(name):
    path = STUDY / name
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(gzip.decompress(path.read_bytes()))


DATA = frozen("reference-first.json.gz")
FOLDS = frozen("fold-reference-first.json.gz")
SELECTED = []
for zone in (
    "UTC",
    "America/New_York",
    "Australia/Lord_Howe",
    "Pacific/Apia",
    "Europe/Amsterdam",
):
    SELECTED.append(
        next(
            r
            for r in DATA["rows"]
            if r["zone"] == zone and r.get("missing_from_minute_grid")
        )
    )
    SELECTED.append(
        next(
            r
            for r in DATA["rows"]
            if r["zone"] == zone
            and r["status"] == "resolved_source_control"
            and not r["clipped"]
        )
    )
for zone in (
    "America/New_York",
    "Australia/Lord_Howe",
    "Pacific/Apia",
    "Europe/Amsterdam",
):
    SELECTED.append(
        next(
            r
            for r in FOLDS["rows"]
            if r["zone"] == zone and r["status"] == "resolved_source_control"
        )
    )


@pytest.mark.parametrize("row", SELECTED, ids=lambda r: r["id"])
def test_frozen_witness_states_and_matching_event_are_retained(row) -> None:
    person = PersonInfo(**row["input"])
    before = person.model_dump()
    result = analyze_birth_time_range(
        person, 1, analysis_moment=datetime.fromisoformat(row["analysis_at"])
    )
    states = {(r["status"], r["period"]) for r in result["current_dayun_candidates"]}
    assert set(map(tuple, row["source_witness_states"])) <= states
    event = result["dayun_event_analysis"]
    DayunBirthEventAnalysis.model_validate(event)
    assert event["method_id"] == "dayun_all_boundary_gap_and_analysis_probes_v4"
    assert (
        event["continuous_completeness_certified"]
        is event["physical_precision_certified"]
        is False
    )
    kind = row.get(
        "expected_event_kind",
        "dayun_decade_leap_clip" if row["clipped"] else "dayun_analysis_moment",
    )
    events = [
        r
        for r in event["events"]
        if r["kind"] == kind
        and r["source"]["decade_boundary_index"] == str(row["boundary_index"])
    ]
    assert events
    if kind != "dayun_analysis_moment":
        expected = datetime.fromisoformat(row["inverse_ceil_utc"])
        assert any(
            abs((datetime.fromisoformat(r["at_utc"]) - expected).total_seconds()) <= 0.1
            for r in events
        )
    else:
        pass
    assert result["sample_count"] == 3
    assert person.model_dump() == before


def test_full_gregorian_cycle_matches_the_independent_calendar_projection() -> None:
    for row in DATA["calendar_cycle_rows"]:
        wall = datetime(row["year"], 2, 29)
        birth = datetime(1880, 1, 1, tzinfo=timezone.utc)
        result, adjusted = TimingAnalysis._resolve_dayun_calendar_boundary(
            birth, wall, row["boundary_index"] * 10, "UTC"
        )
        assert result.date().isoformat() == row["projected_date"]
        assert adjusted is False
    assert len(DATA["calendar_cycle_rows"]) == 1261


def test_source_full_scope_retains_all_unknowns_and_negative_controls() -> None:
    assert len(DATA["rows"]) == 11986 and len(FOLDS["rows"]) == 22649
    assert DATA["counts"] == {
        "resolved_source_control": 6981,
        "unresolved_source_interaction": 5005,
    }
    assert FOLDS["counts"] == {
        "resolved_source_control": 14714,
        "unresolved_source_interaction": 7935,
    }
    assert sum(bool(r.get("missing_from_minute_grid")) for r in DATA["rows"]) == 3225
    assert any(
        r["status"] == "resolved_source_control" and not r["clipped"]
        for r in DATA["rows"]
    )


def test_analysis_bracket_does_not_split_a_valid_future_gap_inverse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    row = INITIAL_BOUNDARY_CONTROLS[0]
    person = PersonInfo(**row["input"])
    analysis = datetime.fromisoformat(row["analysis_at"])
    first = analyze_birth_time_range(person, 1, analysis_moment=analysis)
    gap = next(
        e
        for e in first["dayun_event_analysis"]["events"]
        if e["kind"] == "dayun_future_civil_gap_end"
    )
    assert gap["lower_utc"] != gap["upper_utc"]
    injected = {**gap, "kind": "dayun_analysis_moment"}
    monkeypatch.setattr(
        events,
        "collect_dayun_analysis_events",
        lambda *args, **kwargs: ([injected], []),
    )
    result = analyze_birth_time_range(person, 1, analysis_moment=analysis)
    assert any(
        e["kind"] == "dayun_future_civil_gap_end"
        and e["lower_utc"] == gap["lower_utc"]
        and e["upper_utc"] == gap["upper_utc"]
        for e in result["dayun_event_analysis"]["events"]
    )


@pytest.mark.parametrize(
    "minutes,analysis_at,expected",
    [
        (
            0,
            "1993-02-24T04:47:06.968635+00:00",
            ("1984-08-01T15:00:00+00:00", "1984-08-01T15:00:00+00:00"),
        ),
        (
            1,
            "1993-02-24T06:48:06.968634+00:00",
            ("1984-08-01T15:00:59.999999+00:00", "1984-08-01T15:01:00+00:00"),
        ),
    ],
)
def test_analysis_inverse_includes_closed_birth_range_endpoint(
    minutes: int, analysis_at: str, expected
) -> None:
    person = PersonInfo(
        name="Closed birth range control",
        gender="女",
        birth_year=1984,
        birth_month=8,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_second=0,
        birth_timezone="America/Recife",
        birth_utc_offset="-03:00",
        use_true_solar_time=False,
    )
    result = analyze_birth_time_range(
        person, minutes, analysis_moment=datetime.fromisoformat(analysis_at)
    )
    assert [
        (event["lower_utc"], event["upper_utc"])
        for event in result["dayun_event_analysis"]["events"]
        if event["kind"] == "dayun_analysis_moment"
    ] == [expected]


def test_analysis_inverse_includes_the_forward_shifted_gap_label() -> None:
    person = PersonInfo(
        name="Civil gap inverse control",
        gender="女",
        birth_year=1984,
        birth_month=7,
        birth_day=9,
        birth_hour=4,
        birth_minute=16,
        birth_second=0,
        birth_timezone="America/New_York",
        birth_utc_offset="-04:00",
        use_true_solar_time=False,
    )
    result = analyze_birth_time_range(
        person, 1, analysis_moment=datetime(1985, 4, 28, 7, 30, tzinfo=timezone.utc)
    )
    assert [
        (event["lower_utc"], event["upper_utc"])
        for event in result["dayun_event_analysis"]["events"]
        if event["kind"] == "dayun_analysis_moment"
    ] == [
        ("1984-07-09T08:16:13.330837+00:00", "1984-07-09T08:16:13.330838+00:00"),
        ("1984-07-09T08:16:43.082903+00:00", "1984-07-09T08:16:43.082904+00:00"),
    ]


@pytest.mark.parametrize(
    "kind,label",
    [
        ("dayun_analysis_moment", "分析时刻逆像"),
        ("dayun_decade_leap_clip", "十年闰日裁剪"),
        ("dayun_future_civil_fold_end", "未来回拨结束"),
    ],
)
def test_snapshot_names_only_additional_events_actually_returned(
    kind: str, label: str
) -> None:

    data = {
        "uncertainty_minutes": 1,
        "sample_count": 3,
        "dayun_event_probe_count": 1,
        "dayun_event_analysis": {"events": [{"kind": kind}]},
    }
    lines = _birth_range_snapshot_lines(data)
    detail = next(line for line in lines if line.startswith("本次实际核对的补充事件"))
    assert detail == "本次实际核对的补充事件：" + label + "。"
    data["dayun_event_analysis"]["events"] = []
    assert not any(
        line.startswith("本次实际核对的补充事件")
        for line in _birth_range_snapshot_lines(data)
    )
