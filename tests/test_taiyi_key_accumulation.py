"""A worked passage must not be promoted to a universal calendar or encoding."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from scripts.audit_taiyi_key_accumulation import (
    CORPUS,
    ROOT,
    audit,
    grouped_myriads,
    verify_sources,
    worked_trace,
)


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    return audit()


@pytest.mark.parametrize(
    "groups,value",
    [
        ([157, 4913, 8742], 15749138742),
        ([346, 8646, 6759], 34686466759),
        ([7, 788, 7076], 707887076),
    ],
)
def test_explicit_myriad_groups_keep_large_numerals(
    groups: list[int], value: int
) -> None:
    assert grouped_myriads(groups) == value


@pytest.mark.parametrize("groups", [[], [True], [10000], [-1], [1, 2.5]])
def test_no_implicit_or_noncanonical_myriad_group(groups: list[int]) -> None:
    with pytest.raises(ValueError):
        grouped_myriads(groups)


@pytest.mark.parametrize("years", [True, 0, -1, 1938117.5])
def test_worked_trace_rejects_nonintegral_or_invalid_years(years: int) -> None:
    with pytest.raises(ValueError):
        worked_trace(years)


def test_all_seven_printed_intermediates_match_previous_year_only(
    report: dict[str, Any],
) -> None:
    previous, same_year = report["worked_arithmetic_hypotheses"]
    assert previous["matching_numeric_fields"] == 7
    assert len(previous["printed_numeric_observations"]) == 7
    assert same_year["matching_numeric_fields"] == 0
    assert previous["actual"]["accumulated_lunations"] == 23971291
    assert previous["actual"]["counted_lunations_with_six_months"] == 23971297
    assert previous["actual"]["chapter_remainder"] == 555
    assert previous["actual"]["day_small_remainder"] == 35
    assert (
        previous["actual"]["chapter_remainder_denominator"]
        != previous["actual"]["day_denominator"]
    )


def test_month_and_day_tokens_require_different_local_origins(
    report: dict[str, Any],
) -> None:
    encodings = report["worked_arithmetic_hypotheses"][0]["counter_encodings"]
    matches = [r for r in encodings if r["both_match"]]
    assert len(encodings) == 4 and len(matches) == 1
    assert matches[0]["month_jiazi_origin"] == 1
    assert matches[0]["day_jiazi_origin"] == 0
    assert not matches[0]["universal_encoding_selected"]
    assert not report["universal_day_or_month_counter_encoding_adjudicated"]


def test_ambiguous_cycle_divisor_not_silently_assumed360(
    report: dict[str, Any],
) -> None:
    readings = report["worked_arithmetic_hypotheses"][0]["remainder_readings"]
    assert [r["divisor"] for r in readings] == [60, 360]
    assert (readings[0]["month_remainder"], readings[0]["day_remainder"]) == (30, 56)
    assert (readings[1]["month_remainder"], readings[1]["day_remainder"]) == (330, 356)
    assert all(not r["source_divisor_adjudicated"] for r in readings)


def test_new_historical_calendar_is_a_full_year_not_only_matching_may(
    report: dict[str, Any],
) -> None:
    controls = report["full_printed_calendar_controls"]
    assert len(controls) == report["source_firsts"] == 14
    assert sum(c["month_days"] or 0 for c in controls) == report["source_days"] == 384
    assert [
        c["source"]["month"] for c in controls[:-1] if c["source"]["is_leap_month"]
    ] == [5]
    assert all(
        c["cycle_matches"] and c["week_matches"] and c["length29_or30"]
        for c in controls
    )
    may = next(
        c
        for c in controls
        if c["source"]["month"] == 5 and not c["source"]["is_leap_month"]
    )
    assert may["source"]["julian_start"] == "1561-05-14"
    assert may["gregorian_start"] == "1561-05-24"
    assert report["may1_printed_calendar_ganzhi"] == "庚申"


def test_matching_worked_number_does_not_override_wrong_month_identity(
    report: dict[str, Any],
) -> None:
    series = next(
        s
        for s in report["conditional_full_year_series"]
        if s["moon_year_shift"] == -1
        and s["middle_term_assignment"] == "civil_day"
        and s["initial_quotient_encoding"] == "completed_days"
    )
    number_matches = [
        r
        for w in series["windows"]
        for r in w["records"]
        if r["raw_quotient"] == 707887076
    ]
    assert len(number_matches) == 1 and number_matches[0]["month"] == 4
    may = next(
        m
        for m in series["source_months"]
        if m["source"]["month"] == 5 and not m["source"]["is_leap_month"]
    )
    assert may["actual"]["raw_quotient"] != 707887076
    assert not may["first_matches"]
    assert not series["full_observed_year_matches"]


def test_eight_complete_failed_cohorts_and_unknowns_survive(
    report: dict[str, Any],
) -> None:
    assert len(report["conditional_full_year_series"]) == 8
    for s in report["conditional_full_year_series"]:
        assert len(s["source_months"]) == 14
        assert len(s["source_days"]) == 384
        assert not s["full_observed_year_matches"]
        if s["moon_year_shift"] == 0:
            assert s["available_month_identities"] == 0
            assert all(
                d["ordinal_exists"] is None and d["actual_day_ganzhi"] is None
                for d in s["source_days"]
            )
    assert not report["any_series_matches_full_observed_year"]
    assert not report["whole_goal_complete"]
    assert not report["wang_and_key_absolute_epoch_identity_adjudicated"]


def test_public_adapter_difference_is_measured_without_changing_epoch(
    report: dict[str, Any],
) -> None:
    observed = report["public_month_adapter_observations"]
    assert len(observed) == 4
    may = [a for a in observed if a["input"]["analysis_month"] == 5]
    assert all(a["source_month4_overlap_verified"] for a in may)
    assert may[0]["raw_difference_from_source_month_counter"] == 0
    assert may[0]["cycle360_matches_source_month_counter"] is True
    assert may[1]["raw_difference_from_source_month_counter"] == 98608320
    assert may[1]["cycle360_matches_source_month_counter"] is True
    assert all(
        a["cycle360_matches_source_month_counter"] is None
        for a in observed
        if a["input"]["analysis_month"] == 6
    )
    assert all(
        not a["absolute_epoch_identity_inferred_from_cycle_match"] for a in observed
    )
    assert report["new_public_provider_or_formula_change"]


def test_no_nonexistent_date_gets_full_match(report: dict[str, Any]) -> None:
    invalid = [
        d
        for s in report["conditional_full_year_series"]
        for d in s["source_days"]
        if d["label_matches"] and d["ordinal_exists"] is False
    ]
    assert invalid and all(not d["full_date_matches"] for d in invalid)


def test_old_failed_reports_stay_false_and_pinned(report: dict[str, Any]) -> None:
    assert len(report["previous_evidence"]) == 2
    assert all(
        not p["whole_goal_complete"] for p in report["previous_evidence"].values()
    )
    assert report["new_complete_dated_taiyi_boards_passed"] == 0
    assert report["new_model_invocations"] == 0
    assert len(verify_sources()["prior_sources"]) == 11


@pytest.mark.parametrize("rewrite_freeze", [False, True])
def test_cannot_make_source_pass_by_changing_an_intermediate(
    tmp_path: Path, rewrite_freeze: bool
) -> None:
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    path = corpus / "readings.json"
    obj = json.loads(path.read_text())
    obj["observed"]["completed_year_count"] += 1
    path.write_text(json.dumps(obj))
    if rewrite_freeze:
        freeze = json.loads((corpus / "freeze.json").read_text())
        freeze["files"]["readings.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (corpus / "freeze.json").write_text(json.dumps(freeze))
    with pytest.raises(ValueError, match="V39"):
        verify_sources(corpus, root=ROOT)
