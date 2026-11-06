"""Review closure, actionable uncertainty and object identity across transports."""

import asyncio
import json
from copy import deepcopy

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import assess
from tests.fengshui.test_fengshui_layout import facing_only
from tests.fengshui.test_fengshui_supplements import (
    adjustment_inputs,
    annual_inputs,
    form_inputs,
)
from tests.fengshui.test_fengshui_surfaces_authored import surface_input
from tests.support.mcp_result_assertions import without_transport
from tests.support.transports import rest_client


def progress(inputs):
    result = assess(**inputs)
    layout = result["layout_analysis"]
    assert result["coverage"]["analysis_progress"] == layout["analysis_progress"]
    return result, layout["analysis_progress"]


@pytest.mark.parametrize(
    "inputs,branch",
    [
        (annual_inputs(), "layout_analysis.annual_remedies.findings"),
        (adjustment_inputs(), "layout_analysis.element_remedies"),
    ],
)
def test_remedy_confirmation_identifies_its_actual_branch_and_action(inputs, branch):
    result, review = progress(inputs)
    layout = result["layout_analysis"]
    remedies = (
        layout["annual_remedies"]["findings"]
        if "annual_remedies" in branch
        else layout["element_remedies"]
    )
    assert remedies
    for remedy in remedies:
        assert remedy["pending_confirmations"]
        assert all(
            p["path"].startswith(branch + ".") and p["action_id"] == remedy["action_id"]
            for p in remedy["pending_confirmations"]
        )
    assert any(
        p["path"].startswith(branch + ".") for p in review["pending_confirmations"]
    )


@pytest.mark.parametrize("purpose", ["bed", "stove"])
def test_surface_and_form_identity_rejects_incompatible_purpose_without_placements(
    purpose,
):
    inputs = surface_input()
    inputs["form_observations"] = form_inputs(purpose=purpose)["form_observations"]
    inputs["form_observations"][0]["object_id"] = "work-surface"
    assert not inputs.get("placements")
    with pytest.raises(ValidationError, match="桌面与形态用途不一致"):
        AssessRequest.model_validate(inputs)
    inputs["form_observations"][0]["object_id"] = "different-object"
    AssessRequest.model_validate(inputs)


def test_same_desk_identity_is_valid_for_independent_surface_and_form():
    inputs = surface_input()
    inputs["form_observations"] = form_inputs()["form_observations"]
    inputs["form_observations"][0]["object_id"] = "work-surface"
    result, review = progress(inputs)
    assert review["assessment_complete"]
    assert review["rule_coverage_counts"] == {
        "supported": 4,
        "confirmed_unsupported": 0,
        "unknown": 0,
    }
    assert len(result["rulesets"]) == len(result["rule_trace"]) == 2


def test_calculation_can_finish_before_action_permission_and_space_are_known():
    inputs = surface_input()
    constraints = inputs["surface_constraints"][0]
    del constraints["can_move_items"]
    del constraints["feasible_zones"]
    result, review = progress(inputs)
    assert result["status"] == result["layout_analysis"]["status"] == "complete"
    assert review["calculation_status"] == "complete"
    assert review["rule_coverage_status"] == "reviewed"
    assert review["assessment_complete"]
    assert review["action_readiness"] == "needs_confirmation"
    assert {p["reason"] for p in review["pending_confirmations"]} == {
        "confirm_action_permission",
        "confirm_target_zone_feasibility",
    }
    assert all(p["required_for"] == "action" for p in review["pending_confirmations"])
    assert review["interpretation_status"] == "available"
    assert review["follow_up"]["conclusion_candidates"] == []
    assert review["follow_up"]["execution_only"] == list(
        dict.fromkeys(p["path"] for p in review["pending_confirmations"])
    )


def test_confirmed_no_rule_item_finishes_review_without_changing_legacy_partial():
    inputs = surface_input()
    inputs["surface_layouts"][0]["items"][0].update(
        representation="other", label="手机", evidence="已确认普通手机，无作者代表属性"
    )
    result, review = progress(inputs)
    assert result["status"] == "partial"
    assert review["calculation_status"] == "complete"
    assert review["rule_coverage_status"] == "reviewed"
    assert review["assessment_complete"]
    assert review["rule_coverage_counts"] == {
        "supported": 0,
        "confirmed_unsupported": 1,
        "unknown": 0,
    }
    assert review["pending_confirmations"] == []
    item = result["layout_analysis"]["surface_analysis"]["findings"][0][
        "item_findings"
    ][0]
    assert item["rule_coverage_status"] == "reviewed_unsupported"
    assert review["interpretation_status"] == "scope_only"
    assert review["follow_up"]["conclusion_candidates"] == []
    assert review["follow_up"]["execution_only"] == []


@pytest.mark.parametrize("basis", ["user_confirmed", "image_observed"])
def test_one_known_form_fact_can_be_explained_before_other_checks_and_actions(basis):
    inputs = form_inputs()
    inputs["form_observations"] = [
        {
            "object_id": "desk",
            "purpose": "desk",
            "entrance_visible": False,
            "observation_basis": basis,
            "evidence": "本次只观察入口视野，未判断其余条件",
        }
    ]
    result, review = progress(inputs)
    assert not review["assessment_complete"]
    assert review["interpretation_status"] == (
        "conditional" if basis == "image_observed" else "available"
    )
    follow_up = review["follow_up"]
    assert follow_up["conclusion_candidates"]
    assert follow_up["execution_only"]
    assessment_paths = {
        p["path"]
        for p in review["pending_confirmations"]
        if p["required_for"] == "assessment"
    }
    assert set(follow_up["conclusion_candidates"]) == assessment_paths
    assert not assessment_paths.intersection(follow_up["execution_only"])
    assert follow_up["selection_policy"] == "ask_only_if_changes_requested_conclusion"
    check = result["layout_analysis"]["form_analysis"]["findings"][0]["checks"][0]
    assert check["finding"] == "opposes_rule"
    assert check["adjustment"]
    assert check["action_status"] != "ready"


def test_unknown_checks_without_an_observed_predicate_do_not_create_a_judgment():
    inputs = form_inputs()
    inputs["form_observations"] = [
        {
            "object_id": "desk",
            "purpose": "desk",
            "entrance_position": "left",
            "observation_basis": "image_observed",
            "evidence": "只看到入口在左侧，视野、直冲和靠背均未知",
        }
    ]
    _, review = progress(inputs)
    assert review["interpretation_status"] == "insufficient_evidence"
    assert not review["assessment_complete"]


def test_optional_candidate_geometry_does_not_reopen_current_explanation():
    from tests.fengshui.test_fengshui_sourced_contracts import relation_candidate

    inputs = relation_candidate()
    del inputs["layout_alternatives"][0]["physically_feasible"]
    _, review = progress(inputs)
    assert review["interpretation_status"] == "available"
    assert review["follow_up"]["conclusion_candidates"] == []
    assert any(
        "physically_feasible" in path for path in review["follow_up"]["execution_only"]
    )


def test_complete_annual_reference_can_be_explained_without_object_sectors():
    result, review = progress(
        {"methods": ["annual_stars"], "effective_year": 2026, "analyze_layout": True}
    )
    assert review["interpretation_status"] == "available"
    assert not review["assessment_complete"]
    assert result["layout_analysis"]["placement_findings"] == []
    assert result["layers"]["annual_stars"]["palaces"]


def test_limited_implementation_without_chart_facts_still_needs_evidence():
    _, review = progress(
        {
            "methods": ["xuankong_natal"],
            "analyze_layout": True,
            "xuankong": {"interpretation": {}},
        }
    )
    assert review["interpretation_status"] == "insufficient_evidence"
    assert review["follow_up"]["conclusion_candidates"]


def test_known_material_reference_survives_an_unrelated_unknown_attribute():
    from tests.fengshui.test_fengshui_material_facts import material_request

    inputs = material_request(shape="round")
    inputs["environmental_context"]["material_facts"].append(
        {
            "fact_id": "unknown-colour",
            "object_id": "item",
            "colour": "unknown",
            "observation_basis": "user_confirmed",
            "evidence": "颜色未知，不影响已确认器形参考",
        }
    )
    _, review = progress(inputs)
    assert review["interpretation_status"] == "available"
    assert not review["assessment_complete"]


@pytest.mark.parametrize("representation", ["unknown", "other", "living_plant"])
def test_photo_or_unknown_representation_is_not_confirmed_unsupported(representation):
    inputs = surface_input()
    inputs["surface_layouts"][0]["items"][0].update(
        representation=representation, observation_basis="image_observed"
    )
    _, review = progress(inputs)
    assert review["calculation_status"] == "partial"
    assert not review["assessment_complete"]
    assert review["rule_coverage_counts"]["unknown"] == 1
    assert review["rule_coverage_counts"]["confirmed_unsupported"] == 0
    assert any(
        p["reason"] == "confirm_item_representation"
        and p["item_id"] == "specimen"
        and p["required_for"] == "assessment"
        for p in review["pending_confirmations"]
    )


def test_user_uncertain_representation_has_a_machine_readable_confirmation_reason():
    inputs = surface_input()
    inputs["surface_layouts"][0]["items"][0]["representation"] = "unknown"
    _, review = progress(inputs)
    assert review["rule_coverage_status"] == "needs_confirmation"
    assert not review["assessment_complete"]
    assert review["pending_confirmations"][0]["reason"] == "confirm_item_representation"


def test_action_states_follow_permission_without_changing_calculated_rule():
    inputs = surface_input()
    ready, ready_progress = progress(inputs)
    constraints = inputs["surface_constraints"][0]
    del constraints["can_move_items"]
    conditional, conditional_progress = progress(inputs)
    constraints["can_move_items"] = False
    del constraints["feasible_zones"]
    blocked, blocked_progress = progress(inputs)
    assert [
        r["action_readiness"]
        for r in [ready_progress, conditional_progress, blocked_progress]
    ] == ["ready", "needs_confirmation", "blocked"]
    results = [ready, conditional, blocked]
    options = [
        r["layout_analysis"]["surface_analysis"]["findings"][0]["action_options"][0]
        for r in results
    ]
    assert len({o["action_id"] for o in options}) == 1
    for key in ["rule_id", "source_ids", "to_zone", "traditional_reason"]:
        assert options[0][key] == options[1][key] == options[2][key]
    assert blocked_progress["pending_confirmations"] == []
    assert options[2]["pending_confirmations"] == []
    assert (
        ready_progress["rule_coverage_counts"]
        == blocked_progress["rule_coverage_counts"]
    )


def test_retention_does_not_ask_for_movement_permission():
    inputs = surface_input(zone="far_left")
    inputs["surface_constraints"] = []
    result, review = progress(inputs)
    action = result["layout_analysis"]["surface_analysis"]["findings"][0][
        "action_options"
    ][0]
    assert action["action"] == "retain_item"
    assert {p["reason"] for p in review["pending_confirmations"]} == {
        "confirm_target_zone_feasibility"
    }


def test_optional_representation_does_not_turn_into_a_required_assessment_task():
    inputs = surface_input(goal="career")
    del inputs["surface_constraints"][0]["can_add_items"]
    _, review = progress(inputs)
    assert review["assessment_complete"]
    assert review["optional_action_count"] == 1
    assert review["action_counts"] == {
        "ready": 1,
        "conditional": 1,
        "candidate": 0,
        "blocked": 0,
    }
    assert review["action_readiness"] == "mixed"
    assert review["pending_confirmations"]
    assert all(
        p["required_for"] == "optional_action" for p in review["pending_confirmations"]
    )


def test_empty_confirmed_surface_has_optional_actions_and_no_missing_existing_item():
    inputs = surface_input()
    inputs["surface_layouts"][0]["items"] = []
    inputs["surface_constraints"] = []
    _, review = progress(inputs)
    assert review["assessment_complete"]
    assert review["rule_coverage_counts"] == {
        "supported": 0,
        "confirmed_unsupported": 0,
        "unknown": 0,
    }
    assert review["optional_action_count"] == 1
    assert all(
        p["required_for"] == "optional_action" for p in review["pending_confirmations"]
    )


def test_form_mirror_remains_conditional_then_closes_when_view_is_confirmed():
    inputs = form_inputs(entrance_visible=False)
    result, review = progress(inputs)
    assert review["calculation_status"] == "complete" and review["assessment_complete"]
    assert review["action_readiness"] == "needs_confirmation"
    mirror = result["layout_analysis"]["form_analysis"]["findings"][0][
        "object_options"
    ][0]
    assert mirror["status"] == "conditional_option" and mirror["optional"]
    assert any(
        p["reason"] == "confirm_mirror_entrance_view"
        for p in mirror["pending_confirmations"]
    )
    assert not any(
        p["reason"] == "verify_avoid_entrance_direct_line"
        for p in mirror["pending_confirmations"]
    )
    inputs["form_observations"][0].update(entrance_visible=True, view_via_mirror=True)
    _, review = progress(inputs)
    assert review["action_readiness"] == "no_action_needed"
    assert review["optional_action_count"] == 0
    assert review["pending_confirmations"] == []


def test_direction_candidates_never_certify_relocation_feasibility():
    result, review = progress(facing_only())
    assert review["action_counts"]["ready"] == 0
    assert review["action_counts"]["conditional"] == 1
    direction = result["layout_analysis"]["adjustment_options"][0]
    assert (
        direction["decision_scope"]
        == "direction_relation_not_verified_relocation_feasibility"
    )
    assert direction["action_status"] == "conditional_option"
    assert (
        direction["pending_confirmations"][0]["reason"]
        == "relocation_feasibility_not_in_current_contract"
    )


def test_missing_form_facts_do_not_claim_no_action_needed():
    inputs = form_inputs()
    observation = inputs["form_observations"][0]
    for key in ["entrance_visible", "entrance_direct_line", "solid_backing"]:
        del observation[key]
    _, review = progress(inputs)
    assert review["calculation_status"] == "partial"
    assert review["action_readiness"] == "not_evaluated"
    assert all(
        p["required_for"] == "assessment" for p in review["pending_confirmations"]
    )


def test_unsupported_authored_year_closes_known_scope_without_an_action_verdict():
    inputs = {
        "methods": ["annual_stars"],
        "effective_year": 2027,
        "annual_remedy_ruleset_id": "pang_2026_annual_v1",
        "placements": [
            {"object_id": "desk", "purpose": "desk", "location_direction": "S"}
        ],
    }
    result, review = progress(inputs)
    assert result["layout_analysis"]["status"] == "partial"
    assert review["calculation_status"] == "complete"
    assert review["rule_coverage_status"] == "limited"
    assert review["assessment_complete"]
    assert review["action_readiness"] == "not_evaluated"
    assert review["pending_confirmations"] == []


@pytest.mark.parametrize(
    "state", ["ready", "conditional", "blocked", "unsupported", "photo", "unknown"]
)
def test_coverage_projection_preserves_review_and_action_states_on_all_transports(
    monkeypatch, tmp_path, capsys, state
):
    inputs = surface_input()
    if state == "conditional":
        del inputs["surface_constraints"][0]["feasible_zones"]
    elif state == "blocked":
        inputs["surface_constraints"][0]["can_move_items"] = False
    elif state == "unsupported":
        inputs["surface_layouts"][0]["items"][0]["representation"] = "other"
    elif state == "photo":
        inputs["surface_layouts"][0]["items"][0]["observation_basis"] = "image_observed"
        # Rebuilding progress for layout constraints must preserve conditional evidence.
        inputs["form_observations"] = [
            {
                "object_id": "work-surface",
                "purpose": "desk",
                "entrance_position": "left",
                "observation_basis": "image_observed",
                "evidence": "只观察到入口相对位置，其他形态未知",
            }
        ]
        inputs["layout_constraints"] = [
            {"object_id": "work-surface", "can_add_items": False, "evidence": "不新增"}
        ]
    elif state == "unknown":
        inputs["surface_layouts"][0]["items"][0]["representation"] = "unknown"
    expected = assess(**deepcopy(inputs))["coverage"]["analysis_progress"]
    assert expected["interpretation_status"] == {
        "unsupported": "scope_only",
        "photo": "conditional",
        "unknown": "insufficient_evidence",
    }.get(state, "available")
    controls = {
        "fields": ["coverage.analysis_progress", "rulesets", "rule_trace"],
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_assess", {**inputs, **controls}, raise_on_error=False
            )

    response = rest_client(monkeypatch).post(
        "/api/fengshui/assess", params=controls, json=inputs
    )
    protocol = asyncio.run(call())
    path = tmp_path / "progress.json"
    path.write_text(json.dumps(inputs, ensure_ascii=False))
    assert (
        run(
            [
                "fengshui_assess",
                "--request-file",
                str(path),
                "--fields",
                *controls["fields"],
                "--strict-fields",
                "--no-include-snapshot-text",
                "--response-char-limit",
                "0",
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not protocol.is_error
    assert (
        without_transport(response.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    for result in [response.json(), protocol.structured_content, cli]:
        Draft202012Validator(FengshuiOutput.model_json_schema()).validate(result)
        assert result["coverage"]["analysis_progress"] == expected
        assert "layout_analysis" not in result
        assert result["rulesets"] and result["rule_trace"]


def test_object_purpose_conflict_is_rejected_on_rest_mcp_cli(
    monkeypatch, tmp_path, capsys
):
    inputs = surface_input()
    inputs["form_observations"] = form_inputs(purpose="stove")["form_observations"]
    inputs["form_observations"][0]["object_id"] = "work-surface"

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_assess", inputs, raise_on_error=False
            )

    response = rest_client(monkeypatch).post("/api/fengshui/assess", json=inputs)
    protocol = asyncio.run(call())
    path = tmp_path / "conflict.json"
    path.write_text(json.dumps(inputs, ensure_ascii=False))
    code = run(["fengshui_assess", "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 422
    assert protocol.is_error
    assert code != 0
    for result in [response.json(), protocol.structured_content, cli]:
        assert result["error_code"] == "validation_error"
        assert {"path": "request", "code": "value_error"} in result["issues"]
