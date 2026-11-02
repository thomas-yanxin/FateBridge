"""Historical source matches never remove prior failures or required models."""

import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hd_historical_models", ROOT / "scripts/audit_human_design_historical_models.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FIX = ROOT / "tests/fixtures"
PLAN = (FIX / "human-design-historical-model-plan.json").read_bytes()
TREES = (FIX / "human-design-historical-source-trees.json").read_bytes()
PRIOR = (FIX / "human-design-historical-prior-audit.json").read_bytes()
PREDICTIONS = json.loads(
    (FIX / "human-design-historical-model-predictions.json").read_text()
)
PLAN_SHA = "f1fb4c7842d307f531c118c6582df28ef4c1b5dfd20bc1e4cac99134cddf7ba4"


def audit(predictions=PREDICTIONS, prior=PRIOR, trees=TREES):
    return MODULE.compare_all(PLAN, predictions, prior, trees, PLAN_SHA)


def test_complete14_paths_expose_duplicate_tags_and_preserve_failed_prior_audit():
    result = audit()
    assert result["all_required_predictions_present_once"]
    assert result["required_model_count"] == 14
    assert result["required_root_count"] == result["provided_root_count"] == 56
    assert len(result["hypotheses"]) == 28
    compatible = [
        r for r in result["hypotheses"] if r["all_required_intervals_compatible"]
    ]
    assert {(r["model"], r["local_minus_common_ut1_seconds"]) for r in compatible} == {
        ("v21003_175e_JPL406_default", 0),
        ("installed_21003_JPL406_default", 0),
    }
    assert result["nominal_tag_count"] == 5
    assert result["unique_official_tree_count"] == 3
    assert result["tag_tree_groups"]["2642e22d6de0d40949bf0bea87eefca823217676"] == [
        "v1.77",
        "v1.80",
        "v2.00",
    ]
    assert result["prior_audit_status"] == "not_achieved"
    assert result["prior_compatible_hypothesis_count"] == 0
    for key in (
        "prior_failures_regraded",
        "physical_accuracy_certified",
        "source_backend_identified",
        "distinct_historical_release_versions_authenticated",
        "all_three_axes_full_marks",
    ):
        assert not result[key]


@pytest.mark.parametrize(
    "event", ["neptune_boundary", "moon_before", "moon_after", "sun_nearest"]
)
def test_removing_any_event_invalidates_the_complete_candidate_inventory(event):
    changed = deepcopy(PREDICTIONS)
    changed["rows"] = [r for r in changed["rows"] if r["event_id"] != event]
    result = audit(changed)
    assert not result["all_required_predictions_present_once"]
    assert len(result["hypotheses"]) == 28
    assert result["compatible_execution_path_count"] == 0


def test_selecting_only_the_two_matching_paths_does_not_create_complete_success():
    changed = deepcopy(PREDICTIONS)
    changed["rows"] = [
        r
        for r in changed["rows"]
        if r["model"]
        in ("v21003_175e_JPL406_default", "installed_21003_JPL406_default")
    ]
    result = audit(changed)
    assert result["provided_root_count"] == 8
    assert result["required_root_count"] == 56
    assert not result["all_required_predictions_present_once"]
    assert result["compatible_execution_path_count"] == 0


def test_duplicate_root_rows_are_not_silently_deduplicated():
    changed = deepcopy(PREDICTIONS)
    changed["rows"].append(deepcopy(changed["rows"][0]))
    result = audit(changed)
    assert result["provided_root_count"] == 57
    assert len(result["all_supplied_prediction_rows_retained"]) == 57
    assert not result["all_required_predictions_present_once"]


def test_changing_old_failed_report_is_rejected_by_its_original_digest():
    changed = json.loads(PRIOR)
    changed["status"] = "passed"
    with pytest.raises(ValueError, match="required digest"):
        audit(prior=json.dumps(changed).encode())


def test_changing_vendor_identity_bytes_does_not_manufacture_distinct_releases():
    with pytest.raises(ValueError, match="required digest"):
        audit(trees=TREES + b" ")


@pytest.mark.parametrize("mutation", ["clock", "root", "plan"])
def test_clock_root_or_plan_contradictions_invalidate_all_candidate_success(mutation):
    changed = deepcopy(PREDICTIONS)
    if mutation == "clock":
        changed["rows"][0]["clock_hypotheses"][0][
            "predicted_local_calendar"
        ] = "1840-02-02T03:12:30"
    elif mutation == "root":
        changed["rows"][0]["root_jd_tt"] += 0.01
    else:
        changed["plan_sha256"] = "forged"
    result = audit(changed)
    assert not result["all_required_predictions_present_once"]
    assert result["compatible_execution_path_count"] == 0


def test_same_size_changed_vendor_blob_is_detected(tmp_path):
    raw = b"original source\n"
    target = tmp_path / "source1" / "file.c"
    target.parent.mkdir()
    target.write_bytes(raw)
    tree = [
        {
            "id": "source1",
            "tree": {
                "tree": [
                    {
                        "type": "blob",
                        "path": "file.c",
                        "size": len(raw),
                        "sha": hashlib.sha1(
                            ("blob " + str(len(raw)) + "\0").encode() + raw
                        ).hexdigest(),
                    }
                ]
            },
        }
    ]
    assert MODULE.verify_vendor_blobs(json.dumps(tree).encode(), tmp_path)[0][
        "git_blob_matches"
    ]
    target.write_bytes(b"replaced source\n")
    row = MODULE.verify_vendor_blobs(json.dumps(tree).encode(), tmp_path)[0]
    assert row["size_matches"]
    assert not row["git_blob_matches"]
