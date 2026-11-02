"""No omission of a source qualification or switch of calculation receipt."""

from copy import deepcopy

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim
from fatebridge.validation.qimen import verify_qimen_pattern_quotes


@pytest.fixture
def receipt():
    spec = next(s for s in CATALOG if s.tool_name == "qimen")
    payload = execute_tool(
        spec,
        spec.request_model.model_validate(
            {
                "analysis_year": 2026,
                "analysis_month": 1,
                "analysis_day": 25,
                "analysis_hour": 12,
                "analysis_timezone": "Asia/Hong_Kong",
                "use_true_solar_time": False,
            }
        ),
        options=ExecutionOptions(
            as_of="2026-10-22T12:00:00+08:00",
        ),
    )
    index = next(
        i for i, p in enumerate(payload["qimen"]["patterns"]) if p["name"] == "三奇得使"
    )
    p = payload["qimen"]["patterns"][index]
    assert not p["qualification"]["condition_observed"]
    assert p["qualification"]["same_palace_conflicts"] == ["青龙逃走"]
    claim = CalculationClaim(
        path=f"qimen.patterns.{index}",
        value=deepcopy(p),
        run_id=payload["run_metadata"]["run_id"],
        business_output_sha256=payload["run_metadata"]["business_output_sha256"],
    )
    return payload, claim


def test_verified_quote_carries_conditions_and_keeps_semantic_scope_limited(receipt):
    payload, claim = receipt
    report = verify_qimen_pattern_quotes(payload, [claim])
    assert report["status"] == "verified_structured_pattern_quotes"
    assert not report["free_text_semantics_validated"]
    assert not report["real_world_efficacy_validated"]


@pytest.mark.parametrize(
    "mutation",
    [
        "drop_qualification",
        "change_condition",
        "erase_conflicts",
        "different_run",
        "name_only",
    ],
)
def test_quote_cannot_hide_conditions_or_use_a_different_receipt(receipt, mutation):
    payload, claim = receipt
    changed = claim.model_dump()
    if mutation == "drop_qualification":
        changed["value"].pop("qualification")
    elif mutation == "change_condition":
        changed["value"]["qualification"]["condition_observed"] = True
    elif mutation == "erase_conflicts":
        changed["value"]["qualification"]["same_palace_conflicts"] = []
    elif mutation == "different_run":
        changed["run_id"] = "another-run"
    else:
        changed["path"] += ".name"
        changed["value"] = claim.value["name"]
    report = verify_qimen_pattern_quotes(
        payload, [CalculationClaim.model_validate(changed)]
    )
    assert report["status"] == "rejected"
    assert report["errors"]


def test_projected_or_modified_original_payload_is_rejected(receipt):
    payload, claim = receipt
    projected = {"qimen": payload["qimen"], "run_metadata": payload["run_metadata"]}
    assert verify_qimen_pattern_quotes(projected, [claim])["status"] == "rejected"
    changed = deepcopy(payload)
    changed["qimen"]["assessment"]["authority_certified"] = True
    assert verify_qimen_pattern_quotes(changed, [claim])["status"] == "rejected"


def test_new_head_dependent_quote_cannot_hide_or_replace_hour_xun_binding():
    spec = next(s for s in CATALOG if s.tool_name == "qimen")
    payload = execute_tool(
        spec,
        spec.request_model.model_validate(
            {
                "analysis_year": 2026,
                "analysis_month": 1,
                "analysis_day": 21,
                "analysis_hour": 0,
                "analysis_timezone": "Asia/Hong_Kong",
                "use_true_solar_time": False,
                "qimen_options": {"ju_method": "chaibu"},
            }
        ),
        options=ExecutionOptions(as_of="2026-10-22T12:00:00+08:00"),
    )
    index = next(
        i
        for i, p in enumerate(payload["qimen"]["patterns"])
        if p["rule_id"] == "dragon_returns_head"
    )
    pattern = payload["qimen"]["patterns"][index]
    assert pattern["qualification"]["identity_binding"]["hidden_stem"] == "己"
    claim = CalculationClaim(
        path=f"qimen.patterns.{index}",
        value=deepcopy(pattern),
        run_id=payload["run_metadata"]["run_id"],
        business_output_sha256=payload["run_metadata"]["business_output_sha256"],
    )
    assert (
        verify_qimen_pattern_quotes(payload, [claim])["status"]
        == "verified_structured_pattern_quotes"
    )
    for change in ["remove_identity", "fixed_wu", "day_xun"]:
        altered = claim.model_dump()
        binding = altered["value"]["qualification"]["identity_binding"]
        if change == "remove_identity":
            altered["value"]["qualification"].pop("identity_binding")
        elif change == "fixed_wu":
            binding["hidden_stem"] = "戊"
        else:
            binding["xun_head"] = payload["qimen"]["day_xun_head"]
        assert (
            verify_qimen_pattern_quotes(
                payload, [CalculationClaim.model_validate(altered)]
            )["status"]
            == "rejected"
        )


def test_literal_day_identity_cannot_be_replaced_by_hour_head_in_a_quote():
    spec = next(s for s in CATALOG if s.tool_name == "qimen")
    payload = execute_tool(
        spec,
        spec.request_model.model_validate(
            {
                "analysis_year": 2026,
                "analysis_month": 1,
                "analysis_day": 15,
                "analysis_hour": 16,
                "analysis_timezone": "Asia/Hong_Kong",
                "use_true_solar_time": False,
                "qimen_options": {"ju_method": "chaibu"},
            }
        ),
        options=ExecutionOptions(as_of="2026-10-22T12:00:00+08:00"),
    )
    index = next(
        i
        for i, p in enumerate(payload["qimen"]["patterns"])
        if p["rule_id"] == "flying_day_stem"
    )
    pattern = payload["qimen"]["patterns"][index]
    assert pattern["qualification"]["stem_identity"]["effective_stem"] == "己"
    claim = CalculationClaim(
        path=f"qimen.patterns.{index}",
        value=deepcopy(pattern),
        run_id=payload["run_metadata"]["run_id"],
        business_output_sha256=payload["run_metadata"]["business_output_sha256"],
    )
    assert (
        verify_qimen_pattern_quotes(payload, [claim])["status"]
        == "verified_structured_pattern_quotes"
    )
    altered = claim.model_dump()
    altered["value"]["qualification"]["stem_identity"]["effective_stem"] = "戊"
    assert (
        verify_qimen_pattern_quotes(
            payload, [CalculationClaim.model_validate(altered)]
        )["status"]
        == "rejected"
    )
