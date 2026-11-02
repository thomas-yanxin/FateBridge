"""Keep the original failed proof, stricter A result and untouched B holdouts."""

import hashlib
import json
import shutil
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.verify_astrodice_joint_epoch import verify, verify_joint

FIXTURE = Path(__file__).parent / "fixtures/astrodice-joint-epoch-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_all_raw_sources_first_results_failures_and_fixed_lines_are_sealed():
    assert (
        sha(FIXTURE / "manifest.json")
        == "fe95e05ac8c0b6ba266aab705ad663463025fd34f4b3bbba79cb06339c1b6da0"
    )
    files = load("manifest.json")["files"]
    assert len(files) == 202
    for name, digest in files.items():
        assert sha(FIXTURE / name) == digest
    audit = load("first-audit.json")
    assert audit["original_position_arcsec"] == 0.02
    assert audit["original_daily_rate_arcsec_per_day"] == 0.002
    assert audit["production_acceptance_exit_code"] == 2
    assert audit["retained_overall_numeric_gate_exit_code"] == 1
    assert audit["candidate_calls"] == audit["new_candidate_holdouts"] == 0
    assert not audit["full_goal_complete"]


@pytest.mark.parametrize(
    "cohort,name,steps,boxes",
    [
        ("A", "A-independent-replay-refined.json", 576, 3600),
        ("B", "B-independent-replay-first.json", 240, 1500),
    ],
)
def test_independent_raw_basis_bernstein_and_epoch_proof_replay(
    cohort, name, steps, boxes
):
    actual = verify(FIXTURE, cohort)
    assert actual == load(name)
    assert actual["contractor_steps_checked"] == steps
    assert actual["source_boxes_checked"] == boxes
    assert not actual["physical_time_model_certified"]


def test_failed_original_verifier_and_numerical_A_are_never_rewritten():
    original = load("A-independent-first-process.json")
    assert original["exit_code"] == 1
    assert "Velocity predicate changed" in original["stderr"]
    assert (FIXTURE / "A-independent-replay-first.json").read_bytes() == b""
    assert load("A-independent-refined-first-process.json")["exit_code"] == 0
    assert (
        sha(FIXTURE / "A-first-analysis.json")
        == "3b24980d206e64c116aa13e8d4bccc44f1fd04f7961ce3bc92f6dace7f1e34d4"
    )
    changed = []
    for name, digest in load("implementation-before-queries.json").items():
        relative = Path(name).relative_to("frozen-source")
        if sha(FIXTURE / "refined-source" / relative) != digest:
            changed.append(relative.name)
    assert changed == ["verify_astrodice_joint_epoch.py"]


def test_fresh_B_dates_queries_and_A_refinement_are_bound_before_collection():
    plan = load("plan-before-queries.json")
    primary = [c for c in plan["cohorts"]["B"] if c["role"] != "auxiliary_not_primary"]
    assert [c["nominal_calendar_TT"] for c in primary] == [
        "1431-03-17T22:34:12.789137",
        "3431-06-17T22:34:12.789137",
        "6431-09-17T22:34:12.789137",
        "9431-12-17T22:34:12.789137",
    ]
    queries = [q for q in plan["queries"] if q["cohort"] == "B"]
    assert len(queries) == 6
    assert {q["encoding"] for q in queries} == {"JD", "MJD", "CAL"}
    binding = load("B-before-query-refinement-binding.json")
    assert binding["A_refined_proof_sha256"] == sha(
        FIXTURE / "A-independent-replay-refined.json"
    )
    assert binding["A_analysis_sha256"] == sha(FIXTURE / "A-first-analysis.json")
    assert not binding["B_results_opened"]
    assert binding["at_utc"] < load("before-B-queries.json")["at_utc"]
    for cohort in ("A", "B"):
        collected = load(cohort + "-collection.json")
        assert len(collected["receipts"]) == 6
        assert all(
            r["status"] == 200 and r["attempt"] == 1 for r in collected["receipts"]
        )


def test_B_keeps_all_three_encodings_and_rejects_the_continuous_velocity_model():
    for group in load("B-independent-replay-first.json")["groups"]:
        for name, p in group["profiles"].items():
            assert p["primary"] == p["two_axis_root_proved"] == 4
            assert p["position_model_not_refuted"] == 4
            assert p["source_range_matches_observer"] == 3
            assert p["continuous_LT_relation_not_refuted"] == (
                0 if name == "printing_only" else 1
            )
            assert p["velocity_models"]["naive_velocity_difference"] == 4
            assert (
                p["velocity_models"]["continuous_Newtonian_reception_derivative"] == 0
            )
            assert p["radial_vector_RR"]["naive_velocity_difference"] == 4
            assert (
                p["radial_vector_RR"]["continuous_Newtonian_reception_derivative"] == 0
            )
            assert p["continuous_full_model_not_refuted"] == 0


def test_original_8103_center_retains_nonzero_continuous_LT_residual():
    groups = load("A-first-analysis.json")["groups"]
    for group in [g for g in groups if g["id"] == "seen-8103-new-format"]:
        row = next(
            r
            for r in group["rows"]
            if r["vector"]["case_id"] == "seen-8103-original-center"
        )
        p = row["profiles"]["printing_plus_64_ULP_hypothesis"]
        low, high = map(Q, p["emission_minus_reception_plus_LT_seconds"])
        assert Q(8, 10**6) < low < high < Q(10, 10**6)
        assert not p["continuous_LT_relation_not_refuted"]
        assert not p["continuous_Newtonian_LT_vector_model_not_refuted"]


def test_two_selected_equations_and_lattice_membership_do_not_certify_physics():
    for group in load("B-first-analysis.json")["groups"]:
        for row in group["rows"]:
            if row["vector"]["role"] == "auxiliary_not_primary":
                continue
            for p in row["profiles"].values():
                assert p["selected_equations_parametric_unique_root_proved"]
                assert not p["full_three_component_root_certified"]
                assert not p["physical_time_model_certified"]
                for role in ("reception", "emission"):
                    models = p["lattices"][role]
                    assert models["absolute_JD_binary64"]["points"] == 0
                    assert models["seconds_from_J2000_binary64"]["points"] == 1
                    assert all(
                        not m["internal_representation_certified"]
                        for m in models.values()
                    )


def test_six_A_refinements_are_retained_as_added_refutations_not_promotions():
    proof = load("A-independent-replay-refined.json")
    rows = proof["refinement_rows"]
    assert len(rows) == 6
    assert {r["profile"] for r in rows} == {"printing_only"}
    assert {r["group"] for r in rows} == {"seen-19h", "seen-20h"}
    for row in rows:
        assert row["refinements"] == [
            {
                "field": "naive_velocity_difference.velocity.1",
                "reported_not_refuted": True,
                "independently_refuted": True,
            }
        ]
    assert load("B-independent-replay-first.json")["refinement_rows"] == []


@pytest.mark.parametrize(
    "mutation", ["A_bytes", "B_bytes", "source", "binding", "plan"]
)
def test_source_result_and_holdout_identity_tampering_is_rejected(tmp_path, mutation):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    if mutation in ("A_bytes", "B_bytes"):
        path = tmp_path / (mutation[0] + "-first-analysis.json")
        path.write_bytes(path.read_bytes() + b" ")
    elif mutation == "source":
        (
            tmp_path / "refined-source/scripts/verify_astrodice_joint_epoch.py"
        ).write_text("pass\n")
    elif mutation == "binding":
        path = tmp_path / "B-before-query-refinement-binding.json"
        d = load(path.name, tmp_path)
        d["A_refined_proof_sha256"] = "0" * 64
        path.write_text(json.dumps(d))
    else:
        path = tmp_path / "plan-before-queries.json"
        d = load(path.name, tmp_path)
        d["reception_search_radius_seconds"] = "2"
        path.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        verify(tmp_path, "B")


@pytest.mark.parametrize(
    "mutation",
    ["C", "third_component", "physical_scope", "norm", "iterations", "support"],
)
def test_independent_math_rejects_invalid_certificates(mutation):
    plan = load("plan-before-queries.json")
    row = load("B-first-analysis.json")["groups"][0]["rows"][1]
    case = next(c for c in plan["cohorts"]["B"] if c["id"] == row["vector"]["case_id"])
    p = row["profiles"]["printing_only"]
    if mutation == "C":
        p["preconditioner"][0][0] = "0"
    elif mutation == "third_component":
        p["source_ray_AU"].pop()
    elif mutation == "physical_scope":
        p["physical_time_model_certified"] = True
    elif mutation == "norm":
        p["history"][0]["contraction_upper"] = "0"
    elif mutation == "iterations":
        p["history"].pop()
    else:
        p["initial_offsets_seconds"][0] = ["-2", "2"]
    with pytest.raises(ValueError):
        verify_joint(
            FIXTURE / "source-records",
            case,
            row["vector"],
            row["observer"],
            "printing_only",
            p,
            plan,
        )
