"""Frozen real source brackets retain missing controls and rejected models."""

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "hd_source_transitions",
    ROOT / "scripts/human_design/audit_human_design_source_transitions.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FIXTURES = ROOT / "tests/fixtures"
PLAN = (FIXTURES / "human-design-neptune-transition-plan.json").read_bytes()
PRIOR = (FIXTURES / "human-design-disc-clock-observations.json").read_bytes()
MODEL_PLAN = (FIXTURES / "human-design-neptune-model-plan.json").read_bytes()
OBSERVATIONS = json.loads(
    (FIXTURES / "human-design-neptune-transition-observations.json").read_text()
)
PREDICTIONS = json.loads(
    (FIXTURES / "human-design-neptune-model-predictions.json").read_text()
)
PLAN_SHA = "07c86e42de9c177e30d01d6956cf98924604774546f4106e2517212d8eda6590"
PRIOR_SHA = "3c92fb2aa7c3e018bc223cad59d6dbb26f5637fadf051a3d87ef11c371d84c34"
MODEL_PLAN_SHA = "2082a9c76e5da303ebc399e8b7c4194e5b9172c8b4d0e32c0f2686039b5e87a2"


def search(observations=OBSERVATIONS):
    return MODULE.adaptive_checks(PLAN, observations, PLAN_SHA, PRIOR, PRIOR_SHA)


def compare(predictions=PREDICTIONS, result=None):
    return MODULE.hypothesis_checks(
        MODEL_PLAN, predictions, search() if result is None else result, MODEL_PLAN_SHA
    )


def test_real26_observations_complete_four_searches_but_no_declared_model_explains_all():
    result = search()
    assert result["finite_adaptive_search_complete"]
    assert result["observations_supplied"] == result["observations_unique"] == 26
    assert result["potential_query_count"] == 100
    assert len(result["events"]) == 4
    assert all(
        c["stable_except_declared_name"] for c in result["repeat_control_checks"]
    )
    assert result["events"][0]["left_local_label"] == "1840-02-02T03:12:00"
    assert result["events"][0]["right_local_label"] == "1840-02-02T03:13:00"
    comparison = compare(result=result)
    assert comparison["all_declared_prediction_rows_present_once"]
    assert len(comparison["hypotheses"]) == 16
    assert len(comparison["all_supplied_prediction_rows_retained"]) == 32
    assert comparison["compatible_hypothesis_count"] == 0
    assert not comparison["source_backend_identified"]


@pytest.mark.parametrize("index", [0, 2, 7, 13, 19, 25])
def test_removing_a_required_query_does_not_make_the_search_complete(index):
    changed = deepcopy(OBSERVATIONS)
    changed.pop(index)
    result = search(changed)
    assert not result["finite_adaptive_search_complete"]
    assert result["observations_supplied"] == 25


def test_unexpected_midpoint_label_is_preserved_as_failure():
    changed = deepcopy(OBSERVATIONS)
    changed[4]["facts"]["columns"]["personality"][11] = "20.1"
    result = search(changed)
    assert not result["finite_adaptive_search_complete"]
    assert result["events"][0]["status"] == "unexpected_source_label"
    assert result["events"][0]["trace"][0]["label"] == "20.1"
    assert result["observations_supplied"] == 26


def test_duplicate_and_out_of_order_queries_are_not_silently_deduplicated():
    changed = deepcopy(OBSERVATIONS)
    changed.insert(2, deepcopy(changed[0]))
    result = search(changed)
    assert not result["finite_adaptive_search_complete"]
    assert result["observations_supplied"] == 27
    assert result["observations_unique"] == 26
    changed = deepcopy(OBSERVATIONS)
    changed[2], changed[3] = changed[3], changed[2]
    assert not search(changed)["finite_adaptive_search_complete"]


def test_wrong_visible_birth_input_cannot_be_hidden_behind_correct_case_id():
    changed = deepcopy(OBSERVATIONS)
    changed[-1]["facts"]["properties"][
        "Date and Time (Local)"
    ] = "February 2, 1840, 00:51"
    result = search(changed)
    assert not result["finite_adaptive_search_complete"]
    assert not result["observation_order_checks"][-1]["planned_local_input_matched"]


def test_changed_repeat_control_does_not_replace_the_original_failure():
    changed = deepcopy(OBSERVATIONS)
    changed[0]["facts"]["columns"]["personality"][11] = "19.5"
    result = search(changed)
    assert not result["repeat_control_checks"][0]["stable_except_declared_name"]
    assert not result["finite_adaptive_search_complete"]


@pytest.mark.parametrize(
    "source,sha", [(PLAN, PLAN_SHA), (PRIOR, PRIOR_SHA), (MODEL_PLAN, MODEL_PLAN_SHA)]
)
def test_frozen_plan_or_prior_bytes_cannot_change_with_retained_digest(source, sha):
    with pytest.raises(ValueError, match="required digest"):
        MODULE.pinned_json(source + b" ", sha)


def test_dropping_failed_neptune_predictions_keeps_all16_hypotheses_rejected():
    changed = deepcopy(PREDICTIONS)
    changed["rows"] = [
        r for r in changed["rows"] if r["event_id"] != "neptune_boundary"
    ]
    result = compare(changed)
    assert not result["all_declared_prediction_rows_present_once"]
    assert len(result["hypotheses"]) == 16
    assert result["compatible_hypothesis_count"] == 0
    assert len(result["all_supplied_prediction_rows_retained"]) == 24


def test_extra_or_missing_clock_hypothesis_invalidates_the_prediction_inventory():
    changed = deepcopy(PREDICTIONS)
    changed["rows"][0]["clock_hypotheses"].pop()
    assert not compare(changed)["all_declared_prediction_rows_present_once"]


def test_self_inconsistent_clock_or_body_cannot_be_used_as_a_matching_prediction():
    changed = deepcopy(PREDICTIONS)
    changed["rows"][0]["clock_hypotheses"][0][
        "predicted_local_calendar"
    ] = "1840-02-02T03:12:30"
    assert not compare(changed)["all_declared_prediction_rows_present_once"]
    changed = deepcopy(PREDICTIONS)
    changed["rows"][0]["body"] = "Moon"
    assert not compare(changed)["all_declared_prediction_rows_present_once"]
    changed = deepcopy(PREDICTIONS)
    changed["rows"][0]["clock_hypotheses"].append(
        deepcopy(changed["rows"][0]["clock_hypotheses"][0])
    )
    assert not compare(changed)["all_declared_prediction_rows_present_once"]
