"""Frozen dual-body proof, original failures and strict time-batch binding."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.verify_astrodice_earth_clock import verify
from scripts.verify_astrodice_earth_context import audit

FIXTURE = Path(__file__).parent / "fixtures/astrodice-earth-clock-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_original_and_batch_bound_results_controls_and_error_lines_stay_frozen():
    assert (
        hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
        == "309c1ef42f7f0c29efca49e767b52eb6995500c394abde1bb7d74191cfd0bbb0"
    )
    files = load("manifest.json")["files"]
    assert len(files) == 588
    for name, sha in files.items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == sha
    result = load("first-audit.json")
    assert result["new_frozen_TT_conditions"] == 4
    assert (
        result["original_position_arcsec"] == 0.02
        and result["original_daily_rate_arcsec_per_day"] == 0.002
    )
    assert (
        result["production_acceptance_exit_code"] == 2
        and result["retained_overall_numeric_gate_exit_code"] == 1
    )
    assert not result["full_goal_complete"]


@pytest.mark.parametrize("cohort", ["A", "B"])
def test_independent_bound_clock_and_bit_lattice_replay_matches_first_receipt(cohort):
    assert verify(FIXTURE, cohort) == load(
        cohort + "-batch-bound-independent-replay-first.json"
    )


def test_restoration_and_same_batch_alias_controls_replay_without_new_holdouts():
    x = audit(FIXTURE)
    assert x == load("context-independent-first.json")
    assert x["alias_same_batch_rows"] == x["alias_identical_printed_states"] == 42
    assert x["restored_original_rows"] == x["restored_identical_printed_states"] == 21
    assert x["new_heldout_conditions"] == 0
    for p in x["profiles"].values():
        assert p == {"primary": 17, "clock_intervals_disjoint": 4}


def test_original_cross_batch_probes_remain_visible_but_are_now_unqualified():
    original = load("A-first-analysis.json")
    bound = load("A-batch-bound-analysis.json")
    assert (
        original["vectors"] == bound["vectors"] and original["pairs"] == bound["pairs"]
    )
    assert any(
        row["profiles"]["printing_plus_64_ULP_hypothesis"]["Venus"]["inference"][
            "lattices"
        ]["seconds_from_J2000_binary64"]["unique_not_refuted"]
        for g in original["transfers"]
        for row in g["rows"]
    )
    for g in bound["transfers"]:
        assert g["clock_time_batches_match"] == {"Earth": False, "Venus": False}
        for row in g["rows"]:
            for models in row["profiles"].values():
                for value in models.values():
                    assert (
                        value["inference"]["status"] == "cross_batch_clock_unqualified"
                    )


def test_same_batch_holdout_numbers_and_9431_jd_failure_are_not_regraded():
    original, bound = load("B-first-analysis.json"), load("B-batch-bound-analysis.json")
    assert (
        original["vectors"] == bound["vectors"] and original["pairs"] == bound["pairs"]
    )
    for a, b in zip(original["transfers"], bound["transfers"]):
        assert a["rows"] == b["rows"] and all(b["clock_time_batches_match"].values())
    row = next(r for r in bound["transfers"][0]["rows"] if r["case_id"] == "B-clock-6")
    for models in row["profiles"].values():
        for value in models.values():
            et = value["inference"]["lattices"]["seconds_from_J2000_binary64"]
            assert et["conditional_refuted"] and not et["unique_not_refuted"]
    narrow = load("B-batch-bound-independent-replay-first.json")["pairs"][
        "printing_only"
    ]
    assert narrow["disjoint"] == 2 and narrow["joint_not_refuted"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "promote",
        "binding",
        "cross_batch_emission",
        "drop_row",
        "hide_JD_failure",
        "narrow_joint",
    ],
)
def test_independent_proof_rejects_false_qualification_or_hiding_new_failures(
    tmp_path, mutation
):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    cohort = "A" if mutation in {"promote", "binding", "cross_batch_emission"} else "B"
    filename = cohort + "-batch-bound-analysis.json"
    x = load(filename, tmp_path)
    if mutation == "promote":
        x["full_goal_complete"] = True
    elif mutation == "binding":
        x["transfers"][0]["clock_time_batches_match"]["Earth"] = True
    elif mutation == "cross_batch_emission":
        x["transfers"][0]["rows"][0]["profiles"]["printing_only"]["Venus"][
            "inference"
        ] = {"status": "inferred"}
    elif mutation == "drop_row":
        x["transfers"][0]["rows"].pop()
    elif mutation == "hide_JD_failure":
        row = next(r for r in x["transfers"][0]["rows"] if r["case_id"] == "B-clock-6")
        row["profiles"]["printing_only"]["Venus"]["inference"]["lattices"][
            "seconds_from_J2000_binary64"
        ]["unique_not_refuted"] = True
    else:
        item = next(
            p["profiles"]["printing_only"]
            for p in x["pairs"]
            if p["role"] != "auxiliary_not_primary"
            and p["profiles"]["printing_only"]["status"] == "intersecting"
        )
        assert item["joint_necessary_not_refuted"] is False
        item["joint_necessary_not_refuted"] = True
    (tmp_path / filename).write_text(json.dumps(x))
    with pytest.raises(ValueError):
        verify(tmp_path, cohort)
