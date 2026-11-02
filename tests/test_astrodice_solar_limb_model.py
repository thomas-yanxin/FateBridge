"""Preserve model disagreement; a fitting diagnostic is not production success."""

import ast
import hashlib
import json
import shutil
import subprocess
import sys
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice_solar_limb_reference import replay
from scripts.audit_astrodice_solar_limb import independent_aberration, separation

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/astrodice-solar-limb-model-v1"


def read(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_additive_binding_manifest_preserves_the_historical_self_hash_failure():
    root = FIXTURE.with_name("astrodice-solar-limb-import-binding-v1")
    reviewed = root / "reviewed-manifest.json"
    assert hashlib.sha256(reviewed.read_bytes()).hexdigest() == (
        "ec6af6a991dbf34ac70280a140b8da2fe09299d53a980c0e813d2bb7009556e0"
    )
    data = read(reviewed.name, root)
    assert not data["historical_manifest_regraded"]
    assert not data["numerical_results_changed"]
    assert set(data["files"]) == {p.name for p in root.iterdir()} - {reviewed.name}
    for name, digest in data["files"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    old = read("manifest.json", root)
    mismatches = {
        name: {
            "expected": digest,
            "actual": hashlib.sha256((root / name).read_bytes()).hexdigest(),
        }
        for name, digest in old["files"].items()
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest
    }
    assert mismatches == data["historical_manifest_failure"]
    assert set(mismatches) == {"manifest.json"}
    addendum = read("runtime-addendum-manifest.json", root)
    assert addendum["previous_manifest_sha256"] == data["files"]["manifest.json"]
    for name, digest in addendum["files"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest


def test_all_frozen_inputs_and_unmodified_blind_checker_remain_intact():
    assert hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest() == (
        "622e140473714b150f15314833f23e7f5d5723c52d50f5dd3ebf7eae8cc302dd"
    )
    for name, expected in read("manifest.json")["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    a, b = read("A-native-first-seal.json"), read("B-native-first-seal.json")
    assert a["candidate_files"] == b["candidate_files"]
    assert b["B_still_unopened"] and not b["model_and_checker_changed_after_A"]
    for name in [
        "scripts/select_astrodice_solar_limb.py",
        "scripts/astrodice_solar_limb_reference.py",
    ]:
        assert (
            hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            == b["candidate_files"][name]
        )
    binding_root = FIXTURE.with_name("astrodice-solar-limb-import-binding-v1")
    binding = read("binding.json", binding_root)
    before = (binding_root / "source-before.py.txt").read_bytes()
    current = (ROOT / "scripts/audit_astrodice_solar_limb.py").read_bytes()
    assert (
        hashlib.sha256(before).hexdigest()
        == binding["before_sha256"]
        == b["candidate_files"]["scripts/audit_astrodice_solar_limb.py"]
    )
    assert hashlib.sha256(current).hexdigest() == binding["after_sha256"]

    def normalized(value):
        tree = ast.parse(value)
        body = []
        for node in tree.body:
            if (
                isinstance(node, ast.ImportFrom)
                and body
                and isinstance(body[-1], ast.ImportFrom)
                and (body[-1].module, body[-1].level) == (node.module, node.level)
            ):
                body[-1].names.extend(node.names)
            else:
                body.append(node)
        tree.body = body
        return ast.dump(tree, include_attributes=False)

    assert normalized(before) == normalized(current)
    # AST serialization has interpreter-version-specific fields. The immutable
    # byte hashes plus same-runtime AST equality above are required everywhere;
    # retain both recorded hashes rather than rewriting the original 3.14 one.
    historical = read("runtime-addendum.json", binding_root)
    local_hash = hashlib.sha256(normalized(before).encode()).hexdigest()
    if tuple(sys.version_info[:2]) == tuple(historical["original_major_minor"]):
        assert local_hash == binding["normalized_AST_sha256"]
    if sys.version_info[:2] == (3, 12):
        assert local_hash == read("runtime-3.12-proof.json", binding_root)["AST_sha256"]
    assert read("original-overall-gate.json")["overall_numeric_gate_exit_code"] == 1
    assert read("original-difficult-cases.json")["exit_code"] == 1


def test_independent_geometry_selects_the_same_32_conditions_without_candidate(
    tmp_path,
):
    output = tmp_path / "selection.json"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.select_astrodice_solar_limb",
            "--run",
            str(FIXTURE),
            "--fixture",
            str(FIXTURE / "source-records"),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    selected = json.loads(output.read_text())
    assert selected == read("selection-first.json")
    assert [len(selected["cohorts"][cohort]) for cohort in ["A", "B"]] == [16, 16]
    assert not selected["candidate_or_apparent_residual_used"]
    assert not selected["physical_TT_TDB_conversion_certified"]


@pytest.mark.parametrize(
    "cohort,encoding", [(c, e) for c in ["A", "B"] for e in ["JD", "MJD"]]
)
def test_both_source_encodings_replay_every_planned_centre(cohort, encoding):
    prefix = cohort + "-" + encoding
    result = replay(
        FIXTURE / (prefix + "-protocol.json"),
        FIXTURE / (prefix + "-reference-first.json"),
        FIXTURE / (prefix + "-raw"),
    )
    assert len(result["rows"]) == 16
    assert all(row["status"] == "position_reference_replayed" for row in result["rows"])
    assert not result["rejected_epoch_rows"]
    assert (
        not result["rate_accuracy_assessed"]
        and not result["candidate_accuracy_assessed"]
    )
    if cohort == "A":
        assert result == read(prefix + "-position-replay-after-code-retention.json")
    for row in result["rows"]:
        point = row["observation"]
        if point["primary_visibility_code"] == "o":
            assert not point["primary_visibility_code_documented_exactly"]


@pytest.mark.parametrize("cohort", ["A", "B"])
def test_default_and_global_no_gr_failures_cannot_be_replaced_by_piecewise_success(
    cohort,
):
    rows = [read(f"{cohort}-native-first/{i:02}.json") for i in range(16)]
    assert (
        sum(Q(row["case"]["nominal_source_impact_radius_fraction"]) < 1 for row in rows)
        == 8
    )
    for row in rows:
        inside = Q(row["case"]["nominal_source_impact_radius_fraction"]) < 1
        assert (
            not row["production_formula_changed"] and not row["rate_accuracy_assessed"]
        )
        assert row["hypotheses_are_diagnostics_not_production_acceptance"]
        assert not row["full_goal_complete"]
        for value in row["comparisons"].values():
            tests = value["native_comparisons"]
            assert tests["default"]["status"] == (
                "numeric_failure" if inside else "declared_position_line_satisfied"
            )
            assert tests["no_GR"]["status"] == (
                "declared_position_line_satisfied" if inside else "numeric_failure"
            )
            assert (
                tests["piecewise_background_inside_no_GR"]["status"]
                == "declared_position_line_satisfied"
            )
            assert tests["piecewise_background_inside_no_GR"][
                "selected_native_mode"
            ] == ("no_GR" if inside else "default")
            assert tests["astrometric"]["status"] == "declared_position_line_satisfied"
            assert tests["no_aberration"]["status"] == "numeric_failure"
            assert all(test["fixed_line_arcsec"] == 0.02 for test in tests.values())
        assert (
            row["states"]["default"]["state_xyz_AU_and_AU_per_day"]
            == row["states"]["default_after_controls"]["state_xyz_AU_and_AU_per_day"]
        )
        assert row["native_default_repeat_drift_arcsec"] == 0


def test_independent_published_astrometric_aberration_reproduces_the_recorded_signal():
    for cohort in ["A", "B"]:
        for i in range(16):
            row = read(f"{cohort}-native-first/{i:02}.json")
            inside = Q(row["case"]["nominal_source_impact_radius_fraction"]) < 1
            for value in row["comparisons"].values():
                new = independent_aberration(
                    FIXTURE,
                    row["case"],
                    value["observation"]["astrometric_printed_angles"],
                )
                old = value["independent_aberration_of_quantity1"]
                assert separation(new["direction"], old["direction"]) < 1e-9
                assert (
                    new["observer_barycentric_velocity_AU_per_TDB_day"]
                    == old["observer_barycentric_velocity_AU_per_TDB_day"]
                )
                # The original 0.02 arcsecond line separates the signal. This
                # does not certify an observer velocity/TT model error bound.
                assert (old["separation_from_printed_apparent_arcsec"] < 0.02) == inside
                assert not old["candidate_accuracy_certified"]


def test_initial_lowercase_visibility_parser_failures_are_preserved():
    original = (FIXTURE / "position-replay-before-lowercase-code.py").read_bytes()
    for encoding in ["JD", "MJD"]:
        failure = read("A-" + encoding + "-position-replay-first-process.json")
        assert failure["returncode"] == 1
        assert failure["checker_sha256"] == hashlib.sha256(original).hexdigest()
        assert failure["message"] == "Invalid primary separation or visibility"


def test_a_hidden_rate_claim_or_relaxed_epoch_budget_is_rejected_even_after_hash_rebinding(
    tmp_path,
):
    data = tmp_path / "data"
    shutil.copytree(FIXTURE, data)
    path = data / "B-JD-protocol.json"
    plan = json.loads(path.read_text())
    plan["timestamp_printing_tolerance_days"] = "2e-9"
    path.write_text(json.dumps(plan))
    refpath = data / "B-JD-reference-first.json"
    raw = json.loads(refpath.read_text())
    raw["protocol_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    refpath.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="Position-only protocol"):
        replay(path, refpath, data / "B-JD-raw")


def test_an_available_raw_centre_cannot_be_omitted(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(FIXTURE, data)
    path = data / "B-MJD-reference-first.json"
    raw = json.loads(path.read_text())
    raw["rows"][0]["samples"]["0"] = None
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="Stored position differs"):
        replay(data / "B-MJD-protocol.json", path, data / "B-MJD-raw")
