"""Candidate uncertainty stays visible; shared dates never imply a unique instant."""

import copy
import hashlib
import json
import runpy
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_literal_candidates as subject
from fatebridge.core.guolao_calendar_year import gujin_fixed_qice_year
from fatebridge.core.guolao_cumulative_table import gujin_literal_lunar
from fatebridge.validation.guolao_literal_candidates import audit_literal_candidate_grid

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize(
    "within,indices",
    [
        ("7.2806", [88]),
        ("7.2807", [88, 89, 90]),
        ("7.29", [88, 89, 90]),
        ("7.2987", [89, 90]),
        ("7.2988", [90]),
        ("13.7773", [168]),
    ],
)
def test_declared_endpoint_policy_keeps_every_applicable_original_segment(
    within, indices
):
    result = subject.literal_lunar_candidates(F(within))
    assert result["candidate_limit_indices"] == indices
    assert [r["whole_limit_index"] for r in result["candidates"]] == indices
    assert not result["source_lookup_adjudicated"]
    if len(indices) > 1:
        assert result["strict_lookup"]["whole_limit_index"] is None


@pytest.mark.parametrize("slow", [False, True])
def test_independent_exact_arithmetic_preserves_negative_interpolation(slow):
    anomaly = F("7.29") + (F("13.7773") if slow else F())
    result = subject.literal_lunar_candidates(anomaly)
    # Literal cells from the existing single-collator transcription; this is
    # independent arithmetic, not a new independent textual review.
    expected_cells = [
        (88, "7.2167", "5.42560000", "-0.00479775"),
        (89, "7.2987", "5.42080225", "-0.00690025"),
        (90, "7.2807", "5.41390200", "-0.00898325"),
    ]
    data = json.loads(
        (
            ROOT / "src/fatebridge/data/guolao/gujin45-cumulative-table-v1.json"
        ).read_text()
    )
    for actual, (index, rate, base, slope) in zip(
        result["candidates"], expected_cells, strict=True
    ):
        assert actual["whole_limit_index"] == index
        # Verify the manually entered cells as well as the independent rational calculation.
        assert F(data["rows"][index]["cumulative_ancient_du"]) == F(base)
        assert F(data["rows"][index]["signed_increment_ancient_du"]) == F(slope)
        fraction = (F("7.29") - F(rate)) / F(".0820")
        expected = F(base) + F(slope) * fraction
        assert F(actual["interpolation_fraction_exact"]) == fraction
        assert F(actual["signed_correction_ancient_du_exact"]) == (
            expected if slow else -expected
        )
        assert not actual["interpolation_clipped_or_endpoint_smoothed"]
    assert F(result["candidates"][1]["interpolation_fraction_exact"]) < 0
    assert result["candidates"][1]["descending_segment_diagnostic_assumption"]


@pytest.mark.parametrize(
    "anomaly", ["0", ".041", "1.025", "12.7522", "13.7363", "13.7773", "13.8183"]
)
def test_unique_lookup_arithmetic_matches_strict_including_empty_origins_and_endpoint(
    anomaly,
):
    strict = gujin_literal_lunar(F(anomaly))
    candidate = subject.literal_lunar_candidates(F(anomaly))["candidates"]
    assert len(candidate) == 1
    for field in [
        "whole_limit_index",
        "selected_printed_day_rate_days",
        "selected_effective_day_rate_days",
        "source_selected_cumulative_ancient_du",
        "source_selected_signed_increment_ancient_du",
        "signed_correction_ancient_du_exact",
        "interpolation_fraction_exact",
        "empty_day_rate_origin_interpreted_as_zero",
        "empty_cumulative_endpoint_filled",
    ]:
        assert candidate[0][field] == strict[field]


@pytest.fixture(scope="module")
def ordinary_year():
    return subject.literal_candidate_year(F("88753.8789"))


def test_unique_branch_retains_strict_calendar_and_only_civil_shared_facts(
    ordinary_year,
):
    r = ordinary_year
    assert r["strict_calendar"] == gujin_fixed_qice_year(
        F("88753.8789"), conjunction_method="literal_table"
    )
    assert r["declared_branch_count"] == r["enumerated_branch_count"] == 1
    assert r["complete_civil_facts_identical_under_candidate_policy"]
    assert r["shared_civil_facts"]["total_days"] == 354
    for row in r["shared_civil_facts"]["months"]:
        assert "conjunction_offset_from_winter_days_exact" not in row
        assert "conjunction_day_cycle_exact" not in row
        assert "instant_interval_principal_term_indices_diagnostic" not in row
    assert not r["unique_conjunction_times_claimed"]
    for field in [
        "source_lookup_adjudicated",
        "printed_source_cells_repaired",
        "all_possible_historical_interpretations_enumerated",
        "complete_historical_calendar_accepted",
        "real_world_prediction_validated",
        "modern_epoch_calibrated",
        "used_in_native_birth_chart",
    ]:
        assert not r[field]


def test_disagreeing_branch_does_not_copy_first_but_preserves_unaffected_fields(
    ordinary_year,
):
    a = copy.deepcopy(ordinary_year["branches"][0])
    b = copy.deepcopy(a)
    b["branch_id"] = 1
    b["calendar"]["months"][0]["length_days"] += 1
    r = subject._civil_consensus([a, b])
    assert not r["complete_civil_facts_identical_under_candidate_policy"]
    month = r["shared_civil_facts"]["months"][0]
    assert month["length_days"] is None
    assert (
        month["start_source_day_integer"]
        == a["calendar"]["months"][0]["start_source_day_integer"]
    )
    assert r["shared_civil_facts"]["total_days"] == 354
    conflict = next(c for c in r["unresolved_fields"] if c["field"] == "length_days")
    assert [x["value"] for x in conflict["branch_values"]] == [30, 31]


def test_incomplete_branch_is_not_dropped_or_counted_as_whole_year_consensus(
    ordinary_year,
):
    a = copy.deepcopy(ordinary_year["branches"][0])
    b = copy.deepcopy(a)
    b["branch_id"] = 1
    b["calendar"]["complete_named_year_assigned"] = False
    b["calendar"]["months"] = b["calendar"]["months"][:2]
    r = subject._civil_consensus([a, b])
    assert not r["all_branch_years_complete"]
    assert not r["complete_civil_facts_identical_under_candidate_policy"]
    assert r["shared_civil_facts"]["month_count"] is None
    assert r["shared_civil_facts"]["total_days"] is None
    assert r["shared_civil_facts"]["months"][0]["length_days"] == 30
    assert r["shared_civil_facts"]["months"][2]["length_days"] is None


def test_missing_conjunction_branch_survives_into_unresolved_calendar(monkeypatch):
    original = subject.literal_conjunction_candidates

    def missing(middle, index):
        result = original(middle, index)
        if index == 2:
            extra = copy.deepcopy(result["candidates"][0])
            extra["research_conjunction_offset_from_winter_days_exact"] = None
            result["candidates"].append(extra)
        return result

    monkeypatch.setattr(subject, "literal_conjunction_candidates", missing)
    r = subject.literal_candidate_year(F("88753.8789"))
    assert r["declared_branch_count"] == r["enumerated_branch_count"] == 2
    assert not r["complete_civil_facts_identical_under_candidate_policy"]
    assert len(r["branches"]) == 2


def test_resource_limit_never_truncates_to_success(monkeypatch):
    monkeypatch.setattr(subject, "MAX_BRANCHES", 0)
    r = subject.literal_candidate_year(F("88753.8789"))
    assert r["status"] == "branch_limit_exceeded_unresolved"
    assert r["declared_branch_count"] == 1 and r["enumerated_branch_count"] == 0
    assert r["shared_civil_facts"] is None and not r["branches"]
    assert not r["complete_civil_facts_identical_under_candidate_policy"]


@pytest.mark.parametrize("value", [0, 0.1, "1"])
def test_nonfraction_input_rejected(value):
    with pytest.raises(TypeError):
        subject.literal_candidate_year(value)


@pytest.mark.parametrize("start,stop", [(0, 0), (-1, 1), (0, 401), (True, 2), (0, 2.0)])
def test_bad_grid_not_silently_changed(start, stop):
    with pytest.raises(ValueError):
        audit_literal_candidate_grid(start, stop)


def test_cli_exposes_diagnostic_policy_without_upgrading_strict_method(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        sys, "argv", ["audit_guolao_literal_candidates.py", "--anomaly-days", "7.29"]
    )
    module = runpy.run_path(
        str(ROOT / "scripts/guolao/audit_guolao_literal_candidates.py")
    )
    assert module["main"]() == 0
    r = json.loads(capsys.readouterr().out)
    assert r["candidate_limit_indices"] == [88, 89, 90]
    assert r["strict_lookup"]["whole_limit_index"] is None


def test_declared_policy_precedes_grid_and_does_not_claim_blinding():
    p = (
        ROOT
        / "tests/fixtures/guolao-literal-candidates-v1/policy-before-evaluation.json"
    )
    raw = p.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "b4a7989824601dbe2df263b7418891b9745a5a53c9c844b1bdee62cd8db8e0c8"
    )
    policy = json.loads(raw)
    assert "no claim of blinding" in policy["prior_knowledge"]
    assert not policy["independent_acceptance"]
    assert policy["empirical_subjects"] == 0


def test_empty_branch_set_cannot_be_vacuously_unanimous():
    with pytest.raises(ValueError):
        subject._civil_consensus([])


def test_next_year_boundary_keeps_agreed_fields_when_one_fact_differs(ordinary_year):
    a = copy.deepcopy(ordinary_year["branches"][0])
    b = copy.deepcopy(a)
    b["branch_id"] = 1
    b["calendar"]["next_regular_first_month"]["start_source_day_integer"] += 1
    r = subject._civil_consensus([a, b])
    boundary = r["shared_civil_facts"]["next_regular_first_month"]
    assert boundary["start_source_day_integer"] is None
    assert boundary["month_number"] == 1
    assert boundary["is_leap_month"] is False
    assert not r["complete_civil_facts_identical_under_candidate_policy"]
