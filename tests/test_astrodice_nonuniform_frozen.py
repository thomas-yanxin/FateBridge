"""Full population, unchanged old failures, independent exact replay."""

import hashlib
import json
import shutil
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.verify_astrodice_nonuniform_reference import (
    bound_proof,
    independent_system,
    inspect_angles,
    verify,
)

FIXTURE = Path(__file__).parent / "fixtures/astrodice-nonuniform-v1"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_entire_old_and_new_evidence_manifest_is_frozen():
    assert (
        hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
        == "04c9283884a39f83f38a927297bc4162611a0e8caa0c287c806ed715451913ed"
    )
    for name, digest in load("manifest.json")["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    baseline = load("baseline-grid5/manifest.json")["files"]
    assert len(baseline) == 302
    for name, digest in baseline.items():
        assert (
            hashlib.sha256((FIXTURE / "baseline-grid5" / name).read_bytes()).hexdigest()
            == digest
        )


def test_independent_source_and_all_point_polynomial_replay():
    for cohort in ("A", "B"):
        assert verify(FIXTURE, cohort) == load(
            cohort + "-independent-replay-first.json"
        )


def test_sampling_points_are_one_fresh_context_not_577_independent_holdouts():
    plan = load("plan-before-queries.json")
    assert (
        plan["new_TT_source_conditions"]
        == plan["new_independent_astronomical_contexts"]
        == 1
    )
    assert (
        plan["new_primary_epoch_nodes"] == 577 and plan["new_candidate_holdouts"] == 0
    )
    assert plan["original_lines"] == {
        "position_arcsec": "0.02",
        "daily_rate_arcsec_per_day": "0.002",
        "reference_quality_arcsec_per_day": "0.002",
    }
    assert not plan["original_odd_polynomial_gate_replaced"]
    for cohort in ("A", "B"):
        d = load(cohort + "-first-analysis.json")
        for profile, rows in d["clock_population"].items():
            assert [r["offset_seconds"] for r in rows] == list(range(-1440, 1441, 5))
            fits = d["fits"][profile]
            if not all(r["qualified"] for r in rows):
                assert (
                    fits["status"] == "full_clock_population_unqualified"
                    and fits["required_nodes"] == 577
                )
            else:
                assert len(fits["all_windows"]) == 22
                assert not fits["quality"]["production_reference_qualified"]
        assert (
            not d["OBSERVER_vector_clock_identity_certified"]
            and not d["full_goal_complete"]
        )
        assert (
            d["production_acceptance_exit_code"] == 2
            and d["retained_overall_numeric_gate_exit_code"] == 1
        )


def test_same_order_nominal_controls_have_all_point_exact_certificates():
    plan = load("plan-before-queries.json")
    for cohort in ("A", "B"):
        data = load(
            cohort
            + (
                "-nominal-control-corrected.json"
                if cohort == "A"
                else "-nominal-control-first.json"
            )
        )
        angles = inspect_angles(FIXTURE, cohort, plan)
        epochs = {o: Q(o) for o in angles}
        assert data["primary_nodes"] == 577 and not data["original_scores_replaced"]
        assert [(r["window_seconds"], r["full_degree"]) for r in data["fits"]] == [
            (w, d) for w in plan["windows_seconds"] for d in (5, 7)
        ]
        checked = 0
        for row in data["fits"]:
            w, d = row["window_seconds"], row["full_degree"]
            for axis, item in enumerate(row["axes"]):
                a, b, base, scale = independent_system(angles, epochs, w, d, axis)
                if all(
                    c["status"] == "exact_primal_dual_optimum"
                    for c in item["certificates"]
                ):
                    low = (
                        (base[1] + scale * bound_proof(a, b, item["certificates"][0]))
                        * 86400
                        / w
                    )
                    high = (
                        (base[1] - scale * bound_proof(a, b, item["certificates"][1]))
                        * 86400
                        / w
                    )
                    assert item[
                        "derivative_interval_arcsec_per_nominal_TT_day"
                    ] == list(map(str, (low, high)))
                    checked += 2
        assert checked == data["independent_exact_certificates_checked"]


@pytest.mark.parametrize("mutation", ["promote", "drop", "body", "grid"])
def test_independent_verifier_rejects_success_forgery_or_lost_rows(tmp_path, mutation):
    root = tmp_path / "input"
    shutil.copytree(FIXTURE, root)
    value = load("A-first-analysis.json", root)
    if mutation == "promote":
        value["full_goal_complete"] = True
    elif mutation == "drop":
        value["queries"][0]["rows"].pop()
    elif mutation == "body":
        value["queries"][0]["body"] = "Venus"
    else:
        profile = next(iter(value["queries"][0]["rows"][0]["grid"]))
        value["queries"][0]["rows"][0]["grid"][profile]["six_component_matches"] = [
            "0x0.0p+0"
        ]
    (root / "A-first-analysis.json").write_text(json.dumps(value))
    with pytest.raises(ValueError):
        verify(root, "A")
