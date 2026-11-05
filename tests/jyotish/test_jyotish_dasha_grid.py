"""Full-grid period coverage, independent arithmetic and matched natal facts."""

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.core import jyotish
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish_dasha_grid import DashaGrid
from fatebridge.services.jyotish import calculate_vimshottari

BIRTH = dict(
    birth_year=2000,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_timezone="UTC",
    birth_latitude=0,
    birth_longitude=0,
)
TARGET = dict(analysis_year=2001, analysis_month=1, analysis_day=1, analysis_hour=12)
FIXTURES = Path(__file__).parents[1] / "fixtures"
ORACLE = json.loads((FIXTURES / "jyotish-dasha-oracle.json").read_text())


def test_real_internal_stage_missing_from_three_points_is_retained():
    result = calculate_vimshottari(
        **BIRTH, divisions=[], birth_time_uncertainty_minutes=120, **TARGET
    )
    sensitivity = result["vimshottari"]["birth_time_sensitivity"]
    variants = sensitivity["stage_variants"]
    labels = {(r["major_lord"], r["sub_lord"]) for r in variants}
    assert labels == {("Rahu", "Mars"), ("Rahu", "Moon"), ("Jupiter", "Jupiter")}
    endpoints = {
        (r["current_major"]["lord"], r["current_sub"]["lord"])
        for r in sensitivity["samples"]
    }
    assert ("Rahu", "Mars") not in endpoints
    assert (
        sensitivity["requested_sample_count"]
        == result["india"]["birth_time_sensitivity"]["sample_count"]
        == 481
    )
    assert sensitivity["evaluated_sample_count"] == 481
    assert sum(r["sample_count"] for r in variants) == 481
    assert len(sensitivity["adjacent_stage_change_brackets"]) == 2
    for bracket in sensitivity["adjacent_stage_change_brackets"]:
        assert (
            0
            < bracket["upper_birth_offset_seconds"]
            - bracket["lower_birth_offset_seconds"]
            <= 30
        )


@pytest.mark.parametrize("case", ORACLE["cases"])
def test_periods_against_pinned_pyjhora_with_controlled_moon_inputs(case):
    birth = datetime.fromisoformat(ORACLE["birth_utc"]) + timedelta(
        seconds=case["offset_seconds"]
    )
    result = jyotish.vimshottari(
        birth,
        case["moon_longitude"],
        datetime.fromisoformat(case["analysis"]),
        year_basis=case["year_basis"],
    )
    for level, name in [("current_major", "major"), ("current_sub", "sub")]:
        assert result[level]["lord"] == case[name]
        for boundary in ["start", "end"]:
            delta = datetime.fromisoformat(
                result[level][boundary]
            ) - datetime.fromisoformat(case[f"{name}_{boundary}"])
            assert abs(delta.total_seconds()) <= ORACLE["boundary_tolerance_seconds"]


def test_oracle_records_frozen_inputs_and_all_predeclared_cases():
    seeds = FIXTURES / "jyotish-dasha-oracle-seeds.json"
    assert hashlib.sha256(seeds.read_bytes()).hexdigest() == ORACLE["seeds_sha256"]
    assert ORACLE["version"] == "4.8.7"
    assert len(ORACLE["cases"]) == 25 * 4 * 3
    assert len({c["year_basis"] for c in ORACLE["cases"]}) == 3
    assert any(c["analysis"].startswith("2225-") for c in ORACLE["cases"])


@pytest.mark.parametrize(
    "uncertainty,count,distinct", [(None, 0, 0), (0, 1, 1), (1e-10, 3, 1)]
)
def test_unknown_zero_and_rounded_duplicate_instants_remain_distinct_concepts(
    uncertainty, count, distinct
):
    result = calculate_vimshottari(
        **BIRTH, divisions=[], birth_time_uncertainty_minutes=uncertainty, **TARGET
    )
    sensitivity = result["vimshottari"]["birth_time_sensitivity"]
    assert (
        sensitivity["requested_sample_count"]
        == sensitivity["evaluated_sample_count"]
        == count
    )
    assert sensitivity["distinct_birth_instant_count"] == distinct
    assert sensitivity["distinct_evaluated_birth_instant_count"] == distinct
    assert sensitivity["status"] == (
        "not_assessed" if uncertainty is None else "sampled_full_birth_grid"
    )
    assert all(
        row["reference"] == "nominal_birth_instant_only"
        for row in result["vimshottari"]["natal_ruler_context"]
    )


def test_alternative_contexts_use_their_own_birth_grid_points_and_coordinate_scopes():
    result = calculate_vimshottari(
        **BIRTH, divisions=[9, 30], birth_time_uncertainty_minutes=120, **TARGET
    )
    birth = build_astro_birth_info(**BIRTH)
    sample_charts = {}
    saw_changed_house = False
    nominal = result["india"]["charts"]
    for variant in result["vimshottari"]["birth_time_sensitivity"]["stage_variants"]:
        for chart_name in ["D1", "D9", "D30"]:
            for lord in {variant["major_lord"], variant["sub_lord"]}:
                contexts = [
                    r
                    for r in variant["natal_ruler_contexts"]
                    if r["chart"] == chart_name and r["planet_id"] == lord
                ]
                assert (
                    sum(r["sample_count"] for r in contexts) == variant["sample_count"]
                )
        for context in variant["natal_ruler_contexts"]:
            assert (
                sum(s["sample_count"] for s in context["sample_segments"])
                == context["sample_count"]
            )
            offset = context["sample_segments"][0]["first_offset_seconds"]
            if offset not in sample_charts:
                raw = jyotish.positions(
                    birth, birth.utc_datetime + timedelta(seconds=offset)
                )
                sample_charts[offset] = {
                    f"D{d}": jyotish.divisional_chart(raw, d) for d in [1, 9, 30]
                }
            chart = sample_charts[offset][context["chart"]]
            planet = next(
                p for p in chart["planets"] if p["id"] == context["planet_id"]
            )
            for name in ["sign", "house", "dignity"]:
                assert context[name] == planet[name]
            assert context["owned_houses"] == [
                h["house"] for h in chart["houses"] if h["lord"] == planet["id"]
            ]
            nominal_planet = next(
                p
                for p in nominal[context["chart"]]["planets"]
                if p["id"] == planet["id"]
            )
            saw_changed_house |= planet["house"] != nominal_planet["house"]
            if context["chart"] == "D30":
                assert "longitude" not in context["sampled_numeric_ranges"]
                assert "degree_in_sign" not in context["sampled_numeric_ranges"]
                assert "d1_conditions" not in context
            if context["chart"] == "D1":
                assert (
                    context["d1_conditions"]["motion"]
                    == planet["physical_state"]["motion"]
                )
                value = planet["longitude"]
                bounds = context["sampled_numeric_ranges"]["longitude"]
                assert bounds["minimum"] <= value <= bounds["maximum"]
    assert saw_changed_house


@pytest.mark.native_engine_fault
def test_complete_stage_grid_adds_no_ephemeris_calls(monkeypatch):
    from fatebridge.core.astro import runtime

    original = runtime.ephemeris_call
    counts = []
    calls = []

    def spy(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", spy)
    options = dict(divisions=[9, 30], birth_time_uncertainty_minutes=2)
    jyotish.build_india(build_astro_birth_info(**BIRTH), **options)
    counts.append(list(calls))
    calls.clear()
    calculate_vimshottari(**BIRTH, **options, **TARGET)
    counts.append(list(calls))
    assert counts[0] == counts[1]


@pytest.mark.native_engine_fault
def test_repeated_ruler_pair_does_not_merge_noncontiguous_birth_segments(monkeypatch):
    import fatebridge.core.jyotish_dasha_grid as module

    birth = build_astro_birth_info(**BIRTH)
    raw = jyotish.positions(birth)
    native = jyotish.vimshottari(
        birth.utc_datetime,
        raw["longitudes"]["Moon"],
        datetime(2001, 1, 1, tzinfo=timezone.utc),
    )
    pairs = iter([("Moon", "Moon"), ("Moon", "Mars"), ("Moon", "Moon")])

    def fake_period(*args, **kwargs):
        result = copy.deepcopy(native)
        result["current_major"]["lord"], result["current_sub"]["lord"] = next(pairs)
        return result

    monkeypatch.setattr(module, "vimshottari", fake_period)
    grid = DashaGrid(
        birth.utc_datetime,
        datetime(2001, 1, 1, tzinfo=timezone.utc),
        "sidereal_365_25636",
        [],
    )
    for offset in [-30.0, 0.0, 30.0]:
        grid.observe(offset, raw)
    result = grid.result()
    assert len(result["adjacent_stage_change_brackets"]) == 2
    repeated = result["stage_variants"][0]
    assert repeated["sample_count"] == 2
    assert len(repeated["sample_segments"]) == 2
    context = repeated["natal_ruler_contexts"][0]
    assert context["roles"] == ["major", "sub"]
    assert context["sample_count"] == 2
