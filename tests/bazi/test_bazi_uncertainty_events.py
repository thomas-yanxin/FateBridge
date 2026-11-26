"""Source-frozen missing states and synthetic event-order isolation controls."""

import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

import fatebridge.services.birth_time_events as events
import fatebridge.utils.solar_time as clock
from fatebridge.core.almanac import SolarTerm
from fatebridge.core.contracts.output_timing import BirthTimeEvent
from fatebridge.services.birth_time_events import collect_natal_event_probes
from fatebridge.services.timing_uncertainty import analyze_birth_time_range
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.civil_time import ZonedCalendar
from fatebridge.utils.solar_time import normalize_birth_time

REFERENCE = (
    Path(__file__).parents[1] / "data/bazi_uncertainty_events_v1/reference.json.gz"
)
assert (
    hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
    == REFERENCE.with_suffix(".sha256").read_text().strip()
)
ROWS = json.loads(gzip.decompress(REFERENCE.read_bytes()))["rows"]
KNOWN = [r for r in ROWS if r["status"] == "resolved_three_regions"]
SELECTED = list(
    {
        row["id"]: row
        for row in [
            KNOWN[0],
            next(r for r in KNOWN if r["root_minus_hour_seconds"] < 0),
            next(r for r in KNOWN if r["input"]["birth_year"] >= 2000),
            next(
                r
                for r in KNOWN
                if r["root_name"] == "立春" and r["input"]["birth_year"] >= 2000
            ),
        ]
    }.values()
)


RETAINED_LIQIU = next(
    row
    for row in json.loads(
        (Path(__file__).parents[1] / "data/retained_civil_points_v1.json").read_text()
    )["rows"]
    if row["name"] == "立秋"
)


@pytest.mark.parametrize("row", SELECTED, ids=lambda r: r["id"])
def test_actual_range_includes_the_frozen_intermediate_month_hour_state(row) -> None:
    person = PersonInfo(**row["input"])
    before = person.model_dump()
    result = analyze_birth_time_range(person, 1, analysis_moment=datetime(2102, 1, 1))
    actual = {
        (r["pillars"]["month"][-1], r["pillars"]["hour"][-1])
        for r in result["pillars_candidates"]
    }
    expected = {
        (r["signature"]["month_branch"], r["signature"]["hour_branch"])
        for r in row["expected_regions"]
    }
    assert actual == expected
    assert len(actual) == 3
    assert (
        sum(r["sample_count"] for r in result["pillars_candidates"])
        == result["sample_count"]
        == 3
    )
    event_only = [r for r in result["pillars_candidates"] if r["sample_count"] == 0]
    assert len(event_only) == 1 and event_only[0]["event_probe_count"] > 0
    assert result["event_analysis"]["continuous_completeness_certified"] is False
    assert person.model_dump() == before


@pytest.mark.parametrize("root_seconds", [85, 95, 89.9998])
def test_apparent_clock_probes_both_event_orders_and_preserves_overlapping_brackets(
    root_seconds: float | int, monkeypatch: pytest.MonkeyPatch
) -> None:

    # Synthetic kernel control, not an independent physical equation-of-time vector.
    monkeypatch.setattr(clock, "calculate_equation_of_time_minutes", lambda _: 0.0)
    center = datetime(2000, 2, 4, 0, 59, 30, tzinfo=timezone.utc)
    low, high = center - timedelta(minutes=1), center + timedelta(minutes=1)
    jie_at = low + timedelta(seconds=root_seconds)

    def term(name, at):
        return SolarTerm(
            name,
            ZonedCalendar.from_datetime(at),
            resolution_provider="swisseph",
            ephemeris_model="synthetic_control",
        )

    previous, jie, following = (
        term("大寒", low - timedelta(days=15)),
        term("立春", jie_at),
        term("雨水", high + timedelta(days=15)),
    )
    monkeypatch.setattr(
        events,
        "get_adjacent_solar_terms",
        lambda at, _: (previous, jie) if at < jie_at else (jie, following),
    )
    monkeypatch.setattr(
        events.BaZiCalendar,
        "get_four_pillars",
        lambda *a, **k: {n: ("甲", "子") for n in ["year", "month", "day", "hour"]},
    )
    person = PersonInfo(
        birth_year=2000,
        birth_month=2,
        birth_day=4,
        birth_hour=0,
        birth_minute=59,
        birth_second=30,
        birth_timezone="UTC",
        birth_longitude=0,
        use_true_solar_time=True,
    )
    result = events.collect_natal_event_probes(normalize_birth_time(person), low, high)
    clock_at = low + timedelta(seconds=90)
    if root_seconds != 89.9998:
        assert any(
            min(clock_at, jie_at) < p.normalized.input_datetime < max(clock_at, jie_at)
            for p in result.probes
        )
    else:
        assert result.payload["unresolved_event_orders"]
    assert result.payload["continuous_completeness_certified"] is False
    assert result.payload["physical_precision_certified"] is False
    jie_event = next(e for e in result.payload["events"] if e["kind"] == "jie")
    assert jie_event["lower_utc"] == jie_event["upper_utc"] == jie_at.isoformat()
    assert jie_event["bracket_width_seconds"] == 0.0
    for event in result.payload["events"]:
        if event["kind"] == "solar_clock":
            assert event["bracket_width_seconds"] <= 0.001
        else:
            pass


def test_zero_range_does_not_invent_an_interval_or_duplicate_a_point() -> None:

    person = PersonInfo(
        birth_year=2000,
        birth_month=5,
        birth_day=1,
        birth_hour=10,
        birth_minute=0,
        birth_second=0,
        birth_timezone="UTC",
        use_true_solar_time=False,
    )
    normalized = normalize_birth_time(person)
    at = normalized.input_datetime.replace(tzinfo=timezone.utc)
    result = collect_natal_event_probes(normalized, at, at)
    assert len(result.probes) == 1
    assert (
        result.payload["regions"][0]["start_utc"]
        == result.payload["regions"][0]["end_utc"]
    )
    assert result.payload["continuous_completeness_certified"] is False


def test_closed_end_boundary_is_retained_as_its_own_point_state() -> None:
    person = PersonInfo(
        birth_year=2000,
        birth_month=5,
        birth_day=1,
        birth_hour=0,
        birth_minute=59,
        birth_second=0,
        birth_timezone="UTC",
        use_true_solar_time=False,
    )
    result = analyze_birth_time_range(person, 1, analysis_moment=datetime(2026, 1, 1))
    assert {r["pillars"]["hour"][-1] for r in result["pillars_candidates"]} == {
        "子",
        "丑",
    }
    analysis = result["event_analysis"]
    assert analysis["regions"][-1]["end_inclusive"] is False
    endpoint = analysis["probes"][analysis["endpoint_probe_indices"][-1]]
    assert endpoint["instant_utc"] == "2000-05-01T01:00:00+00:00"
    assert endpoint["pillars"]["hour"][-1] == "丑"


def test_raw_fold_event_uses_distinct_physical_instants_without_mutating_source() -> (
    None
):
    person = PersonInfo(
        birth_year=1991,
        birth_month=9,
        birth_day=15,
        birth_hour=1,
        birth_minute=59,
        birth_second=30,
        birth_timezone="Asia/Shanghai",
        birth_utc_offset="+09:00",
        use_true_solar_time=False,
    )
    original = person.model_dump()
    result = analyze_birth_time_range(person, 1, analysis_moment=datetime(2026, 1, 1))
    analysis = result["event_analysis"]
    assert any(
        e["kind"] == "civil_clock" and e["at_utc"] == "1991-09-14T17:00:00+00:00"
        for e in analysis["events"]
    )
    instants = [p["instant_utc"] for p in analysis["probes"]]
    assert len(instants) == len(set(instants))
    offsets = {
        datetime.fromisoformat(p["civil_datetime"]).utcoffset()
        for p in analysis["probes"]
    }
    assert offsets == {timedelta(hours=9), timedelta(hours=8)}
    assert person.model_dump() == original


def test_nonmonotone_synthetic_anchors_remain_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:

    monkeypatch.setattr(
        clock, "calculate_equation_of_time_minutes", lambda at: -2.0 * at.minute
    )
    person = PersonInfo(
        birth_year=2000,
        birth_month=5,
        birth_day=1,
        birth_hour=10,
        birth_minute=10,
        birth_second=0,
        birth_timezone="UTC",
        birth_longitude=0,
        use_true_solar_time=True,
    )
    template = normalize_birth_time(person)
    center = template.input_datetime.replace(tzinfo=timezone.utc)
    result = events.collect_natal_event_probes(
        template, center - timedelta(minutes=1), center + timedelta(minutes=1)
    )
    assert result.payload["monotonic_at_minute_anchors"] is False
    assert result.payload["status"] == "partial_unresolved_event_order"
    assert result.payload["unresolved_event_orders"]
    assert result.payload["continuous_completeness_certified"] is False


def test_jie_event_encloses_the_original_retained_point_and_observed_states() -> None:

    row = RETAINED_LIQIU
    floor = datetime.fromisoformat(row["display_utc"])
    person = PersonInfo(
        birth_year=2024,
        birth_month=8,
        birth_day=7,
        birth_hour=0,
        birth_minute=9,
        birth_second=16,
        birth_timezone="UTC",
        use_true_solar_time=False,
    )
    center = datetime(2024, 8, 7, 0, 9, 16, tzinfo=timezone.utc)
    result = collect_natal_event_probes(
        normalize_birth_time(person),
        center - timedelta(minutes=1),
        center + timedelta(minutes=1),
    )
    event = next(e for e in result.payload["events"] if e["kind"] == "jie")
    assert event["name"] == "立秋"
    assert event["civil_point"] == {
        "unit": "nominal_gregorian_day",
        "numerator": row["civil_numerator"],
        "denominator": row["civil_denominator"],
        "excluded_before": None,
    }
    assert event["lower_utc"] == floor.isoformat()
    assert (
        event["upper_utc"]
        == event["at_utc"]
        == (floor + timedelta(microseconds=1)).isoformat()
    )
    assert event["bracket_width_seconds"] == 0.000001
    assert event["bracket_basis"] == "nominal_gregorian_microsecond_enclosure_v1"
    BirthTimeEvent.model_validate(event, context={"full_result": True})
    observed = {
        p.normalized.input_datetime: "".join(p.pillars["month"]) for p in result.probes
    }
    assert [
        observed[floor + timedelta(microseconds=shift)] for shift in [-1, 0, 1]
    ] == ["辛未", "辛未", "壬申"]
    assert result.payload["continuous_completeness_certified"] is False


@pytest.mark.parametrize(
    "low_shift,high_shift,expected_jie_count", [(0, 0, 0), (0, 1, 1), (1, 1, 0)]
)
def test_jie_range_membership_uses_the_source_point(
    low_shift: int, high_shift: int, expected_jie_count: int
) -> None:

    row = RETAINED_LIQIU
    floor = datetime.fromisoformat(row["display_utc"])
    template = normalize_birth_time(
        PersonInfo(
            birth_year=2024,
            birth_month=8,
            birth_day=7,
            birth_hour=0,
            birth_minute=9,
            birth_second=16,
            birth_timezone="UTC",
            use_true_solar_time=False,
        )
    )
    result = collect_natal_event_probes(
        template,
        floor + timedelta(microseconds=low_shift),
        floor + timedelta(microseconds=high_shift),
    )
    assert len([e for e in result.payload["events"] if e["kind"] == "jie"]) == (
        expected_jie_count
    )


def test_projected_nominal_event_does_not_invent_a_missing_cap() -> None:

    row = RETAINED_LIQIU
    floor = datetime.fromisoformat(row["display_utc"])
    record = {
        "kind": "jie",
        "bracket_basis": "nominal_gregorian_microsecond_enclosure_v1",
        "civil_point": {
            "unit": "nominal_gregorian_day",
            "numerator": row["civil_numerator"],
            "denominator": row["civil_denominator"],
        },
        "lower_utc": floor.isoformat(),
        "upper_utc": (floor + timedelta(microseconds=1)).isoformat(),
    }
    projected = BirthTimeEvent.model_validate(record)
    assert projected.civil_point is not None
    assert projected.civil_point.known_day() == Fraction(
        int(row["civil_numerator"]), int(row["civil_denominator"])
    )
    assert projected.civil_point.known_point() is None
    assert (
        "excluded_before" not in projected.model_dump(exclude_unset=True)["civil_point"]
    )
    with pytest.raises(ValidationError, match="微秒格点上包"):
        BirthTimeEvent.model_validate({**record, "upper_utc": floor.isoformat()})
