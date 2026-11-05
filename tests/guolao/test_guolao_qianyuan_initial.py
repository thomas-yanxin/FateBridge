"""Printed durations, quantity separation and exact boundaries; no prediction."""

import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

import fatebridge.core.guolao_qianyuan_initial as module
from fatebridge.core.guolao_nijl_grid import compare_intro_examples

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/guolao-qianyuan-initial-v1"
REFERENCE_SHA = "d8e1449f45a984d4e60bccb4abbbed57642c7fbc556734ed68e6cfac184edbb6"


def test_original_pdf_renderings_and_preimplementation_duration_reference_are_bound():
    ref = json.loads((FIXTURE / "reference.json").read_text())
    for name, wanted in ref["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == wanted
    assert (
        ref["source_pdf"]
        == hashlib.sha256(
            (FIXTURE / "qianyuan-nlc416-original.pdf").read_bytes()
        ).hexdigest()
    )
    assert ref["source_data"] == module.DATA_SHA256
    assert (
        hashlib.sha256(
            (FIXTURE / "reference-before-domain-change.json").read_bytes()
        ).hexdigest()
        == REFERENCE_SHA
    )
    assert not ref["independent_second_collator"]


def test_both_printed_examples_and_prior_luwei_counterexamples_are_kept_separate():
    before = compare_intro_examples()
    result = module.audit_original_examples()
    assert result["example_count"] == len(result["cases"]) == 2
    assert all(case["printed_duration_match"] for case in result["cases"])
    assert [
        case["calculation"]["total_source_years_exact"] for case in result["cases"]
    ] == ["65/6", "79/4"]
    assert result["existing_luwei_original_comparison"] == before
    assert result["original_luwei_numeric_counterexample_count"] == 2
    assert not result["luwei_circular_rows_resolved"]
    assert not result["full_original_acceptance"]
    assert result["real_world_prediction_cases"] == 0
    assert compare_intro_examples() == before


@pytest.mark.parametrize("case_index", [0, 1])
def test_source_hour_interpretation_matches_two_held_duration_recipes(case_index):
    held = json.loads((FIXTURE / "reference-before-domain-change.json").read_text())[
        "cases"
    ][case_index]
    parts = held["input_components"]
    if "hours_short" in parts:
        days = F(parts["days_before_next"]) - F(parts["hours_short"]) / 12
    else:
        days = F(parts["days"]) + F(parts["hours"]) / 12
    assert days == F(held["elapsed_source_days"])
    result = module.initial_limit(module.QianyuanSourceDays(days, module.BASIS))
    assert F(result["total_source_years_exact"]) == F(held["printed_years"]) + F(
        held["printed_months"], 12
    )
    assert result["modern_calendar_date"] is None


def test_all_prior_rational_probes_and_extreme_small_differences_stay_exact():
    ref = json.loads((FIXTURE / "reference-before-domain-change.json").read_text())
    for probe in ref["probes"]:
        value = F(probe["input_source_days"])
        result = module.initial_limit(module.QianyuanSourceDays(value, module.BASIS))
        assert F(result["total_source_years_exact"]) == F(
            probe["expected_total_source_years"]
        )
        reconstructed = (
            F(result["whole_source_years"])
            + F(result["remaining_source_months_exact"]) / 12
        )
        assert reconstructed == F(probe["expected_total_source_years"])
        assert not result["fractional_months_rounded"]


def test_single_qianyuan_computation_does_not_load_luwei_to_fill_its_values(
    monkeypatch,
):
    def unavailable():
        pytest.fail("Qianyuan duration must not depend on LuWei diagram values")

    monkeypatch.setattr(module, "compare_intro_examples", unavailable)
    result = module.initial_limit(module.QianyuanSourceDays(F(5, 2), module.BASIS))
    assert result["remaining_source_months_exact"] == "10"


@pytest.mark.parametrize("bad", [F(3), 3, 3.0, True, None, "初"])
def test_unlabelled_values_are_not_implicitly_source_time(bad):
    with pytest.raises(TypeError):
        module.initial_limit(bad)


@pytest.mark.parametrize("bad", [3, 3.0, True, "初", "3", None])
def test_day_value_requires_an_explicit_fraction(bad):
    with pytest.raises(TypeError):
        module.QianyuanSourceDays(bad, module.BASIS)


@pytest.mark.parametrize(
    "basis", ["longitude_degrees", "luwei_limit_scale_degrees", "utc_days", "", None]
)
def test_angular_ruler_and_clock_quantities_cannot_be_relabelled(basis):
    with pytest.raises(ValueError, match="不把角度"):
        module.QianyuanSourceDays(F(3), basis)


@pytest.mark.parametrize("bad", [F(-1, 10**30), F(30) + F(1, 10**30), F(31)])
def test_source_range_never_clips_or_wraps_at_a_tiny_boundary(bad):
    with pytest.raises(ValueError, match="不截断"):
        module.QianyuanSourceDays(bad, module.BASIS)


def test_changed_source_notes_or_deleted_printed_examples_are_rejected(
    monkeypatch, tmp_path
):
    data = json.loads(module.DATA.read_text())
    data["cases"].pop()
    path = tmp_path / "incomplete.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(module, "DATA", path)
    with pytest.raises(ValueError, match="指纹"):
        module.audit_original_examples()
    monkeypatch.setattr(
        module, "DATA_SHA256", hashlib.sha256(path.read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError, match="具名乾元"):
        module.audit_original_examples()
