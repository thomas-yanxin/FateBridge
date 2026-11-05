"""Hand-computed pairs, enumerated missingness and closed-form logit MLE."""

import itertools
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from statistics import NormalDist
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from fatebridge.validation.guolao_career import (
    CareerOutcome,
    CareerStudyPlan,
    PairedCareerForecast,
    _brier_difference,
    _calibration_fit,
    _metrics,
    _paired_bootstrap,
    analysis_code_fingerprint,
    evaluate_career_study,
)
from fatebridge.validation.predictions import digest

AS_OF = datetime(2028, 2, 1, tzinfo=timezone.utc)


def plan(n=3, **changes):
    cohort = [
        {"case_id": str(i), "subject_id": f"synthetic-subject-{i}"} for i in range(n)
    ]
    data = {
        "study_id": "synthetic-career-test-not-a-real-study",
        "data_kind": "synthetic",
        "target_definition": "formal_role_change_or_promotion_in_fixed_window",
        "preregistered_at": "2026-11-01T00:00:00Z",
        "registration_reference": "synthetic:registration-not-real-evidence",
        "window_start": "2027-01-01T00:00:00Z",
        "window_end": "2028-01-01T00:00:00Z",
        "models_frozen_at": "2026-10-30T00:00:00Z",
        "model_sha256": "a" * 64,
        "baseline_model_sha256": "b" * 64,
        "interpretation_policy_sha256": "c" * 64,
        "analysis_code_sha256": analysis_code_fingerprint(),
        "cohort_sha256": digest(cohort),
        "training_subject_ids": [],
        "power_analysis_reference": "synthetic:power-not-real-evidence",
        "power_analysis_sha256": "d" * 64,
        "minimum_evaluable": 2,
        "minimum_brier_improvement": 0.0,
        "cohort": cohort,
    }
    return CareerStudyPlan.model_validate({**data, **changes})


def forecast(i, p, baseline=0.5, **changes):
    data = {
        "case_id": str(i),
        "issued_at": "2026-12-01T00:00:00Z",
        "information_cutoff_at": "2026-11-30T00:00:00Z",
        "model_sha256": "a" * 64,
        "baseline_model_sha256": "b" * 64,
        "interpretation_policy_sha256": "c" * 64,
        "evidence_sha256": "e" * 64,
        "baseline_reality_input_sha256": "f" * 64,
        "augmented_reality_input_sha256": "f" * 64,
        "independent_timestamp_reference": "synthetic:timestamp-not-real-evidence",
        "baseline_probability": baseline,
        "probability": p,
        "abstention_reason": "synthetic explicit abstention" if p is None else None,
    }
    return PairedCareerForecast.model_validate({**data, **changes})


def outcome(i, y, **changes):
    data = {
        "case_id": str(i),
        "occurred": y,
        "event_at": "2027-06-01T00:00:00Z" if y else None,
        "recorded_at": "2028-01-02T00:00:00Z",
        "source_sha256": "1" * 64,
        "source_reference": "synthetic:source",
        "subtype": "promotion" if y else None,
        "window_complete_through": "2028-01-01T00:00:00Z",
        "blinded_to_forecasts": True,
        "adjudication_reference": "synthetic:adjudication",
    }
    return CareerOutcome.model_validate({**data, **changes})


def evaluate(p, f, o, **changes):
    return evaluate_career_study(p, f, o, as_of=changes.get("as_of", AS_OF))


def test_hand_scores_include_abstention_at_its_person_specific_baseline():
    report = evaluate(
        plan(),
        [forecast(0, 0.9, 0.4), forecast(1, 0.8, 0.3), forecast(2, None, 0.2)],
        [outcome(0, True), outcome(1, False), outcome(2, True)],
    )
    assert report["baseline"]["brier_score"] == pytest.approx(1.09 / 3)
    assert report["augmented_with_baseline_for_abstentions"][
        "brier_score"
    ] == pytest.approx(1.29 / 3)
    assert report["primary"]["mean_paired_brier_difference"] == pytest.approx(0.2 / 3)
    assert report["rows"][2]["paired_brier_difference"] == 0
    assert report["rows"][2]["effective_augmented_probability"] == 0.2
    assert report["explicit_abstention_count"] == 1
    assert report["nonabstaining_forecast_coverage"] == 2 / 3
    assert report["observed_pair_count"] == 3
    assert not report["primary"]["prespecified_sample_comparison_passed"]


def test_sharp_full_cohort_bounds_match_all_binary_completions():
    submitted = [forecast(0, 0.9, 0.4), forecast(1, 0.8, 0.3), forecast(2, None, 0.2)]
    report = evaluate(plan(), submitted, [outcome(0, True)])
    completed = []
    for y1, y2 in itertools.product((0, 1), repeat=2):
        completed.append(
            (
                (0.9 - 1) ** 2
                - (0.4 - 1) ** 2
                + (0.8 - y1) ** 2
                - (0.3 - y1) ** 2
                + (0.2 - y2) ** 2
                - (0.2 - y2) ** 2
            )
            / 3
        )
    assert report["primary"]["full_cohort_identification_bounds"] == pytest.approx(
        [min(completed), max(completed)]
    )
    assert report["outcome_pair_coverage"] == 1 / 3
    assert report["rows"][1]["status"] == "outcome_pending"
    assert not report["primary"]["prespecified_sample_comparison_passed"]


def test_missing_forecast_is_not_converted_to_an_explicit_abstention():
    report = evaluate(plan(2), [forecast(0, 0.9)], [outcome(0, True), outcome(1, True)])
    assert report["rows"][1]["status"] == "missing_forecast"
    assert not report["rows"][1]["abstained"]
    assert report["explicit_abstention_count"] == 0
    assert report["primary"]["full_cohort_identification_bounds"] == pytest.approx(
        [(-0.24 - 1) / 2, (-0.24 + 1) / 2]
    )


def test_empty_records_have_no_score_or_fictitious_effectiveness():
    report = evaluate(plan(), [], [])
    assert report["primary"]["mean_paired_brier_difference"] is None
    assert report["primary"]["uncertainty"]["interval"] is None
    assert report["primary"]["full_cohort_identification_bounds"] == [-1, 1]
    assert report["real_world_efficacy"] == "not_tested"
    assert not report["authority_certified"]


def test_pending_window_never_scores_partial_outcomes():
    report = evaluate(
        plan(),
        [forecast(i, 0.6) for i in range(3)],
        [outcome(i, True) for i in range(3)],
        as_of=datetime(2027, 6, 2, tzinfo=timezone.utc),
    )
    assert report["observed_pair_count"] == 0
    assert all(r["status"] == "window_pending" for r in report["rows"])


def test_future_entered_result_stays_pending_at_analysis_cutoff():
    report = evaluate(
        plan(2),
        [forecast(0, 0.7), forecast(1, 0.8)],
        [outcome(0, True), outcome(1, False, recorded_at="2029-01-01T00:00:00Z")],
    )
    assert report["observed_pair_count"] == 1
    assert report["rows"][1]["status"] == "outcome_pending"


@pytest.mark.parametrize(
    "change",
    [
        {"issued_at": "2027-01-01T00:00:00Z"},
        {"issued_at": "2026-10-31T23:59:59Z"},
        {"model_sha256": "2" * 64},
        {"baseline_model_sha256": "2" * 64},
        {"interpretation_policy_sha256": "2" * 64},
        {"case_id": "unregistered"},
    ],
)
def test_leakage_and_model_substitution_are_rejected(change):
    with pytest.raises(ValueError):
        evaluate(plan(), [forecast(0, 0.5, **change)], [])


@pytest.mark.parametrize(
    "change",
    [
        {"augmented_reality_input_sha256": "0" * 64},
        {"information_cutoff_at": "2027-01-01T00:00:00Z"},
        {"abstention_reason": "claiming abstention with a numeric forecast"},
        {"probability": float("nan")},
        {"baseline_probability": True},
    ],
)
def test_forecast_cannot_change_information_set_or_hide_probability_type(change):
    with pytest.raises(ValidationError):
        (
            forecast(0, 0.5, **change)
            if "probability" not in change
            else forecast(0, change["probability"])
        )


def test_missing_abstention_reason_and_registration_draft_do_not_run():
    with pytest.raises(ValidationError):
        forecast(0, None, abstention_reason=None)
    with pytest.raises(ValidationError):
        CareerStudyPlan.model_validate({"state": "draft_not_registered_no_data"})


def test_train_overlap_code_change_and_duplicate_records_are_rejected():
    with pytest.raises(ValidationError):
        plan(training_subject_ids=["synthetic-subject-0"])
    with pytest.raises(ValueError):
        evaluate(plan(analysis_code_sha256="0" * 64), [], [])
    with pytest.raises(ValueError):
        evaluate(plan(), [forecast(0, 0.7), forecast(0, 0.6)], [])
    with pytest.raises(ValueError):
        evaluate(plan(), [], [outcome(0, True), outcome(0, False)])


@pytest.mark.parametrize(
    "change",
    [
        {"event_at": "2028-01-01T00:00:00Z"},
        {"event_at": "2026-12-31T23:59:59Z"},
        {"window_complete_through": "2027-05-31T23:59:59Z"},
        {
            "recorded_at": "2027-12-31T23:59:59Z",
            "window_complete_through": "2027-12-31T23:59:59Z",
        },
    ],
)
def test_window_endpoints_and_incomplete_followup_are_rejected(change):
    with pytest.raises(ValueError):
        evaluate(plan(), [], [outcome(0, True, **change)])


def test_event_at_inclusive_start_is_valid_but_unblinded_declaration_blocks_gate():
    report = evaluate(
        plan(2),
        [forecast(0, 0.9), forecast(1, 0.8)],
        [
            outcome(
                0, True, event_at="2027-01-01T00:00:00Z", blinded_to_forecasts=False
            ),
            outcome(1, False),
        ],
    )
    assert report["protocol_blockers"] == ["declared_unblinded_outcome:0"]
    assert not report["primary"]["prespecified_sample_comparison_passed"]


def test_analytic_logit_calibration_intercept_slope_and_information_intervals():
    # Three independent binomial groups have event rates exactly generated by
    # logit(rate)=log(2)+logit(p); score equations vanish at a=log(2), b=1.
    pairs = [
        (p, int(i < events))
        for p, events in [(0.2, 3), (0.5, 6), (0.8, 8)]
        for i in range(9)
    ]
    fit = _calibration_fit(pairs)
    assert fit["status"] == "finite_MLE"
    assert fit["intercept"] == pytest.approx(math.log(2), abs=1e-8)
    assert fit["slope"] == pytest.approx(1, abs=1e-8)
    z = NormalDist().inv_cdf(0.975)
    assert fit["intervals"]["intercept"] == pytest.approx(
        [math.log(2) - z * math.sqrt(13 / 58), math.log(2) + z * math.sqrt(13 / 58)],
        abs=1e-7,
    )
    assert fit["intervals"]["slope"] == pytest.approx(
        [
            1 - z * math.sqrt(11 / (29 * math.log(4) ** 2)),
            1 + z * math.sqrt(11 / (29 * math.log(4) ** 2)),
        ],
        abs=1e-7,
    )


@pytest.mark.parametrize(
    "pairs,status",
    [
        ([], "no_observed_pairs"),
        ([(0.0, 0), (0.5, 1)], "undefined_endpoint_probabilities_no_clipping"),
        ([(0.3, 1), (0.7, 1)], "single_outcome_class_no_finite_MLE"),
        ([(0.5, 0), (0.5, 1)], "rank_deficient_constant_probability"),
        ([(0.2, 0), (0.8, 1)], "complete_or_quasi_separation_no_finite_MLE"),
        (
            [(0.2, 0), (0.5, 0), (0.5, 1), (0.8, 1)],
            "complete_or_quasi_separation_no_finite_MLE",
        ),
    ],
)
def test_calibration_does_not_manufacture_finite_coefficients(pairs, status):
    r = _calibration_fit(pairs)
    assert r["status"] == status and r["intercept"] is None and r["slope"] is None


def test_calibration_bins_use_both_sides_of_float_boundaries_and_empty_nulls():
    pairs = [(math.nextafter(0.3, -math.inf), 0), (0.3, 1), (1.0, 1)]
    bins = _metrics(pairs, 0.5)["calibration_bins"]
    assert len(bins) == 10
    assert [b["count"] for b in bins] == [0, 0, 1, 1, 0, 0, 0, 0, 0, 1]
    assert bins[0]["observed_rate"] is None and bins[0]["mean_probability"] is None
    assert bins[9]["upper_inclusive"]


def test_paired_bootstrap_is_reproducible_and_degenerate_bca_stays_undefined():
    a = _paired_bootstrap([-0.3, 0.2, -0.1, 0.4])
    b = _paired_bootstrap([-0.3, 0.2, -0.1, 0.4])
    assert a == b and a["status"] == "computed"
    assert a["resamples"] == 10000 and a["seed"] == 20261022
    assert a["interval"][0] < 0.05 < a["interval"][1]
    degenerate = _paired_bootstrap([-0.2] * 5)
    assert degenerate["interval"] is None
    assert degenerate["status"] == "degenerate_observed_losses_BCa_undefined"


def test_bca_against_independent_frozen_scipy_component_reference():
    fixture = json.loads(
        (
            Path(__file__).parents[1]
            / "fixtures/guolao-career-statistics-reference.json"
        ).read_text()
    )
    assert fixture["data_kind"] == "synthetic_component_reference_not_a_study"
    result = _paired_bootstrap(fixture["paired_differences"])
    assert result["interval"] == pytest.approx(fixture["interval"], abs=1e-12)


def test_no_reordering_no_selective_abstention_and_zero_baseline_division():
    p = plan(2)
    f = [forecast(0, None, 0.0), forecast(1, None, 1.0)]
    o = [outcome(0, False), outcome(1, True)]
    a = evaluate(p, f, o)
    b = evaluate(p, list(reversed(f)), list(reversed(o)))
    assert a["primary"] == b["primary"] and a["rows"] == b["rows"]
    assert a["brier_skill_vs_paired_baseline"] is None
    assert (
        a["baseline"]["brier_score"]
        == a["augmented_with_baseline_for_abstentions"]["brier_score"]
        == 0
    )
    assert a["real_world_efficacy"] == "not_established_by_synthetic_data"


def test_research_cli_schema_and_real_json_round_trip(tmp_path):
    root = Path(__file__).parents[2]
    script = root / "scripts/guolao/audit_guolao_career_study.py"
    schema = subprocess.run(
        [sys.executable, str(script), "--schema"],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    assert (
        json.loads(schema.stdout)["analysis_code_sha256"] == analysis_code_fingerprint()
    )
    records = {
        "plan": plan(2).model_dump(mode="json"),
        "forecasts": [
            forecast(0, 0.9).model_dump(mode="json"),
            forecast(1, 0.7).model_dump(mode="json"),
        ],
        "outcomes": [
            outcome(0, True).model_dump(mode="json"),
            outcome(1, False).model_dump(mode="json"),
        ],
    }
    for name, data in records.items():
        (tmp_path / (name + ".json")).write_text(json.dumps(data))
    output = tmp_path / "report.json"
    args = [
        sys.executable,
        str(script),
        "--as-of",
        AS_OF.isoformat(),
        "--output",
        str(output),
    ]
    for name in records:
        args += ["--" + name, str(tmp_path / (name + ".json"))]
    completed = subprocess.run(
        args, cwd=root, text=True, capture_output=True, check=True
    )
    report = json.loads(output.read_text())
    assert json.loads(completed.stdout)["observed_pair_count"] == 2
    assert report["real_world_efficacy"] == "not_established_by_synthetic_data"
    assert not report["authority_certified"]


def test_positive_prespecified_comparison_can_pass_without_authority_claim():
    n = 20
    p = plan(n, minimum_evaluable=10, minimum_brier_improvement=0.03)
    submitted = [forecast(i, 0.9 if i % 2 else 0.1, 0.3 + 0.02 * i) for i in range(n)]
    recorded = [outcome(i, bool(i % 2)) for i in range(n)]
    report = evaluate(p, submitted, recorded)
    assert report["primary"]["prespecified_sample_comparison_passed"]
    assert report["primary"]["uncertainty"]["interval"][1] < -0.03
    assert not report["authority_certified"]
    assert not report["universal_perfect_prediction_established"]
    assert report["real_world_efficacy"] == "not_established_by_synthetic_data"


def test_naive_analysis_clock_and_future_registration_are_rejected():
    for as_of in [datetime(2028, 2, 1), datetime(2026, 10, 31, tzinfo=timezone.utc)]:
        with pytest.raises(ValueError):
            evaluate(plan(), [], [], as_of=as_of)


def test_confirmed_positive_survives_later_loss_but_negative_needs_full_followup():
    known = outcome(0, True, window_complete_through="2027-06-01T00:00:00Z")
    report = evaluate(plan(2), [forecast(0, 0.9), forecast(1, 0.8)], [known])
    assert report["observed_pair_count"] == 1
    with pytest.raises(ValueError):
        evaluate(
            plan(2),
            [],
            [outcome(1, False, window_complete_through="2027-12-31T23:59:59Z")],
        )


def test_source_change_during_analysis_is_not_given_a_frozen_code_receipt(monkeypatch):
    from fatebridge.validation import guolao_career

    registered = plan()
    values = iter([registered.analysis_code_sha256, "0" * 64])
    monkeypatch.setattr(
        guolao_career, "analysis_code_fingerprint", lambda: next(values)
    )
    with pytest.raises(ValueError, match="执行期间"):
        evaluate(registered, [], [])


def test_dst_fold_cannot_pass_a_late_forecast_as_before_the_window():
    zone = ZoneInfo("America/New_York")
    start = datetime(2027, 11, 7, 1, 30, tzinfo=zone, fold=0)
    issued = datetime(2027, 11, 7, 1, 15, tzinfo=zone, fold=1)
    assert issued < start  # Python same-tz wall comparison ignores the fold.
    assert issued.astimezone(timezone.utc) > start.astimezone(timezone.utc)
    p = plan(2, window_start=start, window_end=datetime(2027, 11, 8, tzinfo=zone))
    with pytest.raises(ValueError, match="窗口开始前"):
        evaluate(p, [forecast(0, 0.5, issued_at=issued)], [])


def test_a_physically_ordered_fold_window_is_valid_and_offsets_are_canonical():
    zone = ZoneInfo("America/New_York")
    start = datetime(2027, 11, 7, 1, 30, tzinfo=zone, fold=0)
    end = datetime(2027, 11, 7, 1, 15, tzinfo=zone, fold=1)
    assert end < start  # Wall order reverses the actual 45-minute window.
    p = plan(2, window_start=start, window_end=end)
    assert (p.window_end - p.window_start).total_seconds() == 45 * 60
    assert p.window_start.tzinfo == p.window_end.tzinfo == timezone.utc
    same = plan(
        2,
        window_start=start.astimezone(timezone.utc),
        window_end=end.astimezone(timezone.utc),
    )
    assert p.model_dump(mode="json") == same.model_dump(mode="json")


@pytest.mark.parametrize(
    "augmented,baseline,outcome",
    [
        (1.0, math.nextafter(1.0, 0.0), 1),
        (1e-20, 2e-20, 1),
        (math.nextafter(0.0, 1.0), 2 * math.nextafter(0.0, 1.0), 1),
    ],
)
def test_small_brier_difference_uses_exact_double_oracle_without_absolute_tolerance(
    augmented, baseline, outcome
):
    a, b, y = Fraction(augmented), Fraction(baseline), Fraction(outcome)
    expected = float((a - y) ** 2 - (b - y) ** 2)
    assert expected != 0
    assert _brier_difference(augmented, baseline, outcome) == pytest.approx(
        expected, rel=1e-15, abs=0
    )
