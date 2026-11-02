"""Literal-source conflicts must survive lookup, interpolation and calendar audits."""

import csv
import hashlib
import json
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_day_rate as rate
from fatebridge.core.guolao_calendar_year import gujin_fixed_qice_year
from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.core.guolao_lunar_velocity import gujin_table_conjunction
from fatebridge.validation.guolao_calendars import (
    audit_named_year_grid,
    compare_named_calendar_methods,
    compare_official_calendar,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/guolao-day-rate-v1"


def test_original_images_and_complete_literal_transcription_are_pinned():
    reference = json.loads((FIXTURE / "reference.json").read_text())
    for artifact in reference["artifacts"]:
        raw = (FIXTURE / artifact["path"]).read_bytes()
        assert len(raw) == artifact["bytes"]
        assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]
    rows = list(csv.DictReader((FIXTURE / "day-rates-transcribed.csv").open()))
    data, digest = rate._table()
    assert len(rows) == 169
    for row, actual in zip(rows, data["rows"], strict=True):
        assert int(row["limit_index"]) == actual["limit_index"]
        assert row["day_rate_days"] == actual["day_rate_days"]
        assert int(row["djvu_page"]) == actual["djvu_page"]
        assert row["half"] == actual["half"]
    assert data["collated_cumulative_anchors"] == json.loads(
        (FIXTURE / "cumulative-anchors-transcribed.json").read_text()
    )
    assert digest == hashlib.sha256(rate.DATA.read_bytes()).hexdigest()
    assert not reference["independent_second_collator"]
    assert len(json.loads((FIXTURE / "before-96-cli-stdout.json").read_text())) == 96


def test_all_rate_discrepancies_and_boundary_discontinuities_remain_visible():
    result = rate.audit_day_rate_table()
    assert result["rate_position_count"] == 169
    assert result["printed_numeric_rate_count"] == 168
    assert result["printed_empty_rate_indices"] == [0]
    assert result["effective_lookup_rate_count"] == 169
    assert [r["limit_index"] for r in result["equal_step_diagnostic_conflicts"]] == [
        90,
        154,
        166,
    ]
    assert [
        r["printed_day_rate_days"] for r in result["equal_step_diagnostic_conflicts"]
    ] == ["7.2807", "12.6392", "13.6333"]
    assert not any(
        r["diagnostic_used_to_replace_source"]
        for r in result["equal_step_diagnostic_conflicts"]
    )
    assert result["nonincreasing_interval_indices"] == [89]
    assert result["nonzero_boundary_jumps"] == 19
    assert not result["full_angular_table_independently_collated"]


@pytest.mark.parametrize("within", ["7.2807", "7.285", "7.2987"])
@pytest.mark.parametrize("half", [F(), F("13.7773")])
def test_printed_reversed_span_including_its_endpoints_is_not_resolved_by_sorting(
    within, half
):
    result = rate.gujin_day_rate_lunar(F(within) + half)
    assert result["status"] == "ambiguous_literal_rate_not_repaired"
    assert result["conflicting_reversed_interval_indices"] == [89]
    assert result["whole_limit_index"] is None
    assert result["signed_correction_ancient_du_exact"] is None
    assert not result["argument_within_printed_limits"]


@pytest.mark.parametrize(
    "anomaly,index",
    [
        ("0", 0),
        (".082", 1),
        ("6.7246", 82),
        ("6.8066", 83),
        ("6.8886", 84),
        ("6.9706", 85),
        ("7.0526", 86),
        ("7.28", 88),
        ("7.3", 90),
        ("12.63", 153),
        ("12.6392", 154),
        ("13.62", 165),
        ("13.6333", 166),
        ("13.7772", 167),
        ("13.7773", 168),
        ("27.5546", 0),
    ],
)
def test_literal_rate_boundaries_and_conflicts_are_used_exactly(anomaly, index):
    result = rate.gujin_day_rate_lunar(F(anomaly))
    assert result["whole_limit_index"] == index
    assert not result["interpolation_clipped_or_endpoint_smoothed"]


def test_printed_long_interval_retains_extrapolation_and_reports_it():
    result = rate.gujin_day_rate_lunar(F("7.4"))
    assert result["selected_printed_day_rate_days"] == "7.2807"
    assert F(result["interpolation_fraction_exact"]) == F(1193, 820)
    assert result["interpolation_fraction_exceeds_one"]


def test_central_cumulative_cells_preserve_source_curvature_instead_of_flat_band():
    expected = [
        F("5.42881000"),
        F("5.42916616"),
        F("5.42934424"),
        F("5.42916616"),
        F("5.42881000"),
    ]
    inputs = ["6.7246", "6.8066", "6.8886", "6.9706", "7.0526"]
    values = [
        F(rate.gujin_day_rate_lunar(F(x))["unsigned_correction_ancient_du_exact"])
        for x in inputs
    ]
    assert values == expected
    assert len(set(values)) == 3
    assert values[2] > values[1] > values[0]


def test_original49_local_lunar_step_and_residual_are_independent_of_whole_year_epoch():
    result = rate.gujin_day_rate_lunar(F("23.310758"))
    assert result["whole_limit_index"] == 116
    assert result["selected_printed_day_rate_days"] == "9.5129"
    computed = F(result["signed_correction_ancient_du_exact"])
    assert computed == F(745590902827, 164000000000)
    assert 0 < computed - F("4.546285") < F(".000001")
    # This is a local step only: the source49 whole-case revised epoch is not used.
    assert not result["full_angular_table_independently_collated"]


@pytest.mark.parametrize("elapsed,sexagenary", [(31, "癸巳"), (296, "乙酉")])
def test_old_endpoint_gaps_select_printed167_without_filling168(elapsed, sexagenary):
    middle = shoushi_winter_cycle(elapsed).zhongji_days
    old = gujin_table_conjunction(middle, 10)
    result = rate.gujin_day_rate_conjunction(middle, 10)
    assert old["lunar_velocity"]["whole_limit_index"] == 168
    assert old["research_conjunction_day_cycle_exact"] is None
    assert result["lunar_velocity"]["whole_limit_index"] == 167
    assert result["lunar_velocity"]["printed_velocity_ancient_du_per_limit"] == "1.2071"
    assert result["research_conjunction_sexagenary_day"] == sexagenary
    assert (
        result["angular_components"]["legacy_continuous_lunar_diagnostic"]
        == old["angular_components"]["lunar"]
    )
    assert result["angular_components"]["early_gujin37_epoch_retained"]
    assert not result["complete_source_calendar_accepted"]


def test_exact_half_endpoint_remains_an_empty_velocity_not_periodic_fill():
    # Force only the mean angular context; the literal table and velocity are real.
    context = rate.source_conjunction(F(), 0, profile_id=rate.GUJIN_COMPONENTS)
    context["lunar"]["anomaly_phase_days_exact"] = "13.7773"
    original = rate.source_conjunction
    try:
        rate.source_conjunction = lambda *a, **kw: context
        result = rate.gujin_day_rate_conjunction(F(), 0)
    finally:
        rate.source_conjunction = original
    assert (
        result["angular_components"]["lunar"]["signed_correction_ancient_du_exact"]
        == "0"
    )
    assert result["lunar_velocity"]["status"] == "printed_empty_endpoint_no_value"
    assert result["time_correction_days_exact"] is None


@pytest.mark.parametrize(
    "reference_id,matches,missing",
    [("jiajing3_1524_wdl108", 26, 0), ("wanli27_1599_nlc_preview", 6, 4)],
)
def test_unchanged_official_reference_is_compared_under_explicit_new_method(
    reference_id, matches, missing
):
    result = compare_official_calendar(reference_id, conjunction_method="day_rate")
    assert result["counts"] == dict(
        matches=matches,
        mismatches=0,
        computed_unavailable=0,
        reference_unreadable_or_unprovided=missing,
    )
    assert result["calendar"]["profile_id"] == rate.CALENDAR_PROFILE
    assert not result["parameters_selected_by_reference_fit"]
    assert not result["pre_registered_holdout"]


@pytest.mark.parametrize("elapsed", [31, 296])
def test_named_year_closes_previous_gap_without_claiming_all_years_are_accepted(
    elapsed,
):
    calendar = gujin_fixed_qice_year(
        shoushi_winter_cycle(elapsed).zhongji_days, conjunction_method="day_rate"
    )
    assert calendar["complete_named_year_assigned"]
    assert not calendar["complete_historical_calendar_accepted"]
    assert not calendar["used_in_native_birth_chart"]


@pytest.mark.parametrize("value", ["", "auto", "best_fit", True])
def test_calendar_cannot_silently_pick_a_method_by_fit(value):
    with pytest.raises(ValueError):
        gujin_fixed_qice_year(F(), conjunction_method=value)


@pytest.mark.parametrize("value", [0, 1.2, "23.310758", True])
def test_requires_exact_original_day_input(value):
    with pytest.raises(TypeError):
        rate.gujin_day_rate_lunar(value)


@pytest.mark.parametrize(
    "mutation", ["delete", "reorder", "precision", "endpoint", "anchors", "claim"]
)
def test_malformed_or_overclaimed_source_profiles_fail_closed(
    tmp_path, monkeypatch, mutation
):
    data = json.loads(rate.DATA.read_text())
    if mutation == "delete":
        data["rows"].pop()
    elif mutation == "reorder":
        data["rows"].reverse()
    elif mutation == "precision":
        data["rows"][3]["day_rate_days"] = "0.24600"
    elif mutation == "endpoint":
        data["half_anomalistic_month_days"] = "13.7774"
    elif mutation == "anchors":
        data["collated_cumulative_anchors"].pop()
    else:
        data["full_angular_table_independently_collated"] = True
    target = tmp_path / "table.json"
    target.write_text(json.dumps(data))
    monkeypatch.setattr(rate, "DATA", target)
    with pytest.raises(ValueError):
        rate.gujin_day_rate_lunar(F(1))


def test_cli_exposes_source_ambiguity_without_reporting_a_numeric_correction(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        sys, "argv", ["audit_guolao_day_rate.py", "--anomaly-days", "7.285"]
    )
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(
            str(ROOT / "scripts/audit_guolao_day_rate.py"), run_name="__main__"
        )
    assert exited.value.code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["signed_correction_ancient_du_exact"] is None


def test_grid_keeps_new_method_failures_and_old_default_distinct():
    # A source conflict can create new unresolved years; do not count old-gap
    # resolution as a universal coverage gain. Full400-year receipt is separate.
    result = audit_named_year_grid(0, 400, conjunction_method="day_rate")
    assert result["input_years"] == 400 and result["input_years_dropped"] == 0
    assert result["conjunction_method"] == "day_rate"
    assert result["counts"] == {
        "complete_under_named_fixed_qice_policy": 392,
        "partial_calendar_year": 8,
    }
    assert [r["elapsed_years"] for r in result["unresolved"]] == [
        45,
        46,
        66,
        168,
        188,
        310,
        311,
        331,
    ]
    for row in result["unresolved"]:
        assert (
            row["missing_first_cycle_conjunction_diagnostics"]
            or row["missing_year_tail_conjunction_diagnostics"]
        )
    assert all(
        result["rows"][i]["status"] == "complete_under_named_fixed_qice_policy"
        for i in [31, 296]
    )
    assert "conjunction_method" not in audit_named_year_grid(31, 32)


@pytest.mark.parametrize(
    "elapsed,both,agree",
    [(31, False, None), (45, False, None), (203, True, False), (243, True, True)],
)
def test_method_comparison_retains_disagreement_missingness_and_no_selection(
    elapsed, both, agree
):
    result = compare_named_calendar_methods(elapsed, elapsed + 1)
    assert result["input_years"] == 1 and result["input_years_dropped"] == 0
    assert result["rows"][0]["both_complete"] is both
    assert result["rows"][0]["calendar_facts_agree"] is agree
    assert not result["methods_selected_by_year_or_reference_fit"]
    assert not result["method_disagreement_is_external_accuracy_evidence"]


@pytest.mark.parametrize(
    "arguments",
    [["--conjunction-method", "day_rate"], ["--conjunction-method=day_rate"]],
)
def test_cli_does_not_silently_ignore_single_method_during_pair_comparison(
    monkeypatch, arguments
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_guolao_calendar_year.py",
            "--compare-methods-grid",
            "0",
            "1",
            *arguments,
        ],
    )
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(
            str(ROOT / "scripts/audit_guolao_calendar_year.py"), run_name="__main__"
        )
    assert exited.value.code == 2
