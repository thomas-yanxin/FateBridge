"""Full frozen geocentric source population and refusal of false success."""

import hashlib
import json
import shutil
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.audit_astrodice_geocentric_clock import audit
from scripts.verify_astrodice_geocentric_clock import verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-geocentric-clock-v1"
MANIFEST_SHA = "e8bf6e1692f240be0a87caf968a353f471d7c70eca634bfc9ceed1cc9098f98a"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_entire_source_observations_and_old_failed_records_are_frozen():
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


def test_independent_proof_checks_every_observer_row():
    for cohort, rows in (("A", 6), ("B", 18)):
        proof = verify(FIXTURE, cohort)
        assert proof == load(cohort + "-independent-replay-first.json")
        assert proof["observer_rows_checked"] == rows


def test_full_model_denominators_and_original_error_lines_remain_visible():
    data = audit(FIXTURE)
    assert data == load("posthoc-population-audit-first.json")
    assert data["new_primary_contexts"] == 5 and data["new_candidate_holdouts"] == 0
    assert data["candidate_calls"] == 0
    assert data["original_fixed_lines"] == {
        "position_arcsec": "0.02",
        "daily_rate_arcsec_per_day": "0.002",
        "reference_quality_arcsec_per_day": "0.002",
    }
    for cohort, denominator in (("A", 3), ("B", 15)):
        summaries = [
            s
            for s in data["cohorts"][cohort]["summaries"]
            if s["population"] == "primary"
        ]
        assert len(summaries) == 8
        for s in summaries:
            assert s["denominator"] == denominator
            assert sum(s["statuses"].values()) == denominator
            assert sum(s["qualified_pair_counts"].values()) == denominator
            assert sum(s["receiver_counts"].values()) == denominator
    assert (
        not data["physical_time_model_certified"]
        and not data["numerical_tubes_certified"]
    )
    assert not data["internal_algorithm_certified"] and not data["full_goal_complete"]
    assert (
        data["production_acceptance_exit_code"] == 2
        and data["retained_overall_numeric_gate_exit_code"] == 1
    )
    assert not data["original_gates_rerun"]


@pytest.mark.parametrize(
    "mutation", ["physical", "algorithm", "drop", "family", "grid", "label", "pair"]
)
def test_verifier_rejects_promoted_claims_or_incomplete_population(tmp_path, mutation):
    root = tmp_path / "input"
    shutil.copytree(FIXTURE, root)
    saved = load("A-first-analysis.json", root)
    if mutation == "physical":
        saved["physical_time_model_certified"] = True
    elif mutation == "algorithm":
        saved["internal_algorithm_certified"] = True
    elif mutation == "drop":
        saved["queries"][0]["rows"].pop()
    elif mutation == "label":
        saved["queries"][0]["rows"][0]["observation"]["printed_JD"] = "2451545"
    else:
        families = saved["queries"][0]["rows"][0]["inference"]["profiles"][
            "printing_only"
        ]
        if mutation == "family":
            families.pop("absolute_JD_binary64")
        elif mutation == "grid":
            families["absolute_JD_binary64"]["receiver_grid_hex"] = ["0x0.0p+0"]
        else:
            families["absolute_JD_binary64"]["qualified_pairs_by_hypothesis"][
                "one_round_source_norm"
            ] = [["0x0.0p+0", "0x0.0p+0"]]
    (root / "A-first-analysis.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError):
        verify(root, "A")
