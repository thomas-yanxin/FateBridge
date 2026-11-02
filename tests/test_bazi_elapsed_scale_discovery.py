"""Do not conflate a known clock-scale difference with adopted calendar policy."""

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-elapsed-scale-discovery-v1"


def frozen(name):
    path = STUDY / name
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(path.read_text())


REFERENCE = frozen("reference-first.json")
AUDIT = frozen("audit-first.json")
PATHS = frozen("dayun-path-first.json")


def test_all_frozen_positive_steps_and_both_sided_controls_are_retained():
    rows = REFERENCE["rows"]
    assert len(rows) == len({r["id"] for r in rows}) == 108
    counts = Counter(r["transition_utc"] for r in rows)
    assert len(counts) == 27 and set(counts.values()) == {4}
    assert Counter(r["kind"] for r in rows) == dict.fromkeys(
        ("cross_forward", "cross_reverse", "before", "after"), 27
    )
    assert REFERENCE["no_application_or_native_imports"] is True


def test_known_atomic_elapsed_intervals_are_derived_from_endpoint_offsets():
    for row in REFERENCE["rows"]:
        nominal = (
            datetime.fromisoformat(row["end_utc"])
            - datetime.fromisoformat(row["start_utc"])
        ).total_seconds()
        atomic = nominal + row["end_tai_minus_utc"] - row["start_tai_minus_utc"]
        assert row["nominal_utc_label_seconds"] == nominal
        assert row["uniform_atomic_elapsed_seconds"] == atomic
        assert (
            atomic
            == {"cross_forward": 3, "cross_reverse": -3, "before": 1, "after": 1}[
                row["kind"]
            ]
        )


def test_actual_helper_matches_nominal_utc_without_being_regraded_as_uniform_si():
    assert AUDIT["nominal_matches"] == 108
    assert AUDIT["uniform_atomic_matches"] == AUDIT["uniform_atomic_mismatches"] == 54
    assert AUDIT["maximum_absolute_scale_difference_seconds"] == 1
    assert "physical time" in AUDIT["helper_source"]
    for row in AUDIT["rows"]:
        assert row["matches_uniform_atomic_elapsed_seconds"] is (
            row["reference"]["kind"] in {"before", "after"}
        )


def test_actual_dayun_starts_match_the_independent_integer_nominal_calendar():
    assert PATHS["cases"] == PATHS["matches_integer_nominal_start"] == 54
    assert Counter(r["input"]["direction"] for r in PATHS["records"]) == {
        "forward": 27,
        "reverse": 27,
    }
    for row in PATHS["records"]:
        assert row["actual_timeline"]["method_id"] == "three_days_one_year_calendar_v1"
        assert row["atomic_elapsed_seconds"] - row["nominal_elapsed_seconds"] == 1
        assert row["initial_nominal_offset_difference_seconds"] == 120
        assert row["atomic_counterfactual_start_difference_seconds"] == 120
        assert datetime.fromisoformat(
            row["integer_nominal_start_at"]
        ) == datetime.fromisoformat(row["actual_timeline"]["start_at"])


def test_float_residues_are_retained_separately_from_the_one_second_scale_gap():
    residues = [
        r["actual_elapsed_seconds"] - r["nominal_elapsed_seconds"]
        for r in PATHS["records"]
        if not r["actual_matches_integer_nominal_elapsed"]
    ]
    assert len(residues) == 5
    assert set(residues) == {-5.820766091346741e-11, 5.820766091346741e-11}
    assert PATHS["matches_integer_nominal_start"] == 54


def test_no_default_policy_original_gate_or_prediction_credit_was_changed():
    assert AUDIT["production_changed"] is False
    assert PATHS["production_policy_changed"] is False
    assert (
        AUDIT["original116906_source_cohort_changed"]
        is PATHS["original116906_source_cohort_changed"]
        is False
    )
    assert (
        AUDIT["original_gates_superseded"]
        is PATHS["original_gates_superseded"]
        is False
    )
    assert AUDIT["new_model_executions"] == PATHS["new_model_executions"] == 0
    assert (
        AUDIT["physical_accuracy_certified"]
        is PATHS["physical_accuracy_certified"]
        is False
    )
