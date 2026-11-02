"""Full-577 evidence and exact fit replay; original failures remain visible."""

import hashlib
import json
import shutil
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.audit_astrodice_native_reference import audit
from scripts.verify_astrodice_native_reference import clocks, references

FIXTURE = Path(__file__).parent / "fixtures/astrodice-native-reference-v1"
MANIFEST_SHA = "82af5ecdedb55448e5d867f6ff62ce93a5d0f96fac971eea92bea9e672ee7305"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_entire_frozen_data_source_first_proofs_and_failed_records_are_unchanged():
    assert (
        hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
        == MANIFEST_SHA
    )
    for name, digest in load("manifest.json")["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    old = load("retained/original-Farkas-replay.json")
    assert old["count"] == 5 and old["all_original_contradictions_preserved"]
    assert not old["original_results_regraded"]
    assert all(Q(w["contradiction"]) < 0 for w in old["witnesses"])


def test_exact_all_point_polynomial_certificates_replay_without_a_solver():
    for cohort in ("A", "B"):
        assert references(FIXTURE, cohort) == load(
            cohort + "-independent-reference-first.json"
        )


def test_all_577_nodes_profiles_grids_and_rounding_models_are_required():
    result = audit(FIXTURE)
    assert result == load("posthoc-summary-first.json")
    assert (
        result["new_primary_contexts"] == 1
        and result["primary_nodes_per_context"] == 577
    )
    assert result["new_candidate_holdouts"] == 0
    for cohort in ("A", "B"):
        models = result["cohorts"][cohort]["models"]
        assert len(models) == 8
        for model in models:
            assert model["required_nodes"] == 577
            assert sum(model["qualified_pair_counts"].values()) == 577
            if model["qualified_nodes"] != 577:
                assert model["status"] == "full_clock_population_unqualified"
                assert "conditional_quality" not in model
    assert (
        result["production_acceptance_exit_code"] == 2
        and result["retained_overall_numeric_gate_exit_code"] == 1
    )
    assert (
        not result["original_gates_rerun"]
        and not result["original_odd_polynomial_gate_replaced"]
    )
    assert (
        not result["TT_derivative_certified"]
        and not result["physical_remainder_certified"]
        and not result["full_goal_complete"]
    )


@pytest.mark.parametrize(
    "mutation",
    ("physical", "TT", "drop_model", "drop_node", "fake_pair", "weaken_line"),
)
def test_independent_replay_rejects_false_success_or_lost_population(
    tmp_path, mutation
):
    root = tmp_path / "input"
    shutil.copytree(FIXTURE, root)
    name = "A-native-reference-first.json"
    data = load(name, root)
    if mutation == "physical":
        data["physical_time_model_certified"] = True
    elif mutation == "TT":
        data["TT_derivative_certified"] = True
    elif mutation == "drop_model":
        data["models"].pop()
    elif mutation == "fake_pair":
        data["models"][0]["population"][0]["qualified_pairs"] = [
            ["0x0.0p+0", "0x0.0p+0"]
        ]
    elif mutation == "weaken_line":
        name = "plan-before-queries.json"
        data = load(name, root)
        data["original_lines"]["daily_rate_arcsec_per_day"] = "0.01"
    else:
        name = "A-first-analysis.json"
        data = load(name, root)
        data["queries"][0]["rows"].pop()
    (root / name).write_text(json.dumps(data))
    with pytest.raises(ValueError):
        (clocks if mutation == "drop_node" else references)(root, "A")
