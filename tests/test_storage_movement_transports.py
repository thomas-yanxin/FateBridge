"""One real public calculation supplies root receipts, text and all transports."""

import asyncio
from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_storage_movement import StorageMovementEffect
from fatebridge.core.storage_movement import storage_movement_snapshot_lines
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_strength_v2 import pillars

PAYLOAD = {
    "name": "虚构四墓冲动回归",
    "birth_year": 2024,
    "birth_month": 10,
    "birth_day": 22,
    "birth_hour": 0,
    "birth_minute": 0,
    "birth_timezone": "Asia/Shanghai",
    "use_true_solar_time": False,
    "gender": "男",
    "analysis_year": 2026,
    "analysis_month": 10,
    "analysis_day": 12,
}


def test_storage_receipt_and_explanation_match_on_rest_mcp_cli(rest, tmp_path, capsys):
    spec = SPECS["bazi_birth"]
    response = rest.post(
        spec.rest_path, json=PAYLOAD, params={"response_char_limit": 0}
    )
    code, local = call_cli(
        spec, PAYLOAD, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, PAYLOAD))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    result = response.json()
    assert business(result) == business(local) == business(protocol.structured_content)
    birth = result["bazi_birth"]
    assessment = birth["day_master"]["assessment"]
    assert assessment["method_id"] == "season_root_revelation_relations_v11"
    events = [e for e in assessment["relations"] if "storage_effect" in e]
    assert len(events) == 1 and events[0]["positions"] == ["year", "month"]
    assert (
        birth["structure_profile"]["evidence_chain"]["strength_context"][
            "storage_movement_effects"
        ]
        == events
    )
    assert "年支辰、月支戌" in result["snapshot_text"]
    assert "工程约定" in result["snapshot_text"]
    for line in storage_movement_snapshot_lines(assessment):
        assert line in result["snapshot_text"]
    receipt = result["run_metadata"]
    claim = CalculationClaim(
        path="bazi_birth.day_master.assessment.relations.0.storage_effect.earth_energy_bonus",
        value=0.0,
        run_id=receipt["run_id"],
        business_output_sha256=receipt["business_output_sha256"],
    )
    assert (
        verify_calculation_claims(result, [claim])["status"]
        == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(result, [claim.model_copy(update={"value": 2.0})])[
            "status"
        ]
        == "rejected"
    )


def test_published_nested_projection_and_typed_receipts_reject_fabricated_facts(rest):
    response = rest.post(
        SPECS["bazi_birth"].rest_path,
        json=PAYLOAD,
        params={
            "fields": [
                "bazi_birth.structure_profile.evidence_chain.strength_context.storage_movement_effects"
            ],
            "strict_fields": "true",
            "include_snapshot_text": "false",
        },
    )
    assert response.status_code == 200, response.text
    effects = response.json()["bazi_birth"]["structure_profile"]["evidence_chain"][
        "strength_context"
    ]["storage_movement_effects"]
    effect = effects[0]["storage_effect"]
    StorageMovementEffect.model_validate(effect)
    for change in [{"earth_energy_bonus": 1.0}, {"formation_status": "formed"}]:
        with pytest.raises(ValidationError):
            StorageMovementEffect.model_validate({**effect, **change})
    altered = deepcopy(effect)
    altered["root_effects"][0]["event_retention_multiplier"] = "1.0"
    with pytest.raises(ValidationError):
        StorageMovementEffect.model_validate(altered)
    altered = deepcopy(effect)
    soil = next(r for r in altered["root_effects"] if r["element"] == "土")
    soil["event_retention_multiplier"] = 0.5
    with pytest.raises(ValidationError, match="统一减损"):
        StorageMovementEffect.model_validate(altered)


def test_shared_evidence_copies_actual_receipt_and_explanation_reads_supplied_factor():
    chart = pillars("甲辰 丙戌 戊巳 庚寅")
    strength = ElementAnalysis.analyze_day_master_strength(chart)
    evidence = build_natal_evidence(chart, strength)
    supplied = evidence["strength_context"]["storage_movement_effects"]
    assert supplied
    supplied[0]["storage_effect"]["earth_energy_bonus"] = 5.0
    assert (
        strength["assessment"]["relations"][0]["storage_effect"]["earth_energy_bonus"]
        == 0
    )
    alternate = deepcopy(strength["assessment"])
    alternate["relations"][0]["storage_effect"]["water_retention_policy"] = 0.6
    for root in alternate["relations"][0]["storage_effect"]["root_effects"]:
        if root["element"] == "水":
            root["event_retention_multiplier"] = 0.6
    assert "水根本事件保留系数0.6" in "\n".join(
        storage_movement_snapshot_lines(alternate)
    )
    assert storage_movement_snapshot_lines({"relations": []}) == []


def test_uncomputed_effects_are_not_an_empty_calculated_event_list():
    chart = pillars("甲辰 丙戌 戊巳 庚寅")
    result = build_natal_evidence(chart)
    assert result["strength_context"]["storage_movement_effects"] is None
    without_storage = pillars("甲寅 丙午 戊子 庚申")
    result = build_natal_evidence(
        without_storage, ElementAnalysis.analyze_day_master_strength(without_storage)
    )
    assert result["strength_context"]["storage_movement_effects"] == []
