"""Frozen inverse/grid evidence keeps model refutations and prior scores."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.verify_astrodice_emission_epoch import verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-emission-epoch-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_complete_frozen_inputs_and_original_failure_gates_remain_sealed():
    assert (
        hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
        == "e4e3c64feacc43b0b993434eefe4b9ed47156f9d8ed3442334d8c5d2c9429e3a"
    )
    files = load("manifest.json")["files"]
    assert len(files) == 366
    for name, expected in files.items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    assert (
        hashlib.sha256((FIXTURE / "controls/manifest.json").read_bytes()).hexdigest()
        == "312977683d017d2a6ddc8b29fa9b6903df65b32c581a81b5210312078e56598d"
    )
    audit = load("first-audit.json")
    assert audit["candidate_calls"] == audit["new_candidate_holdouts"] == 0
    assert audit["new_frozen_TT_conditions"] == 4
    assert audit["production_acceptance_exit_code"] == 2
    assert audit["retained_overall_numeric_gate_exit_code"] == 1
    assert audit["full_goal_complete"] is False


@pytest.mark.parametrize("cohort", ["A", "B"])
def test_all_source_endpoints_and_complete_lattice_points_replay_independently(cohort):
    observed = verify(FIXTURE, cohort)
    assert observed == load(cohort + "-independent-replay-first.json")
    assert observed["exact_inverse_endpoint_checks"] == (456 if cohort == "A" else 120)
    assert observed["lattice_candidate_enclosures_checked"] == (
        240 if cohort == "A" else 26
    )


def test_new_b_all_paths_and_both_noise_profiles_keep_refuted_conditions():
    b = load("B-independent-replay-first.json")
    for query, count in zip(b["groups"], [3, 4, 3]):
        assert query["primary"] == 4
        for profile in query["profiles"].values():
            assert profile["inferred"] == profile["geometric_six_not_refuted"] == 4
            assert profile["lattices"]["absolute_JD_binary64"]["refuted"] == 4
            et = profile["lattices"]["seconds_from_J2000_binary64"]
            assert et["unique"] == count and et["refuted"] == 4 - count
    assert not b["internal_emission_algorithm_certified"]


def test_previous_wide_family_match_does_not_override_an_empty_exact_ET_lattice():
    old = load("controls/B-first-analysis.json")["queries"][0]["rows"]
    original = next(v for v in old if v["case_id"] == "B-window-6")
    assert original["profiles"]["printing_plus_64_ULP_hypothesis"]["models"][
        "converged_Newtonian_24_emission_ET_ULP_hypothesis"
    ]["all_selected_observables_not_refuted"]
    group = next(
        g
        for g in load("A-first-analysis.json")["groups"]
        if g["source_cohort"] == "B" and g["query_id"] == "B-TT-JD"
    )
    same = next(v for v in group["rows"] if v["case_id"] == "B-window-6")
    lattice = same["profiles"]["printing_plus_64_ULP_hypothesis"]["lattices"][
        "seconds_from_J2000_binary64"
    ]
    assert lattice["enumeration_status"] == "complete"
    assert lattice["points_in_effective_interval"] == 0
    assert lattice["conditional_refuted"] and not lattice["unique_not_refuted"]


@pytest.mark.parametrize(
    "mutation",
    [
        "promote",
        "drop_row",
        "Earth_ball",
        "inverse_endpoint",
        "lattice_count",
        "score",
        "time_coordinate",
        "old_geometric_failure",
        "B_binding",
    ],
)
def test_independent_replay_rejects_altered_source_grid_or_acceptance_claims(
    tmp_path, mutation
):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    cohort = "B" if mutation == "B_binding" else "A"
    path = tmp_path / (cohort + "-first-analysis.json")
    data = load(path.name, tmp_path)
    profile = data["groups"][0]["rows"][0]["profiles"]["printing_only"]
    et = profile["lattices"]["seconds_from_J2000_binary64"]
    if mutation == "promote":
        data["internal_emission_algorithm_certified"] = True
    elif mutation == "drop_row":
        data["groups"][0]["rows"].pop()
    elif mutation == "Earth_ball":
        profile["Earth_radius_AU"] = "-1"
    elif mutation == "inverse_endpoint":
        profile["inverse"]["boundary_brackets_JD"][0][0] = "0"
    elif mutation == "lattice_count":
        et["points_in_effective_interval"] += 1
    elif mutation == "score":
        et["unique_not_refuted"] = not et["unique_not_refuted"]
    elif mutation == "time_coordinate":
        profile["lattices"]["absolute_JD_binary64"] = profile["lattices"][
            "seconds_from_J2000_binary64"
        ]
    elif mutation == "old_geometric_failure":
        failed = next(
            v
            for g in data["groups"]
            for v in g["rows"]
            if not v["profiles"]["printing_only"]["calibration_all_six_not_refuted"]
        )
        failed["profiles"]["printing_only"]["calibration_all_six_not_refuted"] = True
    else:
        p = tmp_path / "before-B-queries.json"
        before = load(p.name, tmp_path)
        before["prior_A_analysis_sha256"] = "0" * 64
        p.write_text(json.dumps(before))
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(tmp_path, cohort)
