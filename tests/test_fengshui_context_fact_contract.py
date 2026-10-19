"""The public MCP schema must publish the runtime's nonempty-context fact gate."""

import asyncio
from copy import deepcopy

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.core.fengshui.context_inputs import EnvironmentalContext
from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.mcp_server import create_mcp_app


def object_definition(object_id="item", role=None):
    return {
        "object_id": object_id,
        "label": object_id,
        "kind": "furniture" if role in {"bed", "mirror"} else "material_object",
        "role": role,
        "evidence": "已确认对象身份；单独身份不是环境审查事实",
    }


def floor_definition():
    return {
        "floor_id": "first",
        "level": 1,
        "evidence": "只确认一层身份；中心与图纸对齐尚未确认",
    }


def influence_definition():
    return {
        "influence_id": "local",
        "source_floor_id": "first",
        "extent": "floor_local_confirmed",
        "evidence": "已确认该局部范围只在一层",
    }


def context_cases():
    empty_arrays = {
        name: []
        for name in (
            "household_members",
            "floors",
            "observations",
            "interior_relations",
            "material_facts",
            "objects",
            "floor_influences",
        )
    }
    member = {
        "subject_id": "person",
        "gender_role": "male",
        "generation": 0,
        "family_roles": ["parent"],
        "evidence": "明确提供父亲身份，不从查询范围编造人物",
    }
    observation = {
        "observation_id": "form",
        "object_id": "item",
        "category": "shape",
        "feature": "round",
        "evidence": "已确认圆形器物；未问摆位或资格",
    }
    relation = {
        "relation_id": "mirror-bed",
        "source_object_id": "mirror",
        "target_object_id": "bed",
        "kind": "mirror_faces_bed",
        "present": False,
        "observation_basis": "user_confirmed",
        "evidence": "已确认镜面不照床，不从对象名称推定",
    }
    material = {
        "fact_id": "material",
        "object_id": "item",
        "material": "glass",
        "observation_basis": "user_confirmed",
        "evidence": "已确认玻璃材质；未提出元素代表物问题",
    }
    return [
        ("empty", {}, False),
        ("scope-only", {"household_scope": "symbolic_reference"}, False),
        ("ruleset-only", {"ruleset_id": "expert_environment_2026_10_v1"}, False),
        ("composition-only", {"household_composition_confirmed": True}, False),
        ("empty-arrays", empty_arrays, False),
        ("null-orientation", {**empty_arrays, "orientation": None}, False),
        ("null-list", {"household_members": None}, False),
        ("wrong-orientation-type", {"orientation": []}, False),
        ("objects-only", {"objects": [object_definition()]}, False),
        ("influences-only", {"floor_influences": [influence_definition()]}, False),
        (
            "identities-and-scope-only",
            {"objects": [object_definition()], "household_scope": "symbolic_reference"},
            False,
        ),
        (
            "orientation-uncertainty",
            {"orientation": {"evidence": "方位尚未核实"}},
            True,
        ),
        (
            "household-symbols",
            {"household_scope": "symbolic_reference", "household_members": [member]},
            True,
        ),
        (
            "household-with-null-orientation",
            {
                "orientation": None,
                "household_scope": "symbolic_reference",
                "household_members": [member],
            },
            True,
        ),
        (
            "real-orientation-does-not-relax-null-array",
            {
                "orientation": {"evidence": "方位尚未核实"},
                "household_members": None,
            },
            False,
        ),
        ("floor-fact", {"floors": [floor_definition()]}, True),
        (
            "floor-with-influence",
            {
                "floors": [floor_definition()],
                "floor_influences": [influence_definition()],
            },
            True,
        ),
        (
            "observation-with-identity",
            {"objects": [object_definition()], "observations": [observation]},
            True,
        ),
        (
            "relation-with-identities",
            {
                "objects": [
                    object_definition("mirror", "mirror"),
                    object_definition("bed", "bed"),
                ],
                "interior_relations": [relation],
            },
            True,
        ),
        (
            "material-with-identity",
            {"objects": [object_definition()], "material_facts": [material]},
            True,
        ),
    ]


@pytest.mark.parametrize(
    "name,context,accepted",
    context_cases(),
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_context_canonical_schema_matches_its_runtime_fact_gate(
    name, context, accepted
):
    validator = Draft202012Validator(EnvironmentalContext.model_json_schema())
    assert validator.is_valid(context) is accepted, name
    try:
        EnvironmentalContext.model_validate(context)
        runtime_accepted = True
    except ValidationError:
        runtime_accepted = False
    assert runtime_accepted is accepted, name


def test_actual_mcp_schema_and_runtime_agree_for_empty_and_real_context_facts():
    async def check():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            tool = next(
                t for t in await client.list_tools() if t.name == "fengshui_assess"
            )
            Draft202012Validator.check_schema(
                tool.model_dump(by_alias=True)["inputSchema"]
            )
            validator = Draft202012Validator(
                tool.model_dump(by_alias=True)["inputSchema"]
            )
            for name, context, accepted in context_cases():
                inputs = {
                    "methods": [],
                    "scene": "home",
                    "environmental_context": deepcopy(context),
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                }
                assert validator.is_valid(inputs) is accepted, name
                result = await client.call_tool(
                    "fengshui_assess", inputs, raise_on_error=False
                )
                assert result.is_error is (not accepted), name

    asyncio.run(check())


def test_nested_candidate_uses_the_same_schema_fact_gate():
    async def check():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            tool = next(
                t for t in await client.list_tools() if t.name == "fengshui_assess"
            )
            validator = Draft202012Validator(
                tool.model_dump(by_alias=True)["inputSchema"]
            )
            inputs = {
                "methods": [],
                "scene": "home",
                "placements": [
                    {
                        "object_id": "desk",
                        "purpose": "desk",
                        "facing_direction": "N",
                        "facing_role": "desk_facing",
                    }
                ],
                "layout_alternatives": [
                    {
                        "candidate_id": "rotate",
                        "object_id": "desk",
                        "changes": ["facing"],
                        "placement": {
                            "object_id": "desk",
                            "purpose": "desk",
                            "facing_direction": "E",
                            "facing_role": "desk_facing",
                        },
                        "environmental_context": {
                            "household_scope": "symbolic_reference"
                        },
                        "evidence": "独立候选但未提供任何环境事实",
                    }
                ],
                "include_snapshot_text": False,
                "response_char_limit": 0,
            }
            assert not validator.is_valid(inputs)
            with pytest.raises(ValidationError):
                AssessRequest.model_validate(inputs)
            result = await client.call_tool(
                "fengshui_assess", inputs, raise_on_error=False
            )
            assert result.is_error

    asyncio.run(check())


def test_method_reference_and_annual_query_need_no_placeholder_environment():
    async def check():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            tool = next(
                t for t in await client.list_tools() if t.name == "fengshui_assess"
            )
            inputs = {
                "scene": "home",
                "analyze_layout": False,
                "methods": ["annual_stars"],
                "effective_year": 2026,
                "fields": [
                    "status",
                    "layers.annual_stars.palaces.N",
                    "method_details.palaces.N",
                    "method_details.flying_star_references.6",
                    "method_details.mapping_boundaries",
                    "rulesets",
                    "rule_trace",
                ],
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 0,
            }
            assert "environmental_context" not in inputs
            Draft202012Validator(
                tool.model_dump(by_alias=True)["inputSchema"]
            ).validate(inputs)
            result = await client.call_tool(
                "fengshui_assess", inputs, raise_on_error=False
            )
            assert not result.is_error
            payload = result.structured_content
            assert payload["status"] == "complete"
            assert (
                payload["layers"]["annual_stars"]["palaces"]["N"]["annual_star_number"]
                == 6
            )
            assert (
                payload["method_details"]["palaces"]["N"]["fixed_palace_element"]
                == "水"
            )
            assert (
                payload["method_details"]["flying_star_references"]["6"]["element"]
                == "金"
            )
            assert payload["rulesets"] and payload["rule_trace"]

    asyncio.run(check())
