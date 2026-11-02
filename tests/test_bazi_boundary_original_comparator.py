"""Adverse evidence mutations must not be mistaken for Bazi improvements."""

import copy
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-boundary-original-comparator-v1"
PATH = ROOT / "scripts/compare_bazi_boundary_original_replay.py"
SPEC = importlib.util.spec_from_file_location("_boundary_comparator_test", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SEEDS = MODULE.bound_json(STUDY / "mutation-seeds-first.json")


def known():
    return copy.deepcopy(SEEDS["known"][0])


def compare(before, after):
    return MODULE.compare_record(before, after, before["cohort_index"])


def sync_outside(record):
    # Independent test-fixture calculation, using aware datetime comparison.
    period = next(
        p for p in record["actual_range"]["dayun_boundary_ranges"] if p["period"] == 1
    )
    low, high = (
        datetime.fromisoformat(period[k])
        for k in ("earliest_start_at", "latest_start_at")
    )
    record["safe_source_witnesses_outside_probe_envelope"] = [
        p
        for p in record["timeline_probes"]
        if p["safe_distance_gate"]
        and not low <= datetime.fromisoformat(p["reference"]["manual_start_at"]) <= high
    ]


def test_original_boundary_helpers_are_exact_not_reimplemented_to_pass():
    MODULE.verify_legacy_helpers()


def test_identity_preserves_every_observation_and_original_strict_failure():
    row = known()
    result = compare(row, row)
    assert result["preservation_failures"] == []
    assert result["point_probes_exact"] is True
    assert result["strict_before_failed"] is result["strict_after_failed"] is True
    assert result["strict_transition"] == "retained"


@pytest.mark.parametrize(
    "field,value",
    [
        ("actual_start_at", "1900-01-01T00:00:00+00:00"),
        ("actual_root_jd_tt", -1.0),
        ("safe_distance_gate", 1),
    ],
)
def test_saved_point_value_metadata_and_json_type_changes_are_not_hidden(field, value):
    old, new = known(), known()
    new["timeline_probes"][0][field] = value
    result = compare(old, new)
    assert "point_probe_object_changed" in result["preservation_failures"]
    assert any(
        change["path"].endswith("/" + field)
        for change in result["point_probe_leaf_changes"]
    )


def test_unknown_reason_change_is_retained_as_failure_not_a_new_known_match():
    old, new = copy.deepcopy(SEEDS["unknown"]), copy.deepcopy(SEEDS["unknown"])
    new["unresolved_reason"] += " changed"
    result = compare(old, new)
    assert result["preservation_failures"] == ["unknown_record_changed"]
    assert result["unknown_leaf_changes"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("adjudicated", True),
        ("cohort_index", False),
        ("source_status", "resolved_source_control"),
    ],
)
def test_unknown_promotion_or_identity_coercion_rejects_the_pair(field, value):
    old, new = copy.deepcopy(SEEDS["unknown"]), copy.deepcopy(SEEDS["unknown"])
    new[field] = value
    with pytest.raises(AssertionError):
        compare(old, new)


def test_dropping_stored_failure_list_cannot_make_a_strict_failure_disappear():
    old, new = known(), known()
    new["safe_source_witnesses_outside_probe_envelope"] = []
    result = compare(old, new)
    assert result["strict_after_failed"] is True
    assert "after_stored_strict_receipt_inconsistent" in result["preservation_failures"]


def test_lost_current_state_is_detected_even_when_the_saved_summary_agrees():
    old, new = known(), known()
    removed = new["actual_statuses"].pop()
    new["actual_range"]["current_dayun_candidates"] = [
        r
        for r in new["actual_range"]["current_dayun_candidates"]
        if r["status"] != removed
    ]
    result = compare(old, new)
    assert "removed_states" in result["preservation_failures"]


def test_removed_period_is_detected_without_requiring_first_period_to_disappear():
    old, new = known(), known()
    new["actual_range"]["dayun_boundary_ranges"].pop()
    result = compare(old, new)
    assert "removed_periods" in result["preservation_failures"]


@pytest.mark.parametrize(
    "field,step",
    [
        ("earliest_start_at", 1),
        ("latest_start_at", -1),
        ("earliest_end_at", 1),
        ("latest_end_at", -1),
    ],
)
def test_all_four_utc_bound_directions_detect_shrink(field, step):
    old, new = known(), known()
    row = new["actual_range"]["dayun_boundary_ranges"][2]
    row[field] = (
        datetime.fromisoformat(row[field]) + timedelta(microseconds=step)
    ).isoformat()
    result = compare(old, new)
    assert "shrunken_bounds" in result["preservation_failures"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("sample_count", 2),
        ("first_sample_at", "1900-01-01T00:00:00+00:00"),
        ("last_sample_at", None),
    ],
)
def test_minute_grid_counts_and_labels_are_immutable(field, value):
    old, new = known(), known()
    new["actual_range"]["pillars_candidates"][0][field] = value
    assert "changed_minute_grid_fields" in compare(old, new)["preservation_failures"]


def test_event_multiset_retention_does_not_accept_a_missing_duplicate():
    old, new = known(), known()
    event = old["declared_inverse_events"][0]
    old["declared_inverse_events"].append(copy.deepcopy(event))
    result = compare(old, new)
    assert "lost_declared_inverse_events" in result["preservation_failures"]
    assert result["lost_declared_inverse_events"][0]["missing_count"] == 1


@pytest.mark.parametrize(
    "layer,kind",
    [
        ("event_analysis", "probes"),
        ("dayun_event_analysis", "events"),
        ("dayun_event_analysis", "probes"),
    ],
)
def test_old_event_and_probe_objects_cannot_be_deleted(layer, kind):
    old, new = known(), known()
    new["actual_range"][layer][kind].pop()
    failure = "old_probe_objects_lost" if kind == "probes" else "old_event_objects_lost"
    assert failure in compare(old, new)["preservation_failures"]


def test_additive_events_probes_and_duplicate_receipts_preserve_old_evidence():
    old, new = known(), known()
    for layer in ("event_analysis", "dayun_event_analysis"):
        for kind in ("events", "probes"):
            new["actual_range"][layer][kind].append(
                {"synthetic_verifier_extension": True}
            )
    new["declared_inverse_events"].append(
        copy.deepcopy(new["declared_inverse_events"][0])
    )
    result = compare(old, new)
    assert result["preservation_failures"] == []
    assert result["strict_after_failed"] is True


def test_expansion_can_change_strict_membership_but_is_not_a_calculation_fix():
    old, new = known(), known()
    row = new["actual_range"]["dayun_boundary_ranges"][0]
    row["earliest_start_at"] = (
        datetime.fromisoformat(row["earliest_start_at"]) - timedelta(seconds=1)
    ).isoformat()
    row["latest_start_at"] = (
        datetime.fromisoformat(row["latest_start_at"]) + timedelta(seconds=1)
    ).isoformat()
    sync_outside(new)
    result = compare(old, new)
    assert result["strict_transition"] == "fixed"
    assert result["preservation_failures"] == []
    assert result["expanded_bounds"]


def test_introduced_strict_failure_is_recorded_in_both_directions():
    old, new = known(), known()
    row = old["actual_range"]["dayun_boundary_ranges"][0]
    row["earliest_start_at"] = (
        datetime.fromisoformat(row["earliest_start_at"]) - timedelta(seconds=1)
    ).isoformat()
    row["latest_start_at"] = (
        datetime.fromisoformat(row["latest_start_at"]) + timedelta(seconds=1)
    ).isoformat()
    sync_outside(old)
    result = compare(old, new)
    assert result["strict_transition"] == "introduced"
    assert "strict_failure_introduced" in result["preservation_failures"]


@pytest.mark.parametrize("variant", ["missing", "reordered", "duplicate"])
def test_streams_reject_missing_reordered_and_duplicate_records(variant):
    before = copy.deepcopy(SEEDS["known"])
    after = copy.deepcopy(before)
    if variant == "missing":
        after.pop()
    elif variant == "reordered":
        after.reverse()
    else:
        after[1] = copy.deepcopy(after[0])
    with pytest.raises(AssertionError):
        MODULE.compare_streams(
            map(json.dumps, before), map(json.dumps, after), lambda _: None
        )


def test_leaf_differences_do_not_conflate_null_missing_or_boolean_number():
    assert MODULE.leaf_changes({"x": None}, {})[0]["after_present"] is False
    assert MODULE.leaf_changes([True], [1]) == [dict(path="/0", before=True, after=1)]


@pytest.mark.parametrize("relative", [True, False])
def test_record_paths_remain_readable_inside_and_outside_the_repository(
    tmp_path, relative
):
    path = (
        MODULE.ROOT / "docs/validation/fixture.jsonl.gz"
        if relative
        else tmp_path / "external.jsonl.gz"
    )
    stored = MODULE.record_path(path)
    assert (MODULE.ROOT / stored).resolve() == path.resolve()
    assert Path(stored).is_absolute() is not relative
