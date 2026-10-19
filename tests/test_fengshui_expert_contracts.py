"""Expert-context facts survive public transports without chart substitution."""

import asyncio
import json
from copy import deepcopy

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator

from fatebridge.application.examples import suggested_fields
from fatebridge.cli import run
from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import assess
from fatebridge.services.tool_catalog import CATALOG
from tests.test_fengshui_planning import proposal_request
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport


def context_request():
    """Synthetic family and floor facts, with no birth data or guessed compass."""
    return {
        "scene": "shared_rental",
        "environmental_context": {
            "household_composition_confirmed": True,
            "household_members": [
                {
                    "subject_id": "husband",
                    "gender_role": "male",
                    "generation": 0,
                    "family_roles": ["parent", "middle_child"],
                    "evidence": "本家庭已确认父亲及排行老二身份",
                },
                {
                    "subject_id": "wife",
                    "gender_role": "female",
                    "generation": 0,
                    "family_roles": ["parent", "eldest_child"],
                    "spouse_subject_id": "husband",
                    "follow_spouse_rank": True,
                    "evidence": "明确本家庭随丈夫排行，不按娘家长女身份",
                },
            ],
            "objects": [
                {
                    "object_id": "kitchen",
                    "label": "厨房",
                    "kind": "room",
                    "evidence": "已确认厨房",
                },
                {
                    "object_id": "garden",
                    "label": "院落绿化",
                    "kind": "garden_feature",
                    "evidence": "院落绿化",
                },
            ],
            "observations": [
                {
                    "observation_id": "modern",
                    "object_id": "kitchen",
                    "category": "modern_design",
                    "feature": "open_kitchen",
                    "evidence": "已确认开放厨房，仅轻提醒",
                },
                {
                    "observation_id": "material",
                    "object_id": "garden",
                    "category": "material",
                    "feature": "stone",
                    "evidence": "已确认石材，不猜砂水",
                },
            ],
        },
    }


@pytest.mark.parametrize("case", ["context", "orientation_unknown", "floors"])
def test_context_matches_actual_rest_mcp_cli(monkeypatch, tmp_path, capsys, case):
    inputs = context_request()
    context = inputs["environmental_context"]
    if case == "orientation_unknown":
        context["orientation"] = {"evidence": "方位与户型偏移尚未确认"}
    elif case == "floors":
        context["orientation"] = {
            "direction_confirmed": True,
            "north_reference": "magnetic",
            "floorplan_alignment_confirmed": True,
            "center_confirmed": True,
            "evidence": "逐层确认共用方向、图纸偏移及中心",
        }
        context["floors"] = [
            {
                "floor_id": "first",
                "level": 1,
                "uses_shared_orientation": True,
                "object_ids": ["kitchen"],
                "usage_confirmed": True,
                "usage_evidence": "已完整确认一层厨房的住用范围，夫妻均不在其中",
                "evidence": "一层厨房",
            },
            {
                "floor_id": "yard",
                "level": 1,
                "space_kind": "courtyard",
                "uses_shared_orientation": True,
                "object_ids": ["garden"],
                "usage_confirmed": True,
                "usage_evidence": "已独立完整确认院落使用范围，夫妻均不使用院落",
                "evidence": "院落属于一层",
            },
            {
                "floor_id": "second",
                "level": 2,
                "uses_shared_orientation": True,
                "subject_ids": ["husband", "wife"],
                "suitability": "confirmed_suitable",
                "suitability_evidence": "专家已明确确认另一层适宜",
                "evidence": "仅在二层居住",
            },
        ]
        context["floor_influences"] = [
            {
                "influence_id": "local",
                "source_floor_id": "first",
                "extent": "floor_local_confirmed",
                "evidence": "影响已确认局限一层",
            },
            {
                "influence_id": "shared",
                "source_floor_id": "yard",
                "extent": "shared_confirmed",
                "shared_floor_ids": ["second"],
                "evidence": "另有独立共同影响，不能取消",
            },
        ]
        for floor in context["floors"]:
            floor.update(center_confirmed=True, floorplan_alignment_confirmed=True)
    response = rest_client(monkeypatch).post("/api/fengshui/assess", json=inputs)
    protocol = asyncio.run(mcp_call("assess", inputs))
    path = tmp_path / "专家口径.json"
    path.write_text(json.dumps(inputs, ensure_ascii=False))
    code = run(["fengshui_assess", "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert code == 0 and not protocol.is_error
    assert (
        without_transport(response.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    for body in (response.json(), protocol.structured_content, cli):
        Draft202012Validator(FengshuiOutput.model_json_schema()).validate(body)
        assert body["layers"] == {}
        review = body["layout_analysis"]["environmental_context"]
        people = {p["subject_id"]: p for p in review["household_correspondences"]}
        assert {a["primary_palace"] for a in people["husband"]["associations"]} == {
            "乾",
            "坎",
        }
        assert {a["primary_palace"] for a in people["wife"]["associations"]} == {
            "坤",
            "离",
        }
        assert body["layout_analysis"]["analysis_progress"]["rule_coverage_status"] == (
            "limited" if case == "floors" else "needs_confirmation"
        )
        assert all(a["effects_inferred"] is False for a in people.values())
        assert "人物象征对应不代替环境方位" in body["snapshot_text"]
        assert {"expert_environment_2026_10_v1", "expert_fengshui_methods_v1"} <= {
            r["ruleset_id"] for r in body["rulesets"]
        }
        if case == "floors":
            influences = review["floor_review"]["influences"]
            assert {s["status"] for s in influences[0]["subject_scope"]} == {
                "local_exposure_not_assigned_to_other_floor"
            }
            assert {s["status"] for s in influences[1]["subject_scope"]} == {
                "shared_review_required"
            }


@pytest.mark.parametrize(
    "physical", ["placement", "facing", "feature", "external_forms"]
)
def test_explicit_unknown_orientation_rejects_physical_claims_on_all_transports(
    monkeypatch, tmp_path, capsys, physical
):
    inputs = {
        "methods": [],
        "environmental_context": {"orientation": {"evidence": "方位尚未确认"}},
    }
    if physical in {"placement", "facing"}:
        placement = {"object_id": "desk", "purpose": "desk"}
        placement.update(
            {"location_direction": "N"}
            if physical == "placement"
            else {"facing_direction": "N", "facing_role": "desk_facing"}
        )
        inputs["placements"] = [placement]
    elif physical == "feature":
        inputs["features"] = [
            {
                "object_id": "wall",
                "direction": "N",
                "classification": "sand",
                "classification_basis": "user_confirmed",
                "evidence": "不能与未确认落宫同时传",
            }
        ]
    else:
        inputs.update(
            methods=["xuankong_natal"],
            xuankong={
                "interpretation": {
                    "external_forms": [
                        {
                            "direction": "N",
                            "mountain_present": True,
                            "observation_basis": "user_confirmed",
                            "evidence": "未确认落宫",
                        }
                    ]
                }
            },
        )
    response = rest_client(monkeypatch).post("/api/fengshui/assess", json=inputs)
    protocol = asyncio.run(mcp_call("assess", inputs))
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(inputs))
    code = run(["fengshui_assess", "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 422 and protocol.is_error and code == 1
    assert (
        response.json()["issues"]
        == protocol.structured_content["issues"]
        == cli["issues"]
    )


@pytest.mark.parametrize("explicit_unknown", [False, True])
def test_no_compass_observations_close_as_limited_review_without_invented_taboo(
    explicit_unknown,
):
    inputs = context_request()
    context = inputs["environmental_context"]
    context.pop("household_members")
    if explicit_unknown:
        context["orientation"] = {"evidence": "明确未知方位，但本次只审非方向事实"}
    result = assess(**inputs)
    review = result["layout_analysis"]["environmental_context"]
    assert result["status"] == "complete"
    assert review["missing_inputs"] == []
    assert result["coverage"]["analysis_progress"]["assessment_complete"] is True
    assert review["orientation_review"]["physical_sector_binding_allowed"] is False
    assert {f["finding"] for f in review["environment_findings"]} == {
        "low_priority_reminder",
        "confirmed_fact_without_specific_taboo_rule",
    }
    assert all(not f["action_required"] for f in review["environment_findings"])


def test_explicit_unknown_orientation_does_not_block_independent_indoor_form_review():
    from tests.test_fengshui_method_boundaries import form

    result = assess(
        scene="workstation",
        form_observations=[form()],
        environmental_context={
            "orientation": {"evidence": "方位未知，本次仅审独立室内形态"}
        },
    )
    assert result["coverage"]["analysis_progress"]["assessment_complete"] is True
    assert (
        result["layout_analysis"]["environmental_context"]["orientation_review"][
            "physical_sector_binding_allowed"
        ]
        is False
    )
    assert result["layout_analysis"]["placement_findings"] == []


def test_first_view_can_request_context_and_policy_with_resolvable_sources(monkeypatch):
    inputs = context_request()
    spec = next(s for s in CATALOG if s.key == "fengshui_assess")
    fields = suggested_fields(spec) + [
        "method_policy",
        "layout_analysis.environmental_context",
    ]
    response = rest_client(monkeypatch).post(
        "/api/fengshui/assess",
        json=inputs,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["method_policy"] and body["layout_analysis"]["environmental_context"]
    sources = {s["source_id"] for r in body["rulesets"] for s in r["sources"]}
    assert all(set(trace["source_ids"]) <= sources for trace in body["rule_trace"])
    assert "snapshot_text" not in body


def test_published_mcp_schema_exposes_context_without_birth_requirements():
    async def inspect():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            tool = next(
                t for t in await client.list_tools() if t.name == "fengshui_assess"
            )
            Draft202012Validator(tool.input_schema).validate(context_request())
            return tool.input_schema

    schema = asyncio.run(inspect())
    assert "environmental_context" in schema["properties"]
    assert "shared_rental" in json.dumps(schema["properties"]["scene"])


@pytest.mark.parametrize("with_context", [False, True])
def test_proposal_does_not_reuse_old_environment_context(with_context):
    inputs = proposal_request()
    object_id = inputs["placements"][0]["object_id"]
    context = {
        "observations": [
            {
                "observation_id": "wood",
                "object_id": object_id,
                "category": "material",
                "feature": "wood",
                "evidence": "现状材质记录，不转成新位置的已验收环境",
            }
        ]
    }
    inputs["environmental_context"] = context
    if with_context:
        inputs["layout_alternatives"][0]["environmental_context"] = deepcopy(context)
    result = assess(**inputs)
    proposal = result["layout_analysis"]["alternatives_analysis"]["findings"][0]
    path = f"layout_alternatives.{proposal['candidate_id']}.environmental_context"
    assert (path not in proposal["missing_inputs"]) is with_context
    if not with_context:
        assert proposal["status"] != "ready"


def test_household_subject_can_reference_placement_without_birth_chart():
    inputs = context_request()
    inputs["environmental_context"]["orientation"] = {
        "direction_confirmed": True,
        "north_reference": "magnetic",
        "floorplan_alignment_confirmed": True,
        "center_confirmed": True,
        "evidence": "实测确认",
    }
    inputs["placements"] = [
        {
            "object_id": "desk",
            "purpose": "desk",
            "location_direction": "N",
            "subject_id": "wife",
        }
    ]
    assert AssessRequest.model_validate(inputs).occupants == []
    result = assess(**inputs)
    assert result["layers"] == {}
    assert "bazi" not in result


@pytest.mark.parametrize(
    "missing",
    [
        "uses_shared_orientation",
        "center_confirmed",
        "floorplan_alignment_confirmed",
        None,
    ],
)
def test_each_floor_requires_its_own_confirmed_coordinate_frame(missing):
    inputs = context_request()
    context = inputs["environmental_context"]
    context["orientation"] = {
        "direction_confirmed": True,
        "north_reference": "magnetic",
        "floorplan_alignment_confirmed": True,
        "center_confirmed": True,
        "evidence": "全宅方位已确认",
    }
    floor = {
        "floor_id": "second",
        "level": 2,
        "object_ids": ["desk"],
        "uses_shared_orientation": True,
        "center_confirmed": True,
        "floorplan_alignment_confirmed": True,
        "evidence": "该层独立核对",
    }
    context["floors"] = [floor]
    inputs.update(
        methods=["annual_stars"],
        effective_year=2026,
        placements=[
            {"object_id": "desk", "purpose": "desk", "location_direction": "N"}
        ],
    )
    if missing:
        floor.pop(missing)
        with pytest.raises(ValueError, match="楼层"):
            AssessRequest.model_validate(inputs)
    else:
        result = assess(**inputs)
        finding = result["layout_analysis"]["placement_findings"][0]
        assert finding["floor_id"] == "second" and finding["floor_level"] == 2
        assert (
            finding["location_reference"]
            == "independently_confirmed_floor_center_shared_orientation"
        )


def test_nonempty_candidate_context_cannot_erase_prior_environment_criteria():
    inputs = proposal_request()
    object_id = inputs["placements"][0]["object_id"]
    inputs["environmental_context"] = {
        "observations": [
            {
                "observation_id": "old",
                "object_id": object_id,
                "category": "material",
                "feature": "wood",
                "evidence": "现状明确材质",
            }
        ]
    }
    inputs["layout_alternatives"][0]["environmental_context"] = {
        "orientation": {
            "direction_confirmed": True,
            "north_reference": "magnetic",
            "floorplan_alignment_confirmed": True,
            "center_confirmed": True,
            "evidence": "坐标已核对，但未提供新环境观察",
        }
    }
    result = assess(**inputs)
    proposal = result["layout_analysis"]["alternatives_analysis"]["findings"][0]
    assert proposal["status"] != "ready"
    assert any("observations.material.wood" in p for p in proposal["missing_inputs"])


@pytest.mark.parametrize("present", [False, True])
def test_other_shape_never_proves_previously_reviewed_shape_is_absent(present):
    inputs = proposal_request()
    object_id = inputs["placements"][0]["object_id"]
    old = {
        "observation_id": "shape",
        "object_id": object_id,
        "category": "shape",
        "feature": "pointed",
        "evidence": "现状尖形已经确认",
    }
    inputs["environmental_context"] = {"observations": [old]}
    inputs["layout_alternatives"][0]["environmental_context"] = {
        "observations": [
            {
                **old,
                "feature": "round",
                "present": present,
                "evidence": "只确认圆形状态，未重核尖形",
            }
        ]
    }
    result = assess(**inputs)
    proposal = result["layout_analysis"]["alternatives_analysis"]["findings"][0]
    assert proposal["status"] != "ready"
    assert any("observations.shape.pointed" in p for p in proposal["missing_inputs"])
