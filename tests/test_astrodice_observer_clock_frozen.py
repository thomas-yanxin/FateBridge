"""The frozen transfer study never upgrades a fitting allowance to acceptance."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from scripts.verify_astrodice_observer_clock import verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-observer-clock-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_original_inputs_failures_and_first_results_remain_frozen():
    assert (
        hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
        == "312977683d017d2a6ddc8b29fa9b6903df65b32c581a81b5210312078e56598d"
    )
    files = load("manifest.json")["files"]
    assert len(files) == 234
    for name, expected in files.items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    assert (
        hashlib.sha256(
            (FIXTURE / "vector-controls/manifest.json").read_bytes()
        ).hexdigest()
        == "9c329a5fe34370f811a31e935fe613d1a6afd5e0b436f48b7d46290a702e4420"
    )
    audit = load("first-audit.json")
    assert audit["candidate_calls"] == audit["new_candidate_holdouts"] == 0
    assert audit["new_TT_OBSERVER_conditions"] == 4
    assert audit["production_acceptance_exit_code"] == 2
    assert audit["retained_overall_numeric_gate_exit_code"] == 1
    assert audit["full_goal_complete"] is False
    assert (
        load("legacy-source-semantic-diff.json")[
            "numerical_or_derivative_formula_changed"
        ]
        is False
    )


@pytest.mark.parametrize("cohort", ["A", "B"])
def test_independent_exact_interval_proofs_replay_both_complete_cohorts(cohort):
    actual = verify(FIXTURE, cohort)
    assert actual == load(cohort + "-independent-replay-first.json")
    assert actual["independent_interval_history_steps_checked"] == (
        4200 if cohort == "A" else 1500
    )
    assert actual["independent_model_enclosures_checked"] == (
        1260 if cohort == "A" else 450
    )


def test_all_b_source_models_and_unfavorable_observables_stay_visible():
    raw = load("B-first-analysis.json")
    primary = [
        v
        for q in raw["queries"]
        for v in q["rows"]
        if v["role"] != "auxiliary_not_primary"
    ]
    assert (
        sum(
            v["profiles"]["printing_only"]["calibration_all_six_not_refuted"]
            for v in primary
        )
        == 10
    )
    assert (
        sum(
            v["profiles"]["printing_plus_64_ULP_hypothesis"][
                "calibration_all_six_not_refuted"
            ]
            for v in primary
        )
        == 12
    )
    data = load("B-independent-replay-first.json")
    for query in data["queries"]:
        assert query["primary"] == query["label_pass"] == 4
        for profile in query["profiles"].values():
            old = profile["legacy_two_linearized_delays"]
            continuous = profile["converged_Newtonian_24"]
            widened = profile["converged_Newtonian_24_emission_ET_ULP_hypothesis"]
            assert (
                old["all_not_refuted"]
                == old["light_time_not_refuted"]
                == old["range_not_refuted"]
                == 0
            )
            assert continuous["all_not_refuted"] == continuous["range_not_refuted"] == 0
            assert continuous["light_time_not_refuted"] == 4
            assert widened["all_not_refuted"] == 4
    assert not data["TT_observer_clock_equivalence_certified"]
    assert not data["numerical_tubes_certified"]


@pytest.mark.parametrize(
    "mutation",
    [
        "promote",
        "drop_row",
        "source_support",
        "missing_iteration",
        "emission_budget",
        "failed_LT",
        "observed_noise",
        "collector_binding",
        "B_phase_binding",
    ],
)
def test_replay_rejects_score_hiding_and_changed_physical_or_protocol_claims(
    tmp_path, mutation
):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    cohort = "B" if mutation == "B_phase_binding" else "A"
    path = tmp_path / (cohort + "-first-analysis.json")
    data = load(path.name, tmp_path)
    row = data["queries"][0]["rows"][0]
    profile = row["profiles"]["printing_only"]
    continuous = profile["models"]["converged_Newtonian_24"]
    if mutation == "promote":
        data["TT_observer_clock_equivalence_certified"] = True
    elif mutation == "drop_row":
        data["queries"][0]["rows"].pop()
    elif mutation == "source_support":
        continuous["range_AU"] = ["0", "0"]
    elif mutation == "missing_iteration":
        continuous["history"].pop()
    elif mutation == "emission_budget":
        profile["models"]["converged_Newtonian_24_emission_ET_ULP_hypothesis"][
            "emission_argument_radius_days"
        ] = "0"
    elif mutation == "failed_LT":
        failed = next(
            v
            for q in data["queries"]
            for v in q["rows"]
            if not v["profiles"]["printing_only"]["models"][
                "legacy_two_linearized_delays"
            ]["checks"]["light_time_minutes"]
        )
        failed["profiles"]["printing_only"]["models"]["legacy_two_linearized_delays"][
            "checks"
        ]["light_time_minutes"] = True
    elif mutation == "observed_noise":
        profile["observed_bounds"]["range_AU"] = ["0", "100"]
    elif mutation == "collector_binding":
        p = tmp_path / "before-A-queries.json"
        before = load(p.name, tmp_path)
        before["collector_sha256"] = "0" * 64
        p.write_text(json.dumps(before))
    else:
        p = tmp_path / "B-vector-calibration/A-first-analysis.json"
        p.write_text("{}")
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        verify(tmp_path, cohort)
