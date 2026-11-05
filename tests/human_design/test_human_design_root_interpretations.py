"""All frozen roots, conditional donor changes and rehashed false receipts."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.astro import native_execution, runtime
from fatebridge.core.human_design_depth import fixing_reading
from fatebridge.core.human_design_root_interpretations import root_interpretations
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "tests/fixtures/human-design-root-interpretation-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
SPEC = next(s for s in CATALOG if s.key == "human_design")


def forbidden(*args, **kwargs):
    raise AssertionError("Pure verifier invoked a native producer")


def proof(run):
    return run["design_solver"]["numerical_precision"][
        "design_body_endpoint_assessment"
    ]["endpoint_interpretations"]


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


def test_unsupported_alternative_profile_is_not_repaired(complete):
    p = deepcopy(complete["activations"]["personality"])
    d = deepcopy(complete["activations"]["design"])
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
