"""A birth-origin definition does not settle all returns or retrograde priority."""

from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.human_design_cycles import origin_source_evidence
from fatebridge.services.replay_metadata import digest
from fatebridge.validation.human_design import verify_human_design_reading
from tests.human_design_current import complete_run


@pytest.fixture(scope="module")
def complete():
    return complete_run(
        birth_year=1980,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        cycle_reference_datetime="2029-07-01T00:00:00Z",
    )


def test_explicit_birth_wording_and_personality_epoch_binding_are_separate(complete):
    context = complete["cycle_context"]
    summary = complete["cycle_summary"]
    assert context["ruleset"]["version"] == "1.6.0"
    assert "天王星出生原点有公开明文" in context["scope"]
    assert "土星/凯龙起点及各项首末触优先未定" in context["scope"]
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
def test_rehashed_source_and_priority_forgeries_are_rejected(complete, mutation):
    run = deepcopy(complete)
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
    if mutation in {"unknown_version", "false_legacy"}:
        assert {e["code"] for e in result["errors"]} == {
            "incomplete_or_malformed_cycle_witnesses"
        }
    else:
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
