"""Independent source facts, permutations and infeasible actions, not a user fixture."""

import asyncio
import json
from copy import deepcopy
from typing import get_args

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaValidationError
from pydantic import ValidationError

from fatebridge.application.examples import call_guidance
from fatebridge.cli import run
from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.core.fengshui.surface_inputs import SurfaceZone
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import assess
from fatebridge.services.tool_catalog import CATALOG
from tests.test_fengshui_surfaces import rest_client, without_transport


def surface_input(goal="abundance", zone="near_right", basis="user_confirmed"):
    return {
        "methods": [],
        "surface_layouts": [
            {
                "object_id": "work-surface",
                "ruleset_id": "desktop_bagua_btb_v1",
                "shape": "rectangular",
                "anchor": "seated_near_edge",
                "goal": goal,
                "observation_basis": basis,
                "evidence": "矩形桌面与坐者使用沿已确认，目标由使用者给出",
                "items": [
                    {
                        "object_id": "specimen",
                        "label": "室内盆栽",
                        "representation": "living_plant",
                        "zone": zone,
                        "zone_observation_basis": basis,
                        "observation_basis": basis,
                        "evidence": "实际活植物",
                    }
                ],
            }
        ],
        "surface_constraints": [
            {
                "object_id": "work-surface",
                "can_move_items": True,
                "can_add_items": False,
                "feasible_zones": ["far_left"],
                "evidence": "远左放得下且保留入口视野，允许移动已有物件",
            }
        ],
    }


def surface_result(inputs):
    return assess(**inputs)["layout_analysis"]["surface_analysis"]


@pytest.mark.parametrize(
    "zone",
    [
        "near_left",
        "near_center",
        "near_right",
        "middle_left",
        "middle_center",
        "middle_right",
        "far_left",
        "far_center",
        "far_right",
    ],
)
def test_published_seated_far_left_rule_from_every_start_zone(zone):
    result = surface_result(surface_input(zone=zone))
    option = result["findings"][0]["action_options"][0]
    # Independent expectation from Cho's explicitly seated desk instruction.
    assert option["to_zone"] == "far_left"
    assert option["action"] == ("retain_item" if zone == "far_left" else "place_item")
    assert option["status"] == "ready"
    assert option["source_ids"] == ["D1", "D2"]
    assert not option["changes_compass_result"]


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"can_move_items": False}, "moving_items_forbidden"),
        ({"locked_item_ids": ["specimen"]}, "item_locked"),
        (
            {"feasible_zones": [], "unavailable_zones": ["far_left"]},
            "target_zone_unavailable",
        ),
    ],
)
def test_source_candidate_cannot_override_constraint(change, reason):
    inputs = surface_input()
    inputs["surface_constraints"][0].update(change)
    option = surface_result(inputs)["findings"][0]["action_options"][0]
    assert option["status"] == "blocked" and reason in option["constraint_reasons"]


def test_locked_item_already_in_supported_zone_does_not_require_movement():
    inputs = surface_input(zone="far_left")
    inputs["surface_constraints"][0].update(
        can_move_items=False, locked_item_ids=["specimen"]
    )
    option = surface_result(inputs)["findings"][0]["action_options"][0]
    assert option["action"] == "retain_item" and option["status"] == "ready"


@pytest.mark.parametrize("part", ["boundary", "item"])
def test_photo_hypothesis_never_becomes_ready(part):
    inputs = surface_input()
    if part == "boundary":
        inputs["surface_layouts"][0]["observation_basis"] = "image_observed"
    else:
        inputs["surface_layouts"][0]["items"][0]["observation_basis"] = "image_observed"
    result = surface_result(inputs)
    assert result["findings"][0]["action_options"][0]["status"] == "candidate_only"
    assert result["status"] == "partial"


def test_unconfirmed_feasibility_or_permission_stays_conditional():
    for field in ("feasible_zones", "can_move_items"):
        inputs = surface_input()
        inputs["surface_constraints"][0].pop(field)
        option = surface_result(inputs)["findings"][0]["action_options"][0]
        assert option["status"] == "conditional_option"


def test_labels_do_not_assign_elements_or_matching_side():
    for name in ["电话", "水杯", "树脂陶土造型玩偶", "绿植", "999发财神器"]:
        inputs = surface_input()
        inputs["surface_layouts"][0]["items"][0].update(
            label=name, representation="unknown"
        )
        result = surface_result(inputs)
        item = result["findings"][0]["item_findings"][0]
        assert item["status"] == "no_independent_placement_rule"
        assert item["rule_ids"] == []
        assert result["uncovered_item_ids"] == ["specimen"]
        assert result["status"] == "partial"


def test_other_goal_has_distinct_source_scope_without_forced_addition():
    abundance = surface_result(surface_input())
    career = surface_result(surface_input(goal="career"))
    assert len(abundance["findings"][0]["action_options"]) == 1
    symbols = [
        x
        for x in career["findings"][0]["action_options"]
        if x["to_zone"] == "near_center"
    ]
    assert len(symbols) == 1 and symbols[0]["status"] == "blocked"
    assert symbols[0]["constraint_reasons"] == ["additions_forbidden"]
    assert "dark_accessory" in symbols[0]["representations"]


def test_existing_symbol_uses_authored_career_zone_without_purchase():
    inputs = surface_input(goal="career")
    inputs["surface_layouts"][0]["items"][0].update(
        representation="water_image", label="海景图", zone="near_center"
    )
    inputs["surface_constraints"][0]["feasible_zones"] = ["near_center"]
    symbols = [
        x
        for x in surface_result(inputs)["findings"][0]["action_options"]
        if x["item_id"]
    ]
    assert len(symbols) == 1 and symbols[0]["action"] == "retain_item"
    assert symbols[0]["source_ids"] == ["D3"]


def test_ids_are_references_not_rule_selectors_and_mutation_cannot_poison_sources():
    inputs = surface_input()
    original = surface_result(inputs)
    changed = deepcopy(inputs)
    changed["surface_layouts"][0]["object_id"] = "unseen-☀"
    changed["surface_layouts"][0]["items"][0]["object_id"] = "new-未见"
    changed["surface_constraints"][0]["object_id"] = "unseen-☀"
    option = surface_result(changed)["findings"][0]["action_options"][0]
    baseline = original["findings"][0]["action_options"][0]
    for key in ("to_zone", "rule_id", "source_ids", "status", "traditional_reason"):
        assert option[key] == baseline[key]
    option["source_ids"].append("fake")
    assert (
        "fake"
        not in surface_result(changed)["findings"][0]["action_options"][0]["source_ids"]
    )


def test_personal_birth_and_facing_do_not_rotate_authored_surface_map():
    inputs = surface_input()
    original = surface_result(inputs)
    for year, direction in [(1987, "NE"), (1996, "S"), (2010, "NW")]:
        variant = {
            **inputs,
            "methods": ["bazhai"],
            "occupants": [
                {
                    "subject_id": "resident",
                    "effective_birth_year": year,
                    "gender_convention": "female",
                }
            ],
            "placements": [
                {
                    "object_id": "work-surface",
                    "purpose": "desk",
                    "facing_direction": direction,
                    "facing_role": "desk_facing",
                }
            ],
        }
        assert surface_result(variant) == original


@pytest.mark.parametrize(
    "change",
    [
        {"anchor": "compass_north"},
        {"shape": "round"},
        {"goal": "invented"},
        {
            "items": [
                {
                    "object_id": "x",
                    "label": "x",
                    "representation": "phone_fire",
                    "observation_basis": "user_confirmed",
                    "evidence": "x",
                }
            ]
        },
    ],
)
def test_unknown_methods_frames_and_semantics_are_rejected(change):
    inputs = surface_input()
    inputs["surface_layouts"][0].update(change)
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(inputs)


def test_constraints_cannot_invent_physical_facts():
    inputs = surface_input()
    inputs["surface_constraints"][0]["solid_backing"] = True
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(inputs)
    inputs = surface_input()
    inputs["surface_constraints"][0]["locked_item_ids"] = ["other-surface-item"]
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(inputs)


def test_representation_is_required_not_silently_downgraded_to_unknown():
    inputs = surface_input()
    del inputs["surface_layouts"][0]["items"][0]["representation"]
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(inputs)
    with pytest.raises(SchemaValidationError) as error:
        Draft202012Validator(AssessRequest.model_json_schema()).validate(inputs)
    assert "representation" in str(error.value)


def test_position_and_representation_evidence_are_independent():
    inputs = surface_input(zone="far_left")
    inputs["surface_layouts"][0]["items"][0][
        "zone_observation_basis"
    ] = "image_observed"
    result = surface_result(inputs)
    option = result["findings"][0]["action_options"][0]
    assert option["action"] == "place_item"
    assert option["from_zone_basis"] == "image_observed"
    del inputs["surface_layouts"][0]["items"][0]["zone_observation_basis"]
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(inputs)
    with pytest.raises(SchemaValidationError):
        Draft202012Validator(AssessRequest.model_json_schema()).validate(inputs)


def test_shared_frame_guide_covers_exact_schema_regions_and_is_not_mutable():
    spec = next(s for s in CATALOG if s.key == "fengshui_assess")
    guide = call_guidance(spec)
    assert set(guide["zone_legend"]) == set(get_args(SurfaceZone))
    original = guide["zone_legend"]["far_left"]
    guide["zone_legend"]["far_left"] = "tampered"
    assert call_guidance(spec)["zone_legend"]["far_left"] == original


@pytest.mark.parametrize(
    "pair",
    [
        ("birth_date", "birth_at"),
        ("birth_date", "effective_birth_year"),
        ("birth_at", "effective_birth_year"),
    ],
)
def test_birth_choice_exclusivity_is_machine_visible_and_matches_runtime(pair):
    values = {
        "birth_date": "1993-08-11",
        "birth_at": "1993-08-11T15:20:00+08:00",
        "effective_birth_year": 1993,
    }
    inputs = {
        "occupants": [{"subject_id": "unseen", **{key: values[key] for key in pair}}]
    }
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(inputs)
    with pytest.raises(SchemaValidationError):
        Draft202012Validator(AssessRequest.model_json_schema()).validate(inputs)
    inputs["occupants"][0].pop(pair[1])
    AssessRequest.model_validate(inputs)
    Draft202012Validator(AssessRequest.model_json_schema()).validate(inputs)


def test_passage_is_not_the_actual_entrance_and_side_window_is_separate():
    result = assess(
        methods=[],
        form_observations=[
            {
                "object_id": "a",
                "purpose": "desk",
                "passage_position": "left",
                "window_position": "right",
                "observation_basis": "user_confirmed",
                "evidence": "仅确认经过通道与侧窗，入口未知",
            }
        ],
    )
    finding = result["layout_analysis"]["form_analysis"]["findings"][0]
    checks = {c["criterion"]: c for c in finding["checks"]}
    assert checks["entrance_visible"]["finding"] == "undetermined"
    assert checks["entrance_direct_line"]["finding"] == "undetermined"
    assert checks["window_to_side"]["finding"] == "matches_rule"
    assert finding["entrance_position"] is None
    assert result["status"] == "partial"


@pytest.mark.parametrize("purpose", ["bed", "stove"])
def test_desk_window_source_does_not_expand_to_other_furniture(purpose):
    result = assess(
        methods=[],
        form_observations=[
            {
                "object_id": "different",
                "purpose": purpose,
                "window_position": "right",
                "observation_basis": "user_confirmed",
                "evidence": "只提供侧窗，不把书桌来源外推到其他家具",
            }
        ],
    )
    checks = result["layout_analysis"]["form_analysis"]["findings"][0]["checks"]
    assert all(c["criterion"] != "window_to_side" for c in checks)


@pytest.mark.parametrize(
    "criterion",
    ["passage_direct_line", "exposed_beam_over_user", "sharp_corner_points_at_user"],
)
@pytest.mark.parametrize("observed", [True, False])
def test_additional_form_sources_use_explicit_observations_only(criterion, observed):
    inputs = {
        "methods": [],
        "form_observations": [
            {
                "object_id": "unseen",
                "purpose": "desk",
                criterion: observed,
                "observation_basis": "user_confirmed",
                "evidence": "只确认这一项形态关系",
            }
        ],
    }
    finding = assess(**inputs)["layout_analysis"]["form_analysis"]["findings"][0]
    check = next(c for c in finding["checks"] if c["criterion"] == criterion)
    assert check["finding"] == ("opposes_rule" if observed else "matches_rule")
    assert check["source_ids"] == ["F4"]
    del inputs["form_observations"][0][criterion]
    inputs["form_observations"][0]["passage_position"] = "left"
    checks = assess(**inputs)["layout_analysis"]["form_analysis"]["findings"][0][
        "checks"
    ]
    assert all(c["criterion"] != criterion for c in checks)


def test_authored_surfaces_match_rest_mcp_cli_and_strict_projection(
    monkeypatch, tmp_path, capsys
):
    inputs = surface_input()
    fields = ["layout_analysis.surface_analysis", "rulesets"]
    controls = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    response = rest_client(monkeypatch).post(
        "/api/fengshui/assess",
        params={
            "fields": fields,
            "strict_fields": "true",
            "include_snapshot_text": "false",
        },
        json=inputs,
    )

    async def call():
        async with Client(create_mcp_app()) as client:
            schemas = {t.name: t for t in await client.list_tools()}
            Draft202012Validator(
                schemas["fengshui_assess"].model_dump(by_alias=True)["inputSchema"]
            ).validate({**inputs, **controls})
            return await client.call_tool("fengshui_assess", {**inputs, **controls})

    protocol = asyncio.run(call())
    path = tmp_path / "surface.json"
    path.write_text(json.dumps(inputs))
    code = run(
        [
            "fengshui_assess",
            "--request-file",
            str(path),
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        without_transport(response.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    Draft202012Validator(FengshuiOutput.model_json_schema()).validate(cli)
