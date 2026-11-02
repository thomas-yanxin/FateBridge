"""Frozen input-path evidence keeps unfavorable results and original gates."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.verify_astrodice_vector_clock import bernstein_bounds, derivative, verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-vector-clock-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_frozen_population_raw_inputs_and_original_failures_remain_sealed():
    assert (
        hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
        == "9c329a5fe34370f811a31e935fe613d1a6afd5e0b436f48b7d46290a702e4420"
    )
    files = load("manifest.json")["files"]
    assert len(files) == 94
    for name, expected in files.items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    for name, expected in load("retained-legacy-sha256.json").items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    assert (
        load("retained-legacy/astrodice-grid5-current-regression-audit.json")[
            "overall_numeric_gate_exit_code"
        ]
        == 1
    )
    audit = load("first-audit.json")
    assert audit["production_acceptance_exit_code"] == 2
    assert audit["candidate_calls"] == audit["new_TT_candidate_holdouts"] == 0
    assert audit["full_goal_complete"] is False


@pytest.mark.parametrize("cohort", ["A", "B"])
def test_independent_exact_replay_keeps_first_intervals_and_scores(cohort):
    actual = verify(FIXTURE, cohort)
    assert actual == load(cohort + "-independent-replay-first.json")
    assert actual["exact_inverse_endpoint_checks"] == (672 if cohort == "A" else 240)
    assert actual["independent_source_enclosure_checks"] == (
        1260 if cohort == "A" else 450
    )


def test_delivery_replays_unopened_at_design_B_data_in_a_new_process(tmp_path):
    root = (FIXTURE / "delivery-code").resolve()
    output = tmp_path / "B.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.verify_astrodice_vector_clock",
            "--run",
            str(FIXTURE.resolve()),
            "--cohort",
            "B",
            "--output",
            str(output),
        ],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == load("B-independent-replay-first.json")


def test_the_two_coincident_hypotheses_are_not_independent_replications():
    plan = load("plan-before-queries.json")
    for cases in plan["cohorts"].values():
        for case in cases:
            epoch = Q(case["nominal_JD"])
            assert Q(2451545) + Q(float((epoch - 2451545) * 86400)) / 86400 == epoch
    assert len(plan["cohorts"]["A"]) == 14 and len(plan["cohorts"]["B"]) == 5
    assert plan["new_TDB_clock_conditions"] == 4
    assert plan["new_TT_candidate_holdouts"] == 0


def test_unfavorable_profiles_and_predeclared_hypotheses_are_retained():
    a = {q["id"]: q for q in load("A-independent-replay-first.json")["queries"]}
    b = {q["id"]: q for q in load("B-independent-replay-first.json")["queries"]}
    for encoding, aa, bb in [("JD", 1, 2), ("MJD", 8, 4), ("CAL", 13, 4)]:
        for data, cohort, expected in [(a, "A", aa), (b, "B", bb)]:
            query = data[f"{cohort}-TDB-{encoding}"]
            profile = query["profiles"]["printing_plus_64_ULP_hypothesis"]
            assert profile["hypotheses"]["exact_nominal_TDB"] == expected
            assert profile["hypotheses"]["binary64_absolute_JD"] == 0
            assert query["label_pass"] == query["primary"]
    assert a["A-TDB-MJD"]["profiles"]["printing_only"]["six_not_refuted"] == 12
    assert a["A-TDB-CAL"]["profiles"]["printing_only"]["six_not_refuted"] == 12


@pytest.mark.parametrize(
    "mutation",
    [
        "promote",
        "drop_row",
        "axis",
        "bracket",
        "hypothesis",
        "derivative",
        "state_failure",
        "raw_frame",
        "plan_budget",
        "B_binding",
    ],
)
def test_independent_replay_rejects_tampering_and_score_promotion(tmp_path, mutation):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    cohort = "B" if mutation == "B_binding" else "A"
    path = tmp_path / (cohort + "-first-analysis.json")
    data = load(path.name, tmp_path)
    row = data["queries"][0]["rows"][1]
    if mutation == "promote":
        data["TT_observer_clock_equivalence_certified"] = True
    elif mutation == "drop_row":
        data["queries"][0]["rows"].pop()
    elif mutation == "axis":
        row["axis"] = (row["axis"] + 1) % 3
    elif mutation == "bracket":
        row["profiles"]["printing_only"]["boundary_brackets_JD"][0][0] = str(
            Q(row["nominal_JD"]) - 1
        )
    elif mutation == "hypothesis":
        row["profiles"]["printing_plus_64_ULP_hypothesis"][
            "hypothesis_in_inverse_interval"
        ]["binary64_absolute_JD"] = True
    elif mutation == "derivative":
        row["derivative_bounds"][0] = ["0", "0"]
    elif mutation == "state_failure":
        failed = next(
            v
            for q in data["queries"]
            for v in q["rows"]
            if not v["profiles"]["printing_only"]["all_six_compatible"]
        )
        failed["profiles"]["printing_only"]["all_six_compatible"] = True
    elif mutation == "raw_frame":
        raw = tmp_path / "responses/A-TDB-JD.raw"
        raw.write_bytes(raw.read_bytes().replace(b"ICRF", b"B1950"))
        sha = hashlib.sha256(raw.read_bytes()).hexdigest()
        receipt = tmp_path / "responses/A-TDB-JD.receipt.json"
        d = json.loads(receipt.read_text())
        d["raw_sha256"] = sha
        receipt.write_text(json.dumps(d))
        data["queries"][0]["raw_sha256"] = sha
    elif mutation == "plan_budget":
        plan_path = tmp_path / "plan-before-queries.json"
        plan = json.loads(plan_path.read_text())
        plan["returned_label_match_budget_days"] = "1"
        plan_path.write_text(json.dumps(plan))
    else:
        before_path = tmp_path / "before-B-queries.json"
        before = json.loads(before_path.read_text())
        before["prior_A_analysis_sha256"] = "0" * 64
        before_path.write_text(json.dumps(before))
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(tmp_path, cohort)


def test_exact_bernstein_bounds_match_affine_and_enclose_curved_polynomials():
    assert bernstein_bounds([Q(3), Q(2)], Q(-2), Q(5)) == (Q(-1), Q(13))
    assert bernstein_bounds([Q(7), Q(-3)], Q(2), Q(4)) == (Q(-5), Q(1))
    poly = [Q(1), Q(-2), Q(3), Q(7)]
    lo, hi = bernstein_bounds(poly, Q(-1, 4), Q(1, 3))
    for x in [Q(-1, 4), Q(0), Q(1, 3)]:
        assert lo <= sum(c * x**k for k, c in enumerate(poly)) <= hi
    assert derivative(poly) == [Q(-2), Q(6), Q(21)]
