"""Frozen source witnesses for a state hidden between natal/minute probes."""

import gzip
import hashlib
import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.contracts.output_timing import BirthTimeEvent
from fatebridge.core.timing import TimingAnalysis
from fatebridge.services.birth_time_events import collect_natal_event_probes
from fatebridge.services.dayun_birth_events import collect_dayun_birth_event_probes
from fatebridge.services.timing_uncertainty import analyze_birth_time_range
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.solar_time import normalize_birth_time

REFERENCE = (
    Path(__file__).parents[1] / "data/bazi_dayun_calendar_carries_v1/reference.json.gz"
)
assert (
    hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
    == REFERENCE.with_suffix(".sha256").read_text().strip()
)
DATA = json.loads(gzip.decompress(REFERENCE.read_bytes()))
SELECTED = [
    DATA["rows"][0],
    next(r for r in DATA["rows"] if r["input"]["birth_year"] >= 2000),
]


RETAINED_LIQIU = next(
    row
    for row in json.loads(
        (Path(__file__).parents[1] / "data/retained_civil_points_v1.json").read_text()
    )["rows"]
    if row["name"] == "立秋"
)


@pytest.mark.parametrize("row", SELECTED, ids=lambda r: r["id"])
def test_range_retains_the_source_witness_before_dayun_state(row) -> None:
    person = PersonInfo(**row["input"])
    original = person.model_dump()
    result = analyze_birth_time_range(
        person, 1, analysis_moment=datetime.fromisoformat(row["analysis_at"])
    )
    assert (
        sorted({p["status"] for p in result["current_dayun_candidates"]})
        == row["expected_statuses"]
    )
    assert "current_dayun" in result["affected_fields"]
    assert result["sample_count"] == 3
    first = next(p for p in result["dayun_boundary_ranges"] if p["period"] == 1)
    witness = datetime.fromisoformat(row["expected_witnesses"][0]["manual_start_at"])
    assert (
        datetime.fromisoformat(first["earliest_start_at"])
        <= witness
        <= datetime.fromisoformat(first["latest_start_at"])
    )
    assert person.model_dump() == original
    assert result["event_analysis"]["continuous_completeness_certified"] is False


def test_reference_keeps_all_negative_carries_and_the_corrected_initial_hypothesis() -> (
    None
):
    assert DATA["counts"]["nominal_month_carries_in_birth_domain"] == 291964
    assert len(DATA["rows"]) == DATA["counts"]["negative_calendar_carry_jumps"] == 23794
    assert DATA["no_application_or_dateutil_imported"] is True
    assert DATA["rows"][0]["input"]["birth_day"] == 3
    assert DATA["rows"][0]["negative_jump_seconds"] < -86400
    assert all(r["missing_from_minute_grid"] == ["before_dayun"] for r in DATA["rows"])


def test_nominal_carry_keeps_the_original_point_reference_and_state_guards() -> None:
    row = RETAINED_LIQIU
    root = Fraction(int(row["civil_numerator"]), int(row["civil_denominator"]))
    nominal = root - Fraction(1, 4)
    floor = datetime.fromisoformat(row["display_utc"]) - timedelta(hours=6)
    center = datetime(2024, 8, 6, 18, 9, 16, tzinfo=timezone.utc)
    person = PersonInfo(
        birth_year=2024,
        birth_month=8,
        birth_day=6,
        birth_hour=18,
        birth_minute=9,
        birth_second=16,
        birth_timezone="UTC",
        gender="男",
        use_true_solar_time=False,
    )
    template = normalize_birth_time(person)
    low, high = center - timedelta(minutes=1), center + timedelta(minutes=1)
    natal = collect_natal_event_probes(template, low, high)
    result = collect_dayun_birth_event_probes(
        template,
        low,
        high,
        person.gender,
        natal_events=natal.payload,
        analysis_moment=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    event = next(
        e for e in result.payload["events"] if e["kind"] == "dayun_nominal_month_carry"
    )
    assert event["name"] == "1个名义月进位"
    assert event["civil_point"] == {
        "unit": "nominal_gregorian_day",
        "numerator": str(nominal.numerator),
        "denominator": str(nominal.denominator),
        "excluded_before": None,
    }
    assert event["reference_point"] == {
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
    instants = {p.normalized.input_datetime for p in result.probes}
    assert {
        floor + timedelta(microseconds=shift) for shift in [-1000, -1, 0, 1, 1000]
    } <= instants
    assert [
        TimingAnalysis._dayun_calendar_wall_context(
            floor + timedelta(microseconds=shift), person.gender, "UTC"
        )[3]
        for shift in [-1, 0, 1]
    ] == [
        {"years": 0, "months": 1, "days": 0, "microseconds": 168},
        {"years": 0, "months": 1, "days": 0, "microseconds": 48},
        {"years": 0, "months": 0, "days": 29, "microseconds": 86399999928},
    ]
    assert result.payload["continuous_completeness_certified"] is False
    assert (
        "continuous_boundary_extrema_and_near_carry_floating_root_order"
        in result.payload["unresolved_layers"]
    )


def test_jie_guard_labels_survive_the_reverse_zero_carry_cell_split() -> None:
    row = RETAINED_LIQIU
    floor = datetime.fromisoformat(row["display_utc"])
    center = datetime(2024, 8, 7, 0, 9, 16, tzinfo=timezone.utc)
    template = normalize_birth_time(
        PersonInfo(
            birth_year=2024,
            birth_month=8,
            birth_day=7,
            birth_hour=0,
            birth_minute=9,
            birth_second=16,
            birth_timezone="UTC",
            gender="女",
            use_true_solar_time=False,
        )
    )
    low, high = center - timedelta(minutes=1), center + timedelta(minutes=1)
    natal = collect_natal_event_probes(template, low, high)
    result = collect_dayun_birth_event_probes(
        template,
        low,
        high,
        "女",
        natal_events=natal.payload,
        analysis_moment=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    instants = {p.normalized.input_datetime for p in result.probes}
    assert {
        floor + timedelta(microseconds=shift) for shift in [-1000, -1, 0, 1, 1000]
    } <= instants
    assert result.payload["continuous_completeness_certified"] is False
