"""A birth-origin definition does not settle all returns or retrograde priority."""

import gzip
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.human_design_cycles import origin_source_evidence
from fatebridge.services.replay_metadata import digest
from fatebridge.validation.human_design import verify_human_design_reading
from tests.human_design_policy_expectation import expected_historical_proof

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/validation/human-design-cycle-origin-v2/evidence"
BEFORE = json.loads(
    gzip.decompress((BASE / "before-complete-run.json.gz").read_bytes())
)
AFTER = json.loads(
    gzip.decompress((BASE / "release-complete-run.json.gz").read_bytes())
)


def test_original13_cycle_receipt_still_has_exactly_the_same_verification():
    assert verify_human_design_reading(BEFORE["run"]) == expected_historical_proof(
        BEFORE["run"], BEFORE["proof"]
    )
    assert BEFORE["run"]["cycle_context"]["ruleset"]["version"] == "1.3.0"


def test_new_evidence_preserves_all48064_numerical_witnesses_and_seven_contacts():
    old, new = BEFORE["run"], AFTER["run"]
    assert old["activations"] == new["activations"]
    assert old["design_solver"] == new["design_solver"]
    assert old["time_scales"] == new["time_scales"]
    assert (
        old["cycle_context"]["source_evidence"]
        == new["cycle_context"]["source_evidence"]
    )
    rows = [
        {k: v for k, v in row.items() if k != "origin_source_evidence"}
        for row in new["cycle_context"]["bodies"]
    ]
    assert rows == old["cycle_context"]["bodies"]
    assert sum(len(r["evaluation_witnesses"]) for r in rows) == 48064
    assert sum(len(r["contacts"]) for r in rows) == 7
    assert verify_human_design_reading(new) == expected_historical_proof(
        new, AFTER["proof"]
    )


def test_explicit_birth_wording_and_personality_epoch_binding_are_separate():
    context = AFTER["run"]["cycle_context"]
    summary = AFTER["run"]["cycle_summary"]
    assert context["ruleset"]["version"] == "1.4.2"
    assert "天王星出生原点有公开明文" in summary["scope"]
    assert "土星/凯龙起点及各项首末触优先未定" in summary["scope"]
    for body in context["bodies"]:
        evidence = body["origin_source_evidence"]
        assert evidence["body"] == body["body"]
        assert evidence["contact_priority"] == "unresolved_in_captured_primary_sources"
        assert evidence["unique_traditional_phase_assigned"] is False
        if body["body"] == "Uranus":
            assert evidence["source_origin"] == "birth_position"
            assert (
                evidence["source_origin_status"] == "explicit_birth_position_definition"
            )
            assert evidence["numerical_origin"] == "personality_birth_epoch"
            assert (
                "not in the Uranus-opposition sentence"
                in evidence["epoch_binding_basis"]
            )
            assert evidence["source"]["heading"] == "Uranus Opposition"
            assert (
                evidence["source"]["quote_sha256"]
                == "646ed48912a1ab4e834c38c210067699b6f403c6e7178ff626ee2272787852b8"
            )
        else:
            assert evidence["source_origin"] is None and evidence["source"] is None
            assert (
                evidence["source_origin_status"]
                == "unresolved_in_captured_primary_sources"
            )
    assert summary["sixth_line"]["current_phase"] is None
    assert context["continuous_completeness_certified"] is False
    assert context["timing_accuracy_certified"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "design_origin",
        "saturn_extrapolation",
        "first_contact",
        "forged_source",
        "removed_evidence",
        "unknown_version",
        "false_legacy",
    ],
)
def test_rehashed_source_and_priority_forgeries_are_rejected(mutation):
    run = deepcopy(AFTER["run"])
    context = run["cycle_context"]
    if mutation == "unknown_version":
        context["ruleset"]["version"] = "99.0.0"
    elif mutation == "false_legacy":
        context["ruleset"]["version"] = "1.3.0"
    else:
        target = context["bodies"][1]["origin_source_evidence"]
        if mutation == "design_origin":
            target["source_origin"] = "design_position"
        elif mutation == "saturn_extrapolation":
            context["bodies"][0]["origin_source_evidence"] = deepcopy(target)
        elif mutation == "first_contact":
            target["contact_priority"] = "first_contact_is_authoritative"
        elif mutation == "forged_source":
            target["source"]["quote_sha256"] = "0" * 64
        else:
            del context["bodies"][1]["origin_source_evidence"]
    run["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in run.items() if k != "run_metadata"}
    )
    result = verify_human_design_reading(run)
    assert result["status"] == "rejected"
    assert {e["code"] for e in result["errors"]} & {
        "cycle_contact_derivation_mismatch",
        "cycle_summary_derivation_mismatch",
    }


def test_returned_origin_evidence_cannot_change_the_source_catalogue():
    first = origin_source_evidence("Uranus")
    first["source"]["heading"] = "tampered"
    first["source_origin"] = "design"
    assert origin_source_evidence("Uranus")["source"]["heading"] == "Uranus Opposition"
    with pytest.raises(ValueError, match="Unknown Human Design cycle body"):
        origin_source_evidence("Pluto")
