"""Real missed joint state, closed-form event fixtures and forged trace claims."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design import chart_at, chart_at_tt
from fatebridge.core.human_design_joint import JointSnapshotCache
from fatebridge.core.human_design_sensitivity import assess_birth_interval
from fatebridge.core.human_design_transition import (
    dependency_projection,
    refine_joint_transitions,
)
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from fatebridge.validation.human_design_transition import verify_transition_trace
from tests.golden.runner import golden_ephemeris

ROOT = Path(__file__).resolve().parents[1]
CASE = json.loads(
    (ROOT / "tests/fixtures/human-design-transition-case.json").read_text()
)
SPEC = next(s for s in CATALOG if s.key == "human_design")
MOMENT = datetime.fromisoformat(CASE["nominal_birth_utc"])
INPUT = dict(
    birth_year=MOMENT.year,
    birth_month=MOMENT.month,
    birth_day=MOMENT.day,
    birth_hour=MOMENT.hour,
    birth_minute=MOMENT.minute,
    birth_timezone="UTC",
    birth_time_uncertainty_minutes=1,
)


def test_frozen_search_and_old_missed_state_are_not_replaced_by_new_expectations():
    plan = ROOT / CASE["plan_path"]
    assert hashlib.sha256(plan.read_bytes()).hexdigest() == CASE["plan_sha256"]
    assert CASE["search_samples_checked"] == 207349
    assert CASE["legacy_grid_sample_count"] == 13
    assert CASE["legacy_joint_variant_count"] == 2
    assert CASE["legacy_joint_key_absent"] is True


def test_actual_ten_second_alias_retains_the_missing_coherent_state_with_one_extra_chart():
    with golden_ephemeris():
        nominal = chart_at(MOMENT)
        result = assess_birth_interval(nominal, 1, "true")
        missed = chart_at_tt(CASE["missed_witness_tt"], backend="moshier")
    from scripts.audit_human_design import transition_fixture_diagnostics

    for label, chart in [("nominal", nominal), ("missed", missed)]:
        comparison = transition_fixture_diagnostics(
            chart["activations"], CASE["physical_samples"][label]["activations"]
        )
        assert comparison["discrete_fields_equal"]
        assert comparison["positions_within_existing_reference_tolerances"]
        frozen = CASE["physical_samples"][label]["time_scales"]
        assert (
            chart["time_scales"]["personality"]["jd_tt"]
            == frozen["personality"]["jd_tt"]
        )
        assert (
            abs(chart["time_scales"]["design"]["jd_tt"] - frozen["design"]["jd_tt"])
            * 86400
            <= 0.0002
        )
    assert len(result["classification_variants"]) == 3
    assert result["sampling"]["grid_sample_count"] == 13
    assert result["sampling"]["total_evaluation_count"] == 14
    assert (
        result["joint_transition_refinement_summary"]["additional_evaluation_count"]
        == 1
    )
    key = JointSnapshotCache().key(missed)
    assert key in {
        JointSnapshotCache().key(r["value"]) for r in result["classification_variants"]
    }
    assert result["sampling"]["continuous_interval_certified"] is False
    assert (
        verify_transition_trace(
            result["joint_transition_refinement"],
            result["classification_variants"],
            result["sampling"],
            nominal["time_scales"]["personality"]["jd_tt"],
            60,
            10,
        )["status"]
        == "verified_local_refinement_trace"
    )


def synthetic(first=4.0, second=4.25, *, same_source=False, reversal=False):
    """Known artificial step times, never used as physical celestial evidence."""
    origin = 2450000.5
    calls = []
    cache = {}

    def at(jd):
        if jd not in cache:
            calls.append(jd)
            chart = copy.deepcopy(CASE["physical_samples"]["nominal"])
            t = (jd - origin) * 86400
            bodies = {a["body"]: a for a in chart["activations"]["personality"]}
            if same_source:
                if t >= first:
                    for body in ("Sun", "Earth"):
                        bodies[body]["line"] = bodies[body]["line"] % 6 + 1
                        bodies[body]["tone"] = bodies[body]["tone"] % 6 + 1
            else:
                for body, boundary in [("Moon", first), ("Mercury", second)]:
                    if t >= boundary and (not reversal or t < 6):
                        bodies[body]["line"] = bodies[body]["line"] % 6 + 1
            cache[jd] = chart
        return cache[jd]

    for offset in range(-60, 61, 10):
        at(origin + offset / 86400)
    calls.clear()
    result = refine_joint_transitions(cache, at)
    unique = {}
    for chart in cache.values():
        unique[dependency_projection(chart["activations"])] = chart
    variants = [{"value": {"activations": v["activations"]}} for v in unique.values()]
    sampling = {
        "grid_sample_count": 13,
        "total_evaluation_count": len(cache),
        "additional_evaluation_count": len(cache) - 13,
    }
    return result, variants, sampling, calls, origin


def test_close_distinct_dependency_steps_are_not_merged_or_mixed():
    result, variants, sampling, calls, origin = synthetic()
    assert len(variants) == 3
    assert any(4 < (t - origin) * 86400 < 4.25 for t in calls)
    assert result["summary"]["candidate_interval_count"] == 1
    assert result["summary"]["unresolved_multiple_dependency_brackets"] == 0
    assert (
        verify_transition_trace(result, variants, sampling, origin, 60, 10)["status"]
        == "verified_local_refinement_trace"
    )


def test_unseparated_steps_are_reported_without_claiming_exact_simultaneity():
    result, variants, sampling, calls, origin = synthetic(4, 4)
    assert len(variants) == 2
    assert result["summary"]["unresolved_multiple_dependency_brackets"] == 1
    assert result["summary"]["status"] == "some_multiple_dependency_brackets_unresolved"
    assert any(n["outcome"] == "unseparated_at_TT_resolution" for n in result["nodes"])
    assert (
        verify_transition_trace(result, variants, sampling, origin, 60, 10)["status"]
        == "verified_local_refinement_trace"
    )


def test_budget_exhaustion_retains_unresolved_brackets_instead_of_false_success(
    monkeypatch,
):
    from fatebridge.core import human_design_transition as core
    from fatebridge.validation import human_design_transition as validation

    monkeypatch.setattr(core, "MAX_ADDITIONAL_EVALUATIONS", 1)
    monkeypatch.setattr(validation, "MAX_ADDITIONAL_EVALUATIONS", 1)
    result, variants, sampling, calls, origin = synthetic(4, 4.0001)
    assert len(calls) == 1
    assert result["summary"]["unresolved_multiple_dependency_brackets"] == 1
    assert any(n["outcome"] == "evaluation_budget_exhausted" for n in result["nodes"])
    assert result["summary"]["continuous_interval_certified"] is False
    assert (
        verify_transition_trace(result, variants, sampling, origin, 60, 10)["status"]
        == "verified_local_refinement_trace"
    )


def test_paired_opposition_and_same_body_line_tone_do_not_create_two_independent_events():
    result, variants, sampling, calls, origin = synthetic(same_source=True)
    assert result["summary"]["candidate_interval_count"] == 0
    assert calls == []
    assert len(variants) == 2
    assert (
        verify_transition_trace(result, variants, sampling, origin, 60, 10)["status"]
        == "verified_local_refinement_trace"
    )


def test_unobserved_reversal_does_not_become_a_stability_certificate():
    result, variants, _, calls, _ = synthetic(reversal=True)
    assert len(variants) == 1 and calls == []
    assert result["summary"]["status"] == "no_multiple_dependency_change_observed"
    assert result["summary"]["continuous_interval_certified"] is False


@pytest.fixture(scope="module")
def full_run():
    with golden_ephemeris():
        result = execute_tool(SPEC, SPEC.request_model(**INPUT))
    assert (
        verify_human_design_reading(result)["status"]
        == "verified_fixed_template_reading"
    )
    return result


@pytest.mark.parametrize(
    "bad",
    [
        "midpoint",
        "root",
        "seed",
        "state",
        "unreachable",
        "count",
        "certificate",
        "summary_alias",
        "bool_id",
        "tone",
        "order",
        "unresolved",
        "outcome",
    ],
)
def test_fresh_hash_does_not_accept_forged_finite_refinement_evidence(full_run, bad):
    value = copy.deepcopy(full_run)
    interval = value["time_sensitivity"]
    report = interval["joint_transition_refinement"]
    if bad == "midpoint":
        report["nodes"][0]["midpoint_tt"] += 1 / 86400
    elif bad == "root":
        report["roots"] = []
    elif bad == "seed":
        report["initial_samples"].pop(0)
    elif bad == "state":
        report["states"].pop()
    elif bad == "unreachable":
        report["nodes"].append(copy.deepcopy(report["nodes"][-1]))
    elif bad == "count":
        report["summary"]["additional_evaluation_count"] += 1
    elif bad == "certificate":
        report["summary"]["continuous_interval_certified"] = True
    elif bad == "summary_alias":
        interval["joint_transition_refinement_summary"] = {"status": "stable"}
    elif bad == "bool_id":
        report["initial_samples"][0][1] = False
    elif bad == "tone":
        report["states"][0][1][2] = 1
    elif bad == "order":
        report["dependency_order"].reverse()
    elif bad == "unresolved":
        report["summary"]["unresolved_multiple_dependency_brackets"] = 1
    else:
        report["nodes"][0]["outcome"] = "proven_continuous_stability"
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(value)["status"] == "rejected"


def test_unassessed_interval_cannot_acquire_a_refinement_claim():
    with golden_ephemeris():
        value = execute_tool(
            SPEC, SPEC.request_model(**{**INPUT, "birth_time_uncertainty_minutes": 0})
        )
    assert value["time_sensitivity"]["joint_transition_refinement"] is None
    assert value["time_sensitivity"]["joint_transition_refinement_summary"] is None
    value["time_sensitivity"]["joint_transition_refinement_summary"] = {
        "status": "stable"
    }
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    assert verify_human_design_reading(value)["status"] == "rejected"


def test_audit_rejects_a_degraded_checker_that_drops_the_missed_state(monkeypatch):
    from scripts import audit_human_design as audit

    assert (
        audit.transition_regression_checks()["status"]
        == "observed_transition_regression_passed"
    )
    original = audit.assess_birth_interval
    missed = JointSnapshotCache().key(CASE["physical_samples"]["missed"])

    def degraded(*args, **kwargs):
        result = original(*args, **kwargs)
        result["classification_variants"] = [
            r
            for r in result["classification_variants"]
            if JointSnapshotCache().key(r["value"]) != missed
        ]
        return result

    monkeypatch.setattr(audit, "assess_birth_interval", degraded)
    result = audit.transition_regression_checks()
    assert result["status"] == "failed"
    assert result["missed_witness_recovered"] is False
    assert result["trace_verification"]["status"] == "rejected"


def test_float_replay_drift_is_reported_instead_of_being_called_exact():
    from scripts.audit_human_design import transition_fixture_diagnostics

    frozen = CASE["physical_samples"]["nominal"]["activations"]
    current = copy.deepcopy(frozen)
    current["personality"][0]["longitude"] += 1e-9
    result = transition_fixture_diagnostics(current, frozen)
    assert result["raw_activations_equal"] is False
    assert result["raw_float_differences"]
    assert result["discrete_fields_equal"] is True
    assert result["positions_within_existing_reference_tolerances"] is True
    assert result["speed_accuracy_certified"] is False


@pytest.mark.parametrize("body,delta", [("Moon", 3), ("NorthNode", 1.1)])
def test_diagnostic_thresholds_cannot_accept_larger_position_errors(body, delta):
    from scripts.audit_human_design import transition_fixture_diagnostics

    frozen = CASE["physical_samples"]["nominal"]["activations"]
    current = copy.deepcopy(frozen)
    row = next(r for r in current["personality"] if r["body"] == body)
    row["longitude"] += delta / 3600
    result = transition_fixture_diagnostics(current, frozen)
    assert result["positions_within_existing_reference_tolerances"] is False
    assert result["raw_activations_equal"] is False
