"""Whole-year original-calendar facts, gaps and non-vacuous comparisons."""

import copy
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_calendar_year as year
from fatebridge.core.guolao_historical import shoushi_winter_cycle
from fatebridge.validation import guolao_calendars as audit

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests/fixtures/guolao-official-calendar-v1"
SOURCE = json.loads((FIXTURE / "reference.json").read_text())


@pytest.fixture(scope="module")
def jiajing():
    return audit.compare_official_calendar("jiajing3_1524_wdl108")


@pytest.fixture(scope="module")
def wanli():
    return audit.compare_official_calendar("wanli27_1599_nlc_preview")


def test_original_files_and_precomparison_transcription_remain_pinned():
    for artifact in SOURCE["artifacts"]:
        if artifact["path"].endswith("-cli-stdout.json"):
            continue  # Retired program output is not an independent source.
        raw = (FIXTURE / artifact["path"]).read_bytes()
        assert len(raw) == artifact["bytes"]
        assert hashlib.sha256(raw).hexdigest() == artifact["sha256"]
    original = (FIXTURE / "reference-transcribed-before-comparison.json").read_bytes()
    assert original == audit.DATA.read_bytes()
    assert hashlib.sha256(original).hexdigest() == SOURCE["runtime_reference_sha256"]
    assert (
        hashlib.sha256(original).hexdigest()
        == SOURCE["transcription_before_comparison_sha256"]
    )
    assert SOURCE["single_collator"] and not SOURCE["independent_second_collator"]
    assert SOURCE["original_pdf_pages"] == 36


def test_complete_jiajing_summary_matches_all_twelve_month_starts_and_sizes(jiajing):
    calendar, reference = jiajing["calendar"], jiajing["reference"]
    assert calendar["complete_named_year_assigned"]
    assert (calendar["month_count"], calendar["total_days"]) == (12, 354)
    assert [
        (
            r["month_number"],
            r["is_leap_month"],
            r["length_days"],
            r["sexagenary_start_day"],
        )
        for r in calendar["months"]
    ] == [
        (
            r["month_number"],
            r["is_leap_month"],
            r["length_days"],
            r["sexagenary_start_day"],
        )
        for r in reference["months"]
    ]
    assert jiajing["counts"] == {
        "matches": 26,
        "mismatches": 0,
        "computed_unavailable": 0,
        "reference_unreadable_or_unprovided": 0,
    }
    assert jiajing["status"] == "agreement_on_readable_reference_fields_only"
    assert not jiajing["complete_historical_calendar_accepted"]
    assert not jiajing["real_world_prediction_validated"]
    assert not jiajing["pre_registered_holdout"]


@pytest.mark.parametrize("fixture_name", ["jiajing", "wanli"])
def test_year_end_and_shared_civil_boundaries_do_not_include_prior_winter_months(
    request, fixture_name
):
    calendar = request.getfixturevalue(fixture_name)["calendar"]
    rows = calendar["months"]
    assert rows[0]["month_number"] == 1 and not rows[0]["is_leap_month"]
    assert rows[-1]["month_number"] == 12
    assert [r["month_number"] for r in rows if not r["is_leap_month"]] == list(
        range(1, 13)
    )
    for a, b in zip(rows, rows[1:]):
        assert a["next_start_source_day_integer"] == b["start_source_day_integer"]
    next_first = calendar["next_regular_first_month"]
    assert next_first["month_number"] == 1 and not next_first["is_leap_month"]
    assert (
        rows[-1]["next_start_source_day_integer"]
        == next_first["start_source_day_integer"]
    )
    assert sum(r["length_days"] for r in rows) == calendar["total_days"]
    assert len(rows) == calendar["month_count"]
    assert not calendar["complete_historical_calendar_accepted"]
    assert not calendar["modern_epoch_calibrated"]
    assert not calendar["used_in_native_birth_chart"]
    assert calendar["modern_lunar_dates"] is None


def test_partial_wanli_reference_retains_two_unreadable_starts_and_two_unprovided_year_fields(
    wanli,
):
    assert (wanli["calendar"]["month_count"], wanli["calendar"]["total_days"]) == (
        13,
        384,
    )
    assert [
        r["month_number"] for r in wanli["calendar"]["months"] if r["is_leap_month"]
    ] == [4]
    assert wanli["counts"] == {
        "matches": 6,
        "mismatches": 0,
        "computed_unavailable": 0,
        "reference_unreadable_or_unprovided": 4,
    }
    missing = [
        r
        for r in wanli["comparisons"]
        if r["status"] == "reference_unreadable_or_unprovided"
    ]
    assert len(missing) == 4
    assert all(r["reference"] is None for r in missing)
    assert all(r["computed"] is not None for r in missing)
    assert not wanli["missing_reference_fields_counted_as_matches"]
    assert not wanli["parameters_selected_by_reference_fit"]


def test_unused_missing_late_neighbor_does_not_invalidate_completed_year(monkeypatch):
    original = year.gujin_table_conjunction

    def missing(middle, index):
        result = original(middle, index)
        if index == 17:
            result["research_conjunction_offset_from_winter_days_exact"] = None
        return result

    monkeypatch.setattr(year, "gujin_table_conjunction", missing)
    result = year.gujin_fixed_qice_year(F("88753.8789"))
    assert result["complete_named_year_assigned"] and result["total_days"] == 354
    assert (
        result["extra_conjunction_candidates"][-1][
            "research_conjunction_offset_from_winter_days_exact"
        ]
        is None
    )


def test_required_missing_year_end_keeps_valid_months_but_not_aggregate_acceptance(
    monkeypatch,
):
    original = year.gujin_table_conjunction

    def missing(middle, index):
        result = original(middle, index)
        if index == 15:
            result["research_conjunction_offset_from_winter_days_exact"] = None
        return result

    monkeypatch.setattr(year, "gujin_table_conjunction", missing)
    result = audit.compare_official_calendar("jiajing3_1524_wdl108")
    assert not result["calendar"]["complete_named_year_assigned"]
    assert result["calendar"]["reason"] == "missing_required_year_tail_conjunction"
    assert len(result["calendar"]["months"]) == 12
    assert result["counts"]["matches"] == 24
    assert result["counts"]["computed_unavailable"] == 2
    assert result["calendar"]["month_count"] is result["calendar"]["total_days"] is None
    assert result["status"] == "required_calculation_unavailable"


def test_first_cycle_failure_never_borrows_next_year_or_runs_tail(jiajing, monkeypatch):
    base = copy.deepcopy(jiajing["calendar"]["first_winter_cycle"])
    base["month_assignment"]["status"] = "unresolved"
    monkeypatch.setattr(year, "gujin_fixed_qice_months", lambda _: base)
    monkeypatch.setattr(
        year, "gujin_table_conjunction", lambda *_: pytest.fail("unneeded tail")
    )
    result = year.gujin_fixed_qice_year(F("88753.8789"))
    assert result["reason"] == "first_winter_cycle_unresolved"
    assert result["months"] == [] and not result["complete_named_year_assigned"]


def test_anomalous_tail_length_is_not_clamped(monkeypatch):
    original = year.gujin_table_conjunction

    def shifted(middle, index):
        result = original(middle, index)
        if index == 15:
            result["research_conjunction_offset_from_winter_days_exact"] = str(
                F(result["research_conjunction_offset_from_winter_days_exact"]) + 3
            )
        return result

    monkeypatch.setattr(year, "gujin_table_conjunction", shifted)
    result = year.gujin_fixed_qice_year(F("88753.8789"))
    assert result["reason"] == "year_tail_month_length_outside_29_or_30"
    assert not result["complete_named_year_assigned"]


def test_tail_qi_sequence_conflict_not_relabelled_to_complete_year(
    jiajing, monkeypatch
):
    base = copy.deepcopy(jiajing["calendar"]["first_winter_cycle"])
    for i in [12, 13, 14]:
        row = base["conjunction_candidates"][i]
        row["research_conjunction_offset_from_winter_days_exact"] = str(
            F(row["research_conjunction_offset_from_winter_days_exact"]) + 30
        )
    monkeypatch.setattr(year, "gujin_fixed_qice_months", lambda _: base)
    result = year.gujin_fixed_qice_year(F("88753.8789"))
    assert result["reason"] == "year_tail_principal_term_sequence_conflict"
    assert not result["complete_named_year_assigned"]


def test_comparison_exposes_mismatches_without_fitting_or_dropping_them(
    jiajing, monkeypatch
):
    calendar = copy.deepcopy(jiajing["calendar"])
    calendar["months"][6]["length_days"] += 1
    calendar["months"][6]["sexagenary_start_day"] = "乙丑"
    monkeypatch.setattr(audit, "gujin_fixed_qice_year", lambda _: calendar)
    result = audit.compare_official_calendar("jiajing3_1524_wdl108")
    assert result["counts"]["mismatches"] == 2
    assert result["counts"]["matches"] == 24
    assert result["status"] == "reference_mismatches_present"
    assert [
        r["reference"] for r in result["comparisons"] if r["status"] == "mismatches"
    ] == [29, "甲子"]
    assert not result["parameters_selected_by_reference_fit"]


def test_missing_computed_month_does_not_become_reference_failure(jiajing, monkeypatch):
    calendar = copy.deepcopy(jiajing["calendar"])
    calendar["months"].pop(4)
    monkeypatch.setattr(audit, "gujin_fixed_qice_year", lambda _: calendar)
    result = audit.compare_official_calendar("jiajing3_1524_wdl108")
    assert result["counts"]["computed_unavailable"] == 2
    assert result["counts"]["mismatches"] == 0
    assert result["status"] == "required_calculation_unavailable"


def test_all_unknown_reference_is_not_vacuous_agreement(tmp_path, monkeypatch):
    data = json.loads(audit.DATA.read_bytes())
    for case in data["cases"]:
        case["calendar_month_count"] = case["calendar_total_days"] = None
        for month in case["months"]:
            month["length_days"] = month["sexagenary_start_day"] = None
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(audit, "DATA", path)
    result = audit.compare_official_calendar("jiajing3_1524_wdl108")
    assert result["counts"]["matches"] == 0
    assert result["counts"]["reference_unreadable_or_unprovided"] == 26
    assert result["status"] == "no_readable_reference_fields"


@pytest.mark.parametrize("bad", [None, 243, True, 88753.8789, "88753.8789"])
def test_nonexact_year_input_never_coerced(bad):
    with pytest.raises(TypeError):
        year.gujin_fixed_qice_year(bad)


def test_negative_middle_and_unknown_reference_are_rejected():
    with pytest.raises(ValueError):
        year.gujin_fixed_qice_year(F(-1))
    with pytest.raises(ValueError):
        audit.compare_official_calendar("highest_matching_year")


@pytest.mark.parametrize("elapsed", [31, 296])
def test_actual_empty_endpoint_years_remain_unassigned(elapsed):
    result = year.gujin_fixed_qice_year(shoushi_winter_cycle(elapsed).zhongji_days)
    assert result["reason"] == "first_winter_cycle_unresolved"
    base = result["first_winter_cycle"]
    assert base["month_assignment"]["missing_conjunction_indices"] == [10]
    assert (
        base["conjunction_candidates"][10]["lunar_velocity"]["whole_limit_index"] == 168
    )
    assert not result["complete_named_year_assigned"]


@pytest.mark.parametrize(
    "start,stop,error",
    [
        (True, 3, TypeError),
        (0, 3.0, TypeError),
        (-1, 3, ValueError),
        (3, 3, ValueError),
    ],
)
def test_grid_range_is_not_coerced_or_reordered(start, stop, error):
    with pytest.raises(error):
        audit.audit_named_year_grid(start, stop)


def test_grid_keeps_all_inputs_and_does_not_certify_external_accuracy():
    grid = audit.audit_named_year_grid(30, 33)
    assert grid["input_years"] == 3 and grid["input_years_dropped"] == 0
    assert [r["elapsed_years"] for r in grid["rows"]] == [30, 31, 32]
    assert [r["elapsed_years"] for r in grid["unresolved"]] == [31]
    assert grid["counts"] == {
        "complete_under_named_fixed_qice_policy": 2,
        "partial_calendar_year": 1,
    }
    diagnostic = grid["unresolved"][0]["missing_first_cycle_conjunction_diagnostics"][0]
    assert diagnostic["lunation_index"] == 10 and diagnostic["whole_limit_index"] == 168
    assert grid["status"] == "internal_coverage_only_not_external_accuracy"
    assert not grid["complete_historical_calendar_accepted"]
    assert not grid["real_world_prediction_validated"]
