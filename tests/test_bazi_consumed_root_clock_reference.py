"""Full saved-cohort clock evidence must retain references and unknown limits."""

import ast
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-consumed-root-clock-reference-v1"


def bound(name):
    path = STUDY / name
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == path.with_suffix(".sha256").read_text().strip()
    )
    return json.loads(
        gzip.decompress(path.read_bytes())
        if path.suffix == ".gz"
        else path.read_bytes()
    )


INPUTS = bound("inputs-first.json.gz")
REFERENCE = bound("independent-reference-first.json.gz")
ASSESSMENT = bound("assessment-first.json.gz")
ACTUAL = bound("actual-clock-first.json.gz")


def micros(delta):
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def test_complete_saved_cohort_order_point_inventory_and_unknown_objects_retained():
    mapping = STUDY / INPUTS["mapping"]
    assert hashlib.sha256(mapping.read_bytes()).hexdigest() == INPUTS["mapping_sha256"]
    counts, ids, realizations = Counter(), set(), set()
    with gzip.open(mapping, "rt") as stream:
        for index, row in enumerate(map(json.loads, stream)):
            assert row["cohort_index"] == index
            assert row["id"] not in ids
            ids.add(row["id"])
            if "unknown_source" in row:
                assert row["unknown_saved"]["adjudicated"] is False
                assert (
                    row["unknown_saved"]["id"]
                    == row["unknown_source"]["id"]
                    == row["id"]
                )
                assert (
                    row["unknown_saved"]["source_status"]
                    == row["unknown_source"]["status"]
                )
                counts["unknown"] += 1
            else:
                assert len(row["point_realization_ids"]) == 7
                realizations.update(row["point_realization_ids"])
                counts["points"] += 7
                counts["known"] += 1
    assert len(ids) == 116906
    assert counts == {"unknown": 782, "known": 116124, "points": 812868}
    assert realizations == set(range(2357))
    assert INPUTS["distinct_realizations"] == len(INPUTS["roots"]) == 2357


def test_all_three_independent_answers_precede_assessment_and_have_declared_methods():
    receipt = json.loads((STUDY / "reference-freeze-receipt-first.json").read_text())
    assert receipt["assessment_did_not_exist"] is True
    assert (
        receipt["independent_reference_sha256"]
        == hashlib.sha256(
            (STUDY / "independent-reference-first.json.gz").read_bytes()
        ).hexdigest()
    )
    assert REFERENCE["point_count"] == 7071
    assert REFERENCE["counts"] == {
        "shared_Swiss_DeltaT_minus1_Decimal90_bisection120": 1992,
        "SOFA_raw_table_rational_affine_or_constant": 5079,
    }
    assert REFERENCE["native_deltat_calls"] == 1992 * 120
    for row in REFERENCE["rows"]:
        assert set(row["answers"]) == {
            "original_scalar",
            "independent_split",
            "actual_consumed_split",
        }
        assert all(a["label_utc"] is not None for a in row["answers"].values())


def test_reference_generator_never_reads_delivered_labels_or_imports_application():
    source = ROOT / "scripts/audit_bazi_consumed_root_clock_reference.py"
    tree = ast.parse(source.read_text())
    reference = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "reference"
    )
    forbidden = {
        "actual_consumed_label_utc",
        "reference_civil_under_frozen_policy",
        "actual_datetime_utc",
    }
    strings = {
        n.value
        for n in ast.walk(reference)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    assert not strings & forbidden
    assert REFERENCE["no_application_imports"] is True


def test_actual7071_point_calls_keep_exact_independent_answers_for_all3_root_forms():
    assert ACTUAL["counts"] == {"all_point_calls": 7071, "exact_matches": 7071}
    assert ACTUAL["source_files_unchanged"] is True
    assert [r["realization_id"] for r in ACTUAL["rows"]] == list(range(2357))
    for row, expected in zip(ACTUAL["rows"], REFERENCE["rows"], strict=True):
        assert row["realization_id"] == expected["realization_id"]
        for name, point in row["points"].items():
            assert point["expected"] == expected["answers"][name]
            assert point["matched"] is True
            assert (
                point["actual"]["label_utc"] == expected["answers"][name]["label_utc"]
            )


def test_every_signed_leg_uses_the_correct_same_point_and_sum_is_kept():
    for row in ASSESSMENT["rows"]:
        root, answers = row["root"], row["independent_answer"]["answers"]
        old = datetime.fromisoformat(
            root["original_source"]["reference_civil_under_frozen_policy"]
        )
        delivered = datetime.fromisoformat(root["actual_consumed_label_utc"])
        scalar = datetime.fromisoformat(answers["original_scalar"]["label_utc"])
        split = datetime.fromisoformat(answers["independent_split"]["label_utc"])
        actual = datetime.fromisoformat(answers["actual_consumed_split"]["label_utc"])
        legs = row["label_legs_microseconds"]
        assert legs == {
            "original_clock_label": micros(scalar - old),
            "scalar_to_split_same_skyfield": micros(split - scalar),
            "independent_to_actual_model": micros(actual - split),
            "actual_point_clock": micros(delivered - actual),
        }
        assert (
            sum(legs.values()) == row["total_delivered_label_difference_microseconds"]
        )
        assert sum(legs.values()) == micros(delivered - old)
        assert row["telescoping_residual_microseconds"] == 0


def test_disagreements_never_disappear_by_summing_only_favorable_legs():
    assert ASSESSMENT["counts"] == {
        "all_realizations": 2357,
        "original_clock_label_nonzero": 2330,
        "scalar_to_split_same_skyfield_nonzero": 2331,
        "independent_to_actual_model_nonzero": 2357,
        "actual_point_clock_nonzero": 0,
    }
    assert ASSESSMENT["maximum_absolute_label_leg_microseconds"] == {
        "original_clock_label": 34,
        "scalar_to_split_same_skyfield": 41,
        "independent_to_actual_model": 16,
        "actual_point_clock": 0,
    }
    assert sum(v["all_realizations"] for v in ASSESSMENT["per_era"].values()) == 2357


def test_conditional_preUTC_future_and_original_strict_gates_are_not_upgraded():
    assert REFERENCE["historical_physical_UTC_certified"] is False
    assert REFERENCE["future_offsets_physically_certified"] is False
    assert ASSESSMENT["root_model_physical_correctness_adjudicated"] is False
    assert ASSESSMENT["original116906_strict_gate_passed"] is False
    for data in (INPUTS, REFERENCE, ASSESSMENT, ACTUAL):
        assert data["original_gates_superseded"] is False
        assert data["new_model_executions"] == 0
        assert data["full_goal_complete"] is False


def test_dependency_closed_replays_keep_every_reference_and_actual_byte():
    for name, minimum in (
        ("reference-dependency-replay-first.json", 220),
        ("actual-dependency-replay-first.json", 399),
    ):
        receipt = bound(name)
        assert receipt["loaded_files_guarded"] >= minimum
        assert (
            len(receipt["before_loaded_file_hashes"]) == receipt["loaded_files_guarded"]
        )
        assert receipt["all_prior_loaded_files_unchanged"] is True
        assert receipt["changed_files"] == []
        assert receipt["new_loaded_files"] == 0
        assert receipt["original_rows_exactly_replayed"] is True
        assert receipt["entire_output_bytes_exact"] is True
        assert receipt["first_output_sha256"] == receipt["repeated_output_sha256"]
        assert receipt["original_gates_superseded"] is False
