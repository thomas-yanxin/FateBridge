"""Frozen full-population evidence; conditional clocks are not accuracy scores."""

import hashlib
import json
import shutil
from fractions import Fraction as Q
from pathlib import Path

import pytest

from scripts.astrodice_observer_origin import analyze
from scripts.audit_astrodice_observer_radius_clock import audit
from scripts.verify_astrodice_observer_radius_clock import verify

FIXTURE = Path(__file__).parent / "fixtures/astrodice-observer-radius-v1"
MANIFEST_SHA = "2f690639b13f0e85047192c0ccc5336b77a7a6a305512726950b57b613748e9e"


def load(name, root=FIXTURE):
    return json.loads((root / name).read_text())


def test_entire_contract_radius_and_original_failure_evidence_is_frozen():
    assert (
        hashlib.sha256((FIXTURE / "manifest.json").read_bytes()).hexdigest()
        == MANIFEST_SHA
    )
    for path, digest in load("manifest.json")["files"].items():
        assert hashlib.sha256((FIXTURE / path).read_bytes()).hexdigest() == digest
    source = load("radius-clock/source-records/manifest.json")["files"]
    assert len(source) == 33
    for path, digest in source.items():
        assert (
            hashlib.sha256(
                (FIXTURE / "radius-clock/source-records" / path).read_bytes()
            ).hexdigest()
            == digest
        )
    assert (FIXTURE / "posthoc-population-audit-first.json").read_bytes() == b""
    assert load("posthoc-population-audit-first-process.json")["exit_code"] == 1
    assert load("posthoc-population-audit-corrected-process.json")["exit_code"] == 0


def test_full_independent_radius_angular_rounding_and_geometry_replay():
    assert analyze(FIXTURE, "A") == load("A-first-analysis.json")
    for cohort in ("A", "B"):
        assert verify(FIXTURE / "radius-clock", cohort) == load(
            "radius-clock/" + cohort + "-independent-replay-first.json"
        )


def test_posthoc_set_audit_retains_all_profiles_families_and_rounding_models():
    result = audit(FIXTURE)
    assert result == load("posthoc-population-audit-corrected.json")
    assert result["new_primary_contexts"] == 5 and result["new_candidate_holdouts"] == 0
    assert result["original_fixed_lines"] == {
        "position_arcsec": "0.02",
        "daily_rate_arcsec_per_day": "0.002",
        "reference_quality_arcsec_per_day": "0.002",
    }
    for cohort, denominator in (("A", 3), ("B", 15)):
        summaries = result["cohorts"][cohort]["summaries"]
        primary = [s for s in summaries if s["population"] == "primary"]
        assert len(primary) == 8 and all(
            s["denominator"] == denominator for s in primary
        )
        for s in primary:
            assert sum(s["statuses"].values()) == denominator
            assert sum(s["observer_point_counts"].values()) == denominator
        for hypothesis in ("one_round_source_norm", "two_round_source_norm"):
            cases = [
                s
                for s in result["cohorts"][cohort]["details"]
                if s["role"] != "auxiliary_not_primary"
                and s["profile"] == "printing_plus_64_ULP_hypothesis"
                and s["coordinate_family"] == "seconds_from_J2000_binary64"
                and s["rounding_hypothesis"] == hypothesis
            ]
            disjoint = [s for s in cases if s["status"] == "conditionally_disjoint"]
            assert len(disjoint) == 1 and disjoint[0]["encoding"] == "JD"
            assert disjoint[0]["observer_minus_geometry_seconds"] == [
                "1/32768" if cohort == "A" else "-1/16384"
            ]
            assert (
                sum(s["status"] == "conditionally_compatible" for s in cases)
                == denominator - 1
            )
    assert (
        not result["physical_time_model_certified"]
        and not result["Earth_view_clock_equivalence_certified"]
    )
    assert (
        result["production_acceptance_exit_code"] == 2
        and result["retained_overall_numeric_gate_exit_code"] == 1
    )
    assert not result["full_goal_complete"]


def test_original_farkas_failures_are_unchanged_and_strictly_negative():
    name = "radius-clock/retained/original-Farkas-replay.json"
    old = FIXTURE.parent / "astrodice-nonuniform-v1/original-Farkas-replay.json"
    assert (FIXTURE / name).read_bytes() == old.read_bytes()
    data = load(name)
    assert data["count"] == 5 and data["all_original_contradictions_preserved"]
    assert not data["original_results_regraded"]
    assert all(Q(w["contradiction"]) < 0 for w in data["witnesses"])


@pytest.mark.parametrize(
    "mutation", ["physical", "transfer", "drop", "family", "grid", "label"]
)
def test_independent_replay_rejects_promotion_missing_rows_and_forged_grids(
    tmp_path, mutation
):
    root = tmp_path / "input"
    shutil.copytree(FIXTURE / "radius-clock", root)
    saved = load("A-first-analysis.json", root)
    if mutation == "physical":
        saved["physical_time_model_certified"] = True
    elif mutation == "transfer":
        saved["Earth_view_clock_equivalence_certified"] = True
    elif mutation == "drop":
        saved["observer_queries"][0]["rows"].pop()
    elif mutation == "label":
        saved["observer_queries"][0]["rows"][0]["observation"][
            "printed_JD_TT"
        ] = "2451545"
    else:
        families = saved["observer_queries"][0]["rows"][0]["inference"]["profiles"][
            "printing_only"
        ]["families"]
        if mutation == "family":
            families.pop("absolute_JD_binary64")
        else:
            families["seconds_from_J2000_binary64"]["emission_grid_hex"] = ["0x0.0p+0"]
    (root / "A-first-analysis.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError):
        verify(root, "A")
