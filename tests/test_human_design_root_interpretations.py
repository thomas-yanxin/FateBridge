"""All frozen roots, conditional donor changes and rehashed false receipts."""

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.human_design_depth import fixing_reading
from fatebridge.core.human_design_native_positions import pack_native_positions
from fatebridge.core.human_design_root_bodies import derive_root_body_assessment
from fatebridge.core.human_design_root_interpretations import root_interpretations
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "tests/fixtures/human-design-root-interpretation-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
BEFORE_PATH = ROOT / "docs/validation/human-design-root-interpretation-before.json.gz"
BEFORE = json.loads(gzip.decompress(BEFORE_PATH.read_bytes()))
BODY_BEFORE = json.loads(
    (ROOT / "docs/validation/human-design-root-body-before.json").read_text()
)
SPEC = next(s for s in CATALOG if s.key == "human_design")


def forbidden(*args, **kwargs):
    raise AssertionError("Pure verifier invoked a native producer")


def proof(run):
    return run["design_solver"]["numerical_precision"][
        "design_body_endpoint_assessment"
    ]["endpoint_interpretations"]


def old_version_labels(value):
    if isinstance(value, list):
        return [old_version_labels(v) for v in value]
    if isinstance(value, dict):
        return {
            k: ("1.32.0" if k == "version" and v == "1.39.0" else old_version_labels(v))
            for k, v in value.items()
        }
    return value


def test_preregistered_cases_and_original_thresholds_retained():
    assert (
        hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()
        == "544ffcc661baf6c3a0deec5b604015efa2f05910503b28d9a4bfca3c2fe6d17a"
    )
    assert (
        hashlib.sha256(BEFORE_PATH.read_bytes()).hexdigest()
        == PLAN["frozen_before_sha256"]
        == "fc1769ac235eab8ae5dc3490d7a29dfc19789db06e334bf5fb78e74d7d42fbbd"
    )
    assert (
        [c["id"] for c in PLAN["cases"]]
        == [c["id"] for c in BEFORE["cases"]]
        == [c["id"] for c in BODY_BEFORE["cases"]]
    )
    assert len(PLAN["cases"]) == 7
    assert PLAN["unchanged_thresholds"] == {
        "astronomy_arcsec": 2.0,
        "physical_design_root_seconds": 5.0,
        "clock_seconds": 0.0002,
    }


@pytest.mark.parametrize("index", range(7))
def test_complete_frozen_interpretation_dependencies_before_new_producer(index):
    c = BODY_BEFORE["cases"][index]
    expected = BEFORE["cases"][index]
    evaluations = [
        {
            "jd_tt": e["jd_tt"],
            "source_role": (
                "activation"
                if e["jd_tt"] == c["original_solver"]["design_jd_tt"]
                else "root_bracket_activation"
            ),
            "native_positions": pack_native_positions(e["activations"]),
        }
        for e in c["endpoint_observations"]
    ]
    rebuilt = derive_root_body_assessment(
        c["original_solver"],
        c["original_personality"],
        c["original_selected_design"],
        "true",
        evaluations,
        require_swiss_files=False,
    )["endpoint_interpretations"]
    assert rebuilt["line_fixing_changes"] == expected["changes"]["line_fixing_changes"]
    for actual, snapshot in zip(
        rebuilt["candidates"], expected["snapshots"], strict=True
    ):
        assert actual["line_fixings_sha256"] == digest(
            snapshot["depth_evidence"]["line_fixings"]
        )
        for key in ("circuitry", "definition_bridging"):
            assert old_version_labels(actual[key]) == snapshot[key]
        profile = deepcopy(actual["profile_evidence"])
        assert profile["ruleset"]["version"] == "1.39.0"
        profile["ruleset"]["version"] = "1.32.0"
        assert profile == snapshot["profile_evidence"]
    plan = PLAN["cases"][index]
    summary = rebuilt["summary"]
    assert (
        summary["line_fixing_record_change_count"]
        == plan["expected_fixing_record_changes"]
    )
    assert (
        summary["line_fixing_state_change_count"]
        == plan["expected_fixing_state_changes"]
    )
    assert (
        summary["personality_fixing_record_change_count"]
        == plan["expected_personality_changes"]
    )
    assert summary["definition_bridging_changed"] == plan["expected_bridge_change"]
    assert summary["circuitry_changed"] == plan["expected_circuitry_change"]
    assert summary["complete_line_meanings_accepted"] is False


@pytest.mark.parametrize("mode", PLAN["modes"])
@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize("case", PLAN["cases"], ids=lambda c: c["id"])
def test_all_original_public_seconds_both_modes_and_backends(
    case, empty_files, mode, monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    run = execute_tool(SPEC, SPEC.request_model(**case["input"], node_mode=mode))
    p = proof(run)
    assert len(p["candidates"]) in (1, 2)
    assert all(
        len(c["fixing_states"]) == c["fixing_summary"]["activation_count"] == 26
        for c in p["candidates"]
    )
    assert "双侧26项" in run["interpretation"]["design_time_precision_meaning"]
    if mode == "true" and not empty_files:
        assert (
            p["summary"]["line_fixing_record_change_count"]
            == case["expected_fixing_record_changes"]
        )
        assert (
            p["summary"]["line_fixing_state_change_count"]
            == case["expected_fixing_state_changes"]
        )
        assert (
            p["summary"]["personality_fixing_record_change_count"]
            == case["expected_personality_changes"]
        )
        assert (
            p["summary"]["definition_bridging_changed"]
            == case["expected_bridge_change"]
        )
        assert p["summary"]["circuitry_changed"] == case["expected_circuitry_change"]
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    check = verify_human_design_reading(run)
    assert check["status"] == "verified_fixed_template_reading", check


@pytest.fixture(scope="module")
def complete():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        patch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        return execute_tool(
            SPEC,
            SPEC.request_model(
                **PLAN["cases"][1]["input"], birth_time_uncertainty_minutes=1
            ),
        )


def test_unchanged_personality_neptune_changes_when_design_moon_moves(complete):
    p = proof(complete)
    row = next(r for r in p["line_fixing_changes"] if r["side"] == "personality")
    assert row["body"] == "Neptune"
    assert (
        (row["before"]["gate"], row["before"]["line"])
        == (row["after"]["gate"], row["after"]["line"])
        == (5, 3)
    )
    assert (row["before"]["fixing_state"], row["after"]["fixing_state"]) == (
        "exaltation",
        "juxtaposition",
    )
    assert row["after"]["fixing_planets"]["detriment"] == [
        {
            "side": "design",
            "body": "Moon",
            "gate": 15,
            "line": 1,
            "relation": "harmonic_gate",
            "calculation_path": "activations.design.1",
        }
    ]
    assert row["after"]["reading"] == fixing_reading(row["after"])
    moon = next(r for r in p["line_fixing_changes"] if r["body"] == "Moon")
    assert moon["fixing_state_changed"] is False
    assert moon["before"]["fixing_planets"] != moon["after"]["fixing_planets"]
    assert "双侧26项" in complete["interpretation"]["design_time_precision_meaning"]


@pytest.mark.parametrize("bad", PLAN["required_negative_receipts"])
def test_every_preregistered_rehashed_corruption_rejected(complete, bad, monkeypatch):
    run = deepcopy(complete)
    p = proof(run)
    if bad == "missing_interpretation":
        del run["design_solver"]["numerical_precision"][
            "design_body_endpoint_assessment"
        ]["endpoint_interpretations"]
    elif bad == "changed_fixing_digest":
        p["candidates"][0]["line_fixings_sha256"] = "0" * 64
    elif bad == "changed_state_same_counts":
        p["candidates"][0]["fixing_states"][0][3] = "invented"
    elif bad == "removed_personality_change":
        p["line_fixing_changes"] = [
            r for r in p["line_fixing_changes"] if r["side"] != "personality"
        ]
        p["summary"]["line_fixing_record_change_count"] -= 1
        p["summary"]["line_fixing_state_change_count"] = 0
        p["summary"]["personality_fixing_record_change_count"] = 0
    elif bad == "mixed_endpoint_donor":
        row = p["line_fixing_changes"][0]["after"]
        row["fixing_planets"]["detriment"][0]["gate"] = 12
        row["reading"] = fixing_reading(row)
    elif bad == "changed_reading":
        p["line_fixing_changes"][0]["after"]["reading"] = "必定成功"
    elif bad == "changed_bridge_solution":
        p["candidates"][0]["definition_bridging"]["minimum_solutions"][0][
            "added_gates"
        ][0] = 64
    elif bad == "changed_circuitry":
        p["candidates"][0]["circuitry"]["defined_channel_count"] += 1
    elif bad == "changed_profile":
        p["candidates"][0]["profile_evidence"]["profile"] = "1/5"
    elif bad == "forged_completeness":
        p["summary"]["complete_line_meanings_accepted"] = True
    elif bad == "changed_source":
        p["candidates"][0]["source_pdf_sha256"] = "0" * 64
    elif bad == "changed_summary":
        run["design_solver"]["numerical_precision"]["design_body_endpoint_summary"][
            "interpretation_summary"
        ]["line_fixing_record_change_count"] = 0
    elif bad == "missing_sample_interpretation":
        sample = next(
            s
            for s in run["time_sensitivity"]["evaluation_witnesses"]["samples"]
            if s["birth_utc"] != run["birth_utc"]
        )
        del sample["design_solver"]["numerical_precision"][
            "design_body_endpoint_assessment"
        ]["endpoint_interpretations"]
    elif bad == "changed_backend_interpretation":
        ref = run["ephemeris_backend_comparison"]["reference_chart"]
        proof(ref)["candidates"][0]["line_fixings_sha256"] = "0" * 64
    else:
        raise AssertionError(bad)
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    monkeypatch.setattr(runtime, "ephemeris_call", forbidden)
    monkeypatch.setattr(native_execution, "calculate", forbidden)
    assert verify_human_design_reading(run)["status"] == "rejected"


def test_unsupported_alternative_profile_is_not_repaired():
    c = BODY_BEFORE["cases"][0]
    p, d = deepcopy(c["original_personality"]), deepcopy(c["original_selected_design"])
    for rows, line in ((p, 1), (d, 5)):
        for row in rows:
            if row["body"] in {"Sun", "Earth"}:
                row["line"] = line
    result = root_interpretations(p, [d])
    assert (
        result["candidates"][0]["profile_evidence"]["status"]
        == "inconsistent_profile_combination"
    )
    assert result["candidates"][0]["profile_evidence"]["profile"] == "1/5"
    assert result["line_fixing_changes"] == []
