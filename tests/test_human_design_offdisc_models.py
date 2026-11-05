"""Off-disc source compatibility cannot hide missing probes or TT conflicts."""

import importlib.util
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hd_offdisc_models", ROOT / "scripts/audit_human_design_offdisc_models.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
BASE = ROOT / "tests/data/human_design/offdisc"
PLAN = (BASE / "source-plan.json").read_bytes()
INITIAL = json.loads((BASE / "model-predictions.json").read_bytes())
PRODUCTION = json.loads((BASE / "production-clock-model-predictions.json").read_bytes())
SUPPLEMENT = json.loads((BASE / "production-clock-supplement-plan.json").read_bytes())
COHORT = json.loads((BASE / "source-cohort.json").read_bytes())


@lru_cache(maxsize=1)
def current_packets():
    return MODULE.current_packets(json.loads(PLAN))


def audit(initial=INITIAL, production=PRODUCTION, cohort=COHORT, packets=None):
    return MODULE.compare_all(
        PLAN,
        initial,
        production,
        SUPPLEMENT,
        cohort,
        current_packets() if packets is None else packets,
    )


def assert_no_full_source_acceptance(result):
    assert not any(r["all24_required_targets_compatible"] for r in result["hypotheses"])
    for key in (
        "source_backend_identified",
        "physical_accuracy_certified",
        "complete384_line_prose_accepted",
        "arbitrary_model_prose_accepted",
        "prior_failures_regraded",
        "original_predictions_replaced",
        "all_three_axes_full_marks",
        "all_four_axes_full_marks",
        "authority_certified",
    ):
        assert result[key] is False


def test_all520_predictions_and24_packets_retain14_missing_sources_and5_clock_conflicts():
    result = audit()
    assert result["status"] == "not_achieved"
    assert result["required_cases"] == 24 and result["observed_cases"] == 10
    assert len(result["missing_case_ids"]) == 14
    assert result["all_required_predictions_bound"]
    assert result["initial_prediction_inventory"]["provided"] == 280
    assert result["production_prediction_inventory"]["provided"] == 240
    assert result["source_rows_bound"] and result["source_metadata_consistent"]
    assert result["all_obtained_pdf_text_bound"] is False
    assert result["primary_source_status"] == "not_available"
    assert result["all24_native_packets_bound"]
    assert result["all24_fixed_readings_verified"] is True
    assert len(result["fixed_reading_checks"]) == 24
    assert all(
        row["proof"]["status"] == "verified_fixed_template_reading"
        for row in result["fixed_reading_checks"]
    )
    assert result["original_clock_label_disagreement_ids"] == [
        "od-2100-saturn",
        "od-2200-uranus",
        "od-2200-neptune",
        "od-2300-uranus",
        "od-2300-neptune",
    ]
    assert len(result["data_edition_discriminator_lost_at_production_clock_ids"]) == 10
    assert (
        "od-2100-pluto"
        in result["data_edition_discriminator_lost_at_production_clock_ids"]
    )
    compatible = [
        r
        for r in result["hypotheses"]
        if r["conditional_on_transcriptions_targets_compatible"]
    ]
    assert len(result["hypotheses"]) == 30
    assert len(compatible) == 6
    assert {r["model"] for r in compatible} == {
        "JPL406_default",
        "JPL406_no_deflection",
    }
    assert all(r["observed_target_matches"] == 10 for r in compatible)
    assert_no_full_source_acceptance(result)


@pytest.mark.parametrize("body", ["Saturn", "Uranus", "Neptune", "Pluto"])
def test_dropping_any_body_invalidates_the_required_prediction_inventory(body):
    changed = deepcopy(INITIAL)
    changed["rows"] = [r for r in changed["rows"] if r["body"] != body]
    result = audit(initial=changed)
    assert not result["all_required_predictions_bound"]
    assert not any(r["all_observed_targets_compatible"] for r in result["hypotheses"])
    assert_no_full_source_acceptance(result)


def test_keeping_only_matching_de406_profiles_is_not_a_complete_model_inventory():
    changed = deepcopy(INITIAL)
    changed["rows"] = [r for r in changed["rows"] if r["model"].startswith("JPL406")]
    result = audit(initial=changed)
    assert not result["all_required_predictions_bound"]
    assert len(result["hypotheses"]) == 30
    assert_no_full_source_acceptance(result)


def test_duplicate_prediction_is_retained_and_invalidates_inventory():
    changed = deepcopy(INITIAL)
    changed["rows"].append(deepcopy(changed["rows"][0]))
    result = audit(initial=changed)
    assert result["initial_prediction_inventory"]["provided"] == 281
    assert (
        len(result["all_supplied_prediction_rows_retained"]["original_common_clock"])
        == 281
    )
    assert not result["all_required_predictions_bound"]


def test_forged_gate_label_is_checked_against_numeric_longitude():
    changed = deepcopy(INITIAL)
    changed["rows"][0]["uniform_gate_line"] = "57.1"
    changed["rows"][0]["printed2001_gate_line"] = "57.1"
    result = audit(initial=changed)
    assert result["initial_prediction_inventory"]["invalid_row_indices"] == [0]
    assert not result["all_required_predictions_bound"]


def test_changing_epoch_without_changing_line_still_breaks_clock_binding():
    changed = deepcopy(INITIAL)
    changed["rows"][0]["jd_tt"] += 1 / 86400
    result = audit(initial=changed)
    assert result["initial_prediction_inventory"]["invalid_row_indices"] == [0]


def test_production_clock_cannot_overwrite_original_common_clock_predictions():
    changed = deepcopy(INITIAL)
    target = next(
        r
        for r in PRODUCTION["rows"]
        if r["case_id"] == "od-2100-saturn" and r["model"] == "DE441_default"
    )
    index = next(
        i
        for i, r in enumerate(changed["rows"])
        if r["case_id"] == target["case_id"] and r["model"] == target["model"]
    )
    changed["rows"][index] = deepcopy(target)
    result = audit(initial=changed)
    assert index in result["initial_prediction_inventory"]["invalid_row_indices"]
    assert len(result["original_clock_label_disagreement_ids"]) == 5


def test_deleting_failed_observation_and_claiming_complete_does_not_shrink24_plan():
    changed = deepcopy(COHORT)
    changed["cases"].pop()
    changed.update(
        planned_case_count=9,
        observed_case_count=9,
        missing_planned_ids=[],
        collection_status="complete",
    )
    result = audit(cohort=changed)
    assert result["required_cases"] == 24 and result["observed_cases"] == 9
    assert len(result["missing_case_ids"]) == 15
    assert not result["source_metadata_consistent"]
    assert_no_full_source_acceptance(result)


@pytest.mark.parametrize("kind", ["duplicate", "unknown", "altered_input"])
def test_source_identity_corruption_is_not_accepted(kind):
    changed = deepcopy(COHORT)
    if kind == "duplicate":
        changed["cases"].append(deepcopy(changed["cases"][0]))
    elif kind == "unknown":
        changed["cases"][0]["id"] = "unplanned"
    else:
        changed["cases"][0]["birth_input"]["birth_minute"] += 1
    result = audit(cohort=changed)
    assert not result["source_rows_bound"]
    assert_no_full_source_acceptance(result)


def test_missing_full_packet_cannot_pass_interpretation_coverage():
    result = audit(packets=current_packets()[:-1])
    assert not result["all24_native_packets_bound"]
    assert not result["all24_fixed_readings_verified"]
    assert result["fixed_reading_checks"][-1]["proof"]["status"] == "not_verified"


def test_production_prediction_must_equal_actual_packet_longitude():
    changed = deepcopy(PRODUCTION)
    changed["rows"][0]["longitude"] += 0.000000001
    result = audit(production=changed)
    assert not result["all24_native_packets_bound"]
    assert not result["all24_fixed_readings_verified"]


def test_missing_primary_files_cannot_be_replaced_by_transcription_agreement():
    result = audit()
    assert result["primary_source_status"] == "not_available"
    assert not result["all_obtained_pdf_text_bound"]
    assert (
        sum(
            h["conditional_on_transcriptions_targets_compatible"]
            for h in result["hypotheses"]
        )
        == 6
    )
    assert not any(h["all_observed_targets_compatible"] for h in result["hypotheses"])


def test_changed_plan_bytes_rejected_even_if_json_semantics_unchanged():
    with pytest.raises(ValueError, match="Original off-disc plan changed"):
        MODULE.compare_all(
            PLAN + b" ", INITIAL, PRODUCTION, SUPPLEMENT, COHORT, current_packets()
        )
