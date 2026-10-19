"""Real transport parity and independent-candidate checks for sourced interiors."""

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
from tests.test_fengshui_material_facts import material_request
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport


def relation_request(present=True, basis="user_confirmed"):
    return dict(
        scene="shared_rental",
        methods=[],
        environmental_context=dict(
            orientation=dict(
                direction_confirmed=False, evidence="未测方位，只核明确物理关系"
            ),
            objects=[
                dict(
                    object_id="mirror",
                    kind="material_object",
                    role="mirror",
                    label="镜",
                    evidence="明确确认镜面",
                ),
                dict(
                    object_id="bed",
                    kind="furniture",
                    purpose="bed",
                    label="床",
                    evidence="明确确认用途",
                ),
                dict(
                    object_id="corner",
                    kind="material_object",
                    role="pillar_corner",
                    label="柱角",
                    evidence="明确确认实体尖角源",
                ),
            ],
            interior_relations=[
                dict(
                    relation_id="reflection",
                    source_object_id="mirror",
                    target_object_id="bed",
                    kind="mirror_faces_bed",
                    present=present,
                    observation_basis=basis,
                    evidence="镜与床关系独立观察，不从镜子名称推断",
                )
            ],
        ),
    )


def relation_candidate(moving="mirror"):
    request = relation_request()
    fresh = deepcopy(request["environmental_context"]["interior_relations"][0])
    fresh.update(present=False, evidence="候选位置独立核对：不再正对床")
    operation = "facing" if moving == "mirror" else "location"
    request["layout_constraints"] = [
        dict(
            object_id=moving,
            can_relocate=True,
            can_rotate=True,
            evidence="用户明确许可本对象动作",
        )
    ]
    request["layout_alternatives"] = [
        dict(
            candidate_id="candidate",
            object_id=moving,
            changes=[operation],
            environmental_context=dict(interior_relations=[fresh]),
            physically_feasible=True,
            evidence="候选可容纳、保持操作与通行",
        )
    ]
    return request


def case_input(case):
    if case == "material":
        return material_request(
            element_use="wood_remedy", colour="green", shape="columnar"
        )
    if case == "candidate":
        return relation_candidate()
    return relation_request(
        present={
            "confirmed": True,
            "absent": False,
            "unknown": None,
            "photo_false": False,
            "photo_true": True,
        }[case],
        basis="image_observed" if case.startswith("photo_") else "user_confirmed",
    )


@pytest.mark.parametrize(
    "case",
    [
        "confirmed",
        "absent",
        "unknown",
        "photo_false",
        "photo_true",
        "material",
        "candidate",
    ],
)
def test_sourced_cases_agree_across_actual_rest_mcp_cli(
    monkeypatch, tmp_path, capsys, case
):
    request = case_input(case)
    http = rest_client(monkeypatch).post("/api/fengshui/assess", json=request)
    protocol = asyncio.run(mcp_call("assess", request))
    path = tmp_path / "来源关系.json"
    path.write_text(json.dumps(request, ensure_ascii=False))
    code = run(["fengshui_assess", "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    bodies = [http.json(), protocol.structured_content, cli]
    assert (
        without_transport(bodies[0])
        == without_transport(bodies[1])
        == without_transport(bodies[2])
    )
    for body in bodies:
        Draft202012Validator(FengshuiOutput.model_json_schema()).validate(body)
        assert not any(
            "orientation" in path for path in body["layout_analysis"]["missing_inputs"]
        )
        trace = body["rule_trace"]
        assert any("rule_id" in item for item in trace)
        if case == "material":
            assert (
                body["layout_analysis"]["material_analysis"]["findings"][0]["finding"]
                == "colour_substitute_only"
            )
        elif case == "candidate":
            candidate = body["layout_analysis"]["alternatives_analysis"]["findings"][0]
            assert candidate["status"] == "ready"
            assert (
                candidate["interior_analysis"]["findings"][0]["status"] == "not_present"
            )
        else:
            finding = body["layout_analysis"]["interior_analysis"]["findings"][0]
            expected = {
                "confirmed": "authored_caution",
                "absent": "not_present",
                "unknown": "needs_confirmation",
                "photo_false": "candidate_only",
                "photo_true": "candidate_only",
            }[case]
            assert finding["status"] == expected
            assert body["coverage"]["analysis_progress"]["assessment_complete"] is (
                case in {"confirmed", "absent"}
            )
            if case in {"absent", "unknown", "photo_false"}:
                assert finding["action_options"] == []


def test_actual_mcp_schema_and_strict_projection_include_only_requested_branches(
    monkeypatch,
):
    async def inspect():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            return next(
                t for t in await client.list_tools() if t.name == "fengshui_assess"
            ).input_schema

    schema = asyncio.run(inspect())
    encoded = json.dumps(schema)
    assert "interior_relations" in encoded and "material_facts" in encoded
    for case in ("confirmed", "material", "candidate"):
        Draft202012Validator(schema).validate(case_input(case))
    http = rest_client(monkeypatch).post(
        "/api/fengshui/assess",
        json=case_input("confirmed"),
        params={
            "fields": ["layout_analysis.interior_analysis", "rulesets", "rule_trace"],
            "strict_fields": True,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        },
    )
    assert http.status_code == 200, http.text
    assert "interior_analysis" in http.json()["layout_analysis"]
    assert "material_analysis" not in http.json()["layout_analysis"]


@pytest.mark.parametrize("moving", ["mirror", "bed"])
def test_either_relation_endpoint_can_move_without_faking_placement(moving):
    request = relation_candidate(moving)
    candidate = assess(**request)["layout_analysis"]["alternatives_analysis"][
        "findings"
    ][0]
    assert candidate["status"] == "ready"
    assert candidate["placement_findings"] == []
    assert any(
        c["method"] == "indoor_authored_relations"
        for c in candidate["rule_comparisons"]
    )


@pytest.mark.parametrize("moving", ["mirror", "bed"])
def test_another_relation_cannot_erase_old_predicate_on_either_endpoint(moving):
    request = relation_candidate(moving)
    # The mirror is still explicitly defined as a source and can acquire a
    # second independently confirmed relation. It cannot erase its first one.
    request["environmental_context"]["objects"].append(
        dict(
            object_id="second_bed",
            kind="furniture",
            purpose="bed",
            label="另一张床",
            evidence="独立确认另一用途",
        )
    )
    relation = request["layout_alternatives"][0]["environmental_context"][
        "interior_relations"
    ][0]
    if moving == "mirror":
        relation.update(relation_id="other", target_object_id="second_bed")
    else:
        relation.update(
            relation_id="other",
            source_object_id="corner",
            kind="pillar_corner_points_at_bed",
        )
    candidate = assess(**request)["layout_analysis"]["alternatives_analysis"][
        "findings"
    ][0]
    assert candidate["status"] == "candidate_only"
    assert any("reflection" in path for path in candidate["missing_inputs"])


def test_static_target_permissions_survive_candidate_context_recalculation():
    request = relation_candidate("bed")
    request["layout_constraints"].append(
        dict(
            object_id="mirror",
            can_relocate=False,
            can_rotate=False,
            evidence="固定镜子不许搬转",
        )
    )
    fresh = request["layout_alternatives"][0]["environmental_context"][
        "interior_relations"
    ][0]
    fresh["present"] = True
    candidate = assess(**request)["layout_analysis"]["alternatives_analysis"][
        "findings"
    ][0]
    actions = candidate["interior_analysis"]["action_options"]
    assert all(action["status"] == "blocked" for action in actions)
    assert all(not action["pending_confirmations"] for action in actions)


@pytest.mark.parametrize(
    "violation", ["role", "material", "goal", "duplicate", "unknown_id"]
)
def test_inconsistent_new_contracts_reject_on_all_transports(
    monkeypatch, tmp_path, capsys, violation
):
    request = relation_candidate()
    context = request["environmental_context"]
    if violation in {"material", "goal"}:
        context["material_facts"] = [
            dict(
                fact_id="m",
                object_id="mirror",
                material="processed_wood",
                element_use="wood_remedy",
                observation_basis="user_confirmed",
                evidence="同一镜框的确认属性",
            )
        ]
        fresh = deepcopy(context["material_facts"][0])
        fresh.update(
            material="metal" if violation == "material" else "processed_wood",
            element_use="metal_remedy" if violation == "goal" else "wood_remedy",
        )
        request["layout_alternatives"][0]["environmental_context"]["material_facts"] = [
            fresh
        ]
    elif violation == "role":
        context["objects"][0]["role"] = "pipe"
    elif violation == "duplicate":
        context["interior_relations"].append(
            {**context["interior_relations"][0], "relation_id": "duplicate"}
        )
    else:
        context["interior_relations"][0]["source_object_id"] = "unprovided"
    http = rest_client(monkeypatch).post("/api/fengshui/assess", json=request)
    protocol = asyncio.run(mcp_call("assess", request))
    path = tmp_path / "非法输入.json"
    path.write_text(json.dumps(request))
    code = run(["fengshui_assess", "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 422 and protocol.is_error and code == 1
    assert (
        http.json()["issues"] == protocol.structured_content["issues"] == cli["issues"]
    )


def test_target_role_cannot_be_changed_to_erase_relation():
    request = relation_candidate()
    request["layout_alternatives"][0]["environmental_context"]["objects"] = [
        {**request["environmental_context"]["objects"][0], "role": "sharp_corner"}
    ]
    with pytest.raises(ValidationError, match="类型或角色"):
        AssessRequest.model_validate(request)


def test_environment_role_cannot_override_explicit_layout_use():
    request = relation_request()
    request["placements"] = [
        dict(
            object_id="bed",
            purpose="desk",
            facing_direction="N",
            facing_role="desk_facing",
        )
    ]
    request["environmental_context"].pop("orientation")
    request["environmental_context"]["objects"][1].pop("purpose")
    request["environmental_context"]["objects"][1]["role"] = "bed"
    with pytest.raises(ValidationError, match="环境角色与已有用途"):
        AssessRequest.model_validate(request)
