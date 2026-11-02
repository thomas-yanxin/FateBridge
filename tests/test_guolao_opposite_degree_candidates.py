"""Primary textual cases cannot certify a method by choosing a rounding policy."""

import hashlib
import json
import os
import subprocess
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

import fatebridge.core.guolao_coordinates as module
from fatebridge.core.guolao_classical import BRANCHES

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/guolao-opposite-degree-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


def test_actual_cadal_original_and_publisher_read_views_have_frozen_fingerprints():
    for entry in REFERENCE["downloads"]:
        actual = (FIXTURE / entry["file"]).read_bytes()
        assert hashlib.sha256(actual).hexdigest() == entry["sha256"]
        if entry["file"] == "original.djvu":
            assert len(actual) == 6284105
            assert (
                hashlib.sha1(actual).hexdigest()
                == "37a4a82e01c7b806e75cdb7f6397947bb4d89d5c"
            )
    assert (
        hashlib.sha256(module.OPPOSITE_EXAMPLES.read_bytes()).hexdigest()
        == REFERENCE["runtime_data_sha256"]
    )
    assert (
        hashlib.sha256(
            (FIXTURE / REFERENCE["existing_luwei_source_file"]).read_bytes()
        ).hexdigest()
        == REFERENCE["existing_luwei_source_sha256"]
    )
    assert not REFERENCE["second_independent_collator"]
    assert not REFERENCE["books_have_same_method"]


@pytest.mark.parametrize("key", module.PROFILES)
def test_all_three_cases_and_all_15_shared_shifts_keep_known_counterexamples(key):
    result = module.audit_opposite_examples(module.PROFILES[key])
    shifts = result["constant_column_shift_candidates"]
    assert [r["shift"] for r in shifts] == list(range(-13, 2))
    assert all(len(r["cases"]) == 3 for r in shifts)
    assert not result["any_shared_constant_shift_matches_all_numeric_cases"]
    assert result["every_shared_shift_has_known_numeric_counterexample"]
    zero = next(r for r in shifts if r["shift"] == 0)
    one = next(r for r in shifts if r["shift"] == 1)
    assert [r["numeric_match"] for r in zero["cases"]] == [False, False, True]
    assert [r["numeric_match"] for r in one["cases"]] == [True, True, False]
    assert [r["target_cell"]["numeral_value"] for r in one["cases"]] == [5, 4, 6]
    assert all(
        r["target_cell"]["inherited_mansion"] is None
        for s in shifts
        for r in s["cases"]
    )
    assert any(r["numeric_match"] is None for s in shifts for r in s["cases"])


@pytest.mark.parametrize("key", module.PROFILES)
@pytest.mark.parametrize("basis", ["from_entrance", "to_exit"])
def test_hand_exact_arithmetic_keeps_unrounded_candidates_from_each_named_version(
    key, basis
):
    result = module.audit_opposite_examples(module.PROFILES[key])
    candidate = next(r for r in result["coordinate_candidates"] if r["basis"] == basis)
    expected = REFERENCE["hand_arithmetic"][f"{key}_{basis}"]
    assert len(candidate["cases"]) == len(expected) == 3
    for actual, held in zip(candidate["cases"], expected):
        point = actual["candidate"]["target_point"]
        assert point["mansion"] == held["mansion"]
        assert F(point["degree_in_mansion_du_exact"]) == F(held["degree"])
        assert not actual["candidate"]["rounding_applied"]
        assert not actual["candidate"]["source_textual_derivation_accepted"]
        assert not actual["case"]["birth_datetime_known"]
    assert not candidate["all_exact_literal_points_match"]


def test_apparent_three_of_three_floor_fit_is_not_a_method_or_precision_acceptance():
    result = module.audit_opposite_examples(module.WIKISOURCE_PALACES)
    high = next(r for r in result["coordinate_candidates"] if r["basis"] == "to_exit")
    assert high["all_nominal_points_floor_into_expected_bins"]
    assert not high["floor_is_source_fact"] and not high["candidate_accepted"]
    assert not result["best_candidate_selected"]
    assert not result["quantization_policy_accepted"]
    assert not result["book_methods_assumed_identical"]
    assert result["real_world_prediction_cases"] == 0
    for entry, overlap in zip(high["cases"], [F(".086"), F(".206"), F(".1732")]):
        sensitivity = entry["unit_interval_sensitivity_hypothesis"]
        assert not sensitivity["input_interval_is_source_fact"]
        assert F(sensitivity["overlap_with_expected_unit_bin_du_exact"]) == overlap
        assert not sensitivity["whole_input_interval_matches_expected_unit_bin"]
        assert not entry["exact_literal_point_match"]
        assert not entry["candidate"]["life_degree_accepted"]
    nlc = module.audit_opposite_examples(module.NLC166_PALACES)
    assert not any(
        c["all_nominal_points_floor_into_expected_bins"]
        for c in nlc["coordinate_candidates"]
    )


@pytest.mark.parametrize("key", module.PROFILES)
@pytest.mark.parametrize("basis", ["from_entrance", "to_exit"])
def test_transfer_preserves_the_declared_distance_and_inverts_for_all_144_branch_pairs(
    key, basis
):
    profile = module.PROFILES[key]
    for source_branch in BRANCHES:
        source = profile.from_palace(source_branch, profile.width(source_branch) / 2)
        for target_branch in BRANCHES:
            result = profile.transfer_candidate(
                mansion=source["mansion"],
                degree_du=F(source["degree_in_mansion_du_exact"]),
                source_branch=source_branch,
                target_branch=target_branch,
                basis=basis,
            )
            target = result["target_point"]
            assert target is not None
            source_offset = F(source["degree_in_branch_interval_du_exact"])
            target_offset = F(target["degree_in_branch_interval_du_exact"])
            if basis == "from_entrance":
                assert source_offset == target_offset
            else:
                assert (
                    profile.width(source_branch) - source_offset
                    == profile.width(target_branch) - target_offset
                )
            back = profile.transfer_candidate(
                mansion=target["mansion"],
                degree_du=F(target["degree_in_mansion_du_exact"]),
                source_branch=target_branch,
                target_branch=source_branch,
                basis=basis,
            )
            assert back["target_point"] == source


@pytest.mark.parametrize("key", module.PROFILES)
def test_out_of_target_branch_candidates_remain_unassigned_without_modulus(key):
    profile = module.PROFILES[key]
    wide = max(BRANCHES, key=profile.width)
    narrow = min(BRANCHES, key=profile.width)
    source = profile.from_palace(wide, profile.width(narrow))
    low = profile.transfer_candidate(
        mansion=source["mansion"],
        degree_du=F(source["degree_in_mansion_du_exact"]),
        source_branch=wide,
        target_branch=narrow,
        basis="from_entrance",
    )
    assert low["target_point"] is None
    assert F(low["target_offset_du_exact"]) == profile.width(narrow)
    assert low["status"] == "candidate_outside_target_branch_interval"
    source = profile.from_palace(wide, F())
    high = profile.transfer_candidate(
        mansion=source["mansion"],
        degree_du=F(source["degree_in_mansion_du_exact"]),
        source_branch=wide,
        target_branch=narrow,
        basis="to_exit",
    )
    assert high["target_point"] is None and F(high["target_offset_du_exact"]) < 0


@pytest.mark.parametrize(
    "degree,basis,branch,error",
    [
        (6.0, "to_exit", "子", TypeError),
        (F(6), "automatic", "子", ValueError),
        (F(6), "from_entrance", "丑", ValueError),
    ],
)
def test_transfer_requires_exact_units_an_explicit_policy_and_matching_source_branch(
    degree, basis, branch, error
):
    with pytest.raises(error):
        module.NLC166_PALACES.transfer_candidate(
            mansion="虚",
            degree_du=degree,
            source_branch=branch,
            target_branch="午",
            basis=basis,
        )


@pytest.mark.parametrize(
    "field", ["source_id", "source_image_sha256", "data_sha256", "marker_data_sha256"]
)
def test_grid_version_drift_rejects_old_case_placement(tmp_path, monkeypatch, field):
    raw = json.loads(module.OPPOSITE_EXAMPLES.read_bytes())
    raw["grid_binding"][field] = "another-version"
    path = tmp_path / "data.json"
    path.write_text(json.dumps(raw))
    monkeypatch.setattr(module, "OPPOSITE_EXAMPLES", path)
    with pytest.raises(ValueError, match="重新核读"):
        module.audit_opposite_examples(module.NLC166_PALACES)


@pytest.mark.parametrize("key", module.PROFILES)
def test_actual_research_cli_with_selected_version_and_rejection_of_mixed_inputs(key):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    args = [
        sys.executable,
        str(ROOT / "scripts/audit_guolao_coordinates.py"),
        "--profile",
        key,
        "--audit-opposite-examples",
    ]
    success = subprocess.run(args, env=env, text=True, capture_output=True, check=True)
    assert json.loads(success.stdout)[
        "opposite_degree_candidates"
    ] == module.audit_opposite_examples(module.PROFILES[key])
    failure = subprocess.run(
        [*args, "--palace", "子", "--degree", "6"],
        env=env,
        text=True,
        capture_output=True,
    )
    assert (
        failure.returncode != 0 and not failure.stdout and "不可混用" in failure.stderr
    )


@pytest.mark.parametrize(
    "mutation", ["drop_case", "duplicate_case", "unknown_source", "duplicate_source"]
)
def test_partial_or_duplicated_textual_denominators_are_rejected(
    tmp_path, monkeypatch, mutation
):
    raw = json.loads(module.OPPOSITE_EXAMPLES.read_bytes())
    if mutation == "drop_case":
        raw["cases"].pop()
    elif mutation == "duplicate_case":
        raw["cases"].append(raw["cases"][0])
    elif mutation == "unknown_source":
        raw["cases"][0]["source_document_id"] = "unknown"
    else:
        raw["sources"].append(raw["sources"][0])
    path = tmp_path / "partial.json"
    path.write_text(json.dumps(raw))
    monkeypatch.setattr(module, "OPPOSITE_EXAMPLES", path)
    with pytest.raises(ValueError, match="完整且唯一"):
        module.audit_opposite_examples(module.NLC166_PALACES)
