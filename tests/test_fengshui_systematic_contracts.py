"""Nine-requirement audit regressions across actual REST, MCP and CLI calls."""

import asyncio
import json

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator

from fatebridge.application.description import mcp_description
from fatebridge.application.examples import suggested_fields
from fatebridge.cli import run
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import assess
from fatebridge.services.tool_catalog import CATALOG
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport


def orientation():
    return dict(
        direction_confirmed=True,
        north_reference="magnetic",
        center_confirmed=True,
        floorplan_alignment_confirmed=True,
        evidence="方位、中心及图纸对齐分别确认",
    )


def person():
    return dict(
        subject_id="p",
        gender_role="male",
        generation=0,
        family_roles=["parent"],
        evidence="家庭辈分和父亲身份已确认",
    )


def floor_request(complete_usage=False):
    source = dict(
        floor_id="first",
        level=1,
        uses_shared_orientation=True,
        center_confirmed=True,
        floorplan_alignment_confirmed=True,
        evidence="只核对了一层坐标，使用范围待核",
    )
    if complete_usage:
        source.update(
            usage_confirmed=True,
            usage_evidence="已完整核对一层实际住用范围，明确不包含p",
        )
    return {
        "methods": [],
        "environmental_context": {
            "orientation": orientation(),
            "household_composition_confirmed": True,
            "household_members": [person()],
            "floors": [
                source,
                dict(
                    floor_id="second",
                    level=2,
                    uses_shared_orientation=True,
                    center_confirmed=True,
                    floorplan_alignment_confirmed=True,
                    subject_ids=["p"],
                    suitability="confirmed_suitable",
                    suitability_evidence="已有带依据的二层适宜结论",
                    evidence="确认p在二层居住；尚不据此推断是否用一层",
                ),
            ],
            "floor_influences": [
                dict(
                    influence_id="local",
                    source_floor_id="first",
                    extent="floor_local_confirmed",
                    evidence="该项影响已确认局限一层",
                )
            ],
        },
    }


def case_input(case):
    if case.startswith("floor_"):
        return floor_request(case == "floor_confirmed_absence")
    if case == "symbolic_only":
        return dict(
            methods=[],
            environmental_context=dict(
                household_scope="symbolic_reference",
                household_composition_confirmed=True,
                household_members=[person()],
            ),
        )
    if case == "bazhai_scope":
        return dict(
            methods=["bazhai"],
            occupants=[
                dict(
                    subject_id="p", effective_birth_year=1990, gender_convention="male"
                )
            ],
            environmental_context=dict(
                orientation=orientation(),
                household_composition_confirmed=True,
                household_members=[person()],
            ),
        )
    inputs = dict(
        scene="workstation",
        house=dict(sitting_trigram="坎"),
        occupants=[
            dict(subject_id="p", effective_birth_year=1990, gender_convention="male")
        ],
        placements=[dict(object_id="desk", purpose="desk", location_direction="N")],
    )
    if case == "priority_explicit":
        inputs["methods"] = ["bazhai"]
    return inputs


@pytest.mark.parametrize(
    "case",
    [
        "floor_unknown_usage",
        "floor_confirmed_absence",
        "symbolic_only",
        "bazhai_scope",
        "priority_automatic",
        "priority_explicit",
    ],
)
def test_systematic_findings_agree_across_actual_transports(
    monkeypatch, tmp_path, capsys, case
):
    inputs = case_input(case)
    http = rest_client(monkeypatch).post("/api/fengshui/assess", json=inputs)
    protocol = asyncio.run(mcp_call("assess", inputs))
    path = tmp_path / "系统审查.json"
    path.write_text(json.dumps(inputs, ensure_ascii=False))
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
        if case.startswith("floor_"):
            review = body["layout_analysis"]["environmental_context"]
            scope = review["floor_review"]["influences"][0]["subject_scope"][0]
            if case == "floor_unknown_usage":
                assert scope["status"] == "usage_confirmation_required"
                assert (
                    body["coverage"]["analysis_progress"]["assessment_complete"]
                    is False
                )
                assert (
                    "environmental_context.floors.first.usage_confirmed"
                    in review["missing_inputs"]
                )
            else:
                assert scope["status"] == "local_exposure_not_assigned_to_other_floor"
                assert (
                    body["coverage"]["analysis_progress"]["assessment_complete"] is True
                )
        elif case in {"symbolic_only", "bazhai_scope"}:
            review = body["layout_analysis"]["environmental_context"]
            association = review["household_correspondences"][0]["associations"][0]
            assert (
                association["scope"]
                == "environmental_palace_symbolic_index_not_bazhai_minggua"
            )
            assert association["selected_applicable_methods"] == []
            if case == "symbolic_only":
                assert review["missing_inputs"] == []
                assert association["primary_palace"] == "乾"
                assert association["primary_direction"] is None
                assert association["physical_sector_binding"] == "not_confirmed"
                assert (
                    body["coverage"]["analysis_progress"]["assessment_complete"] is True
                )
        else:
            assert list(body["layers"]) == ["bazhai"]
            assert body["coverage"]["requested_analysis_status"] == "complete"
            policy = body["method_policy"]
            assert (
                body["coverage"]["method_priority_review"]["priority_review_status"]
                == policy["priority_review_status"]
            )
            reasons = {
                r["method"]: r["not_selected_reason"] for r in policy["method_priority"]
            }
            if case == "priority_automatic":
                assert policy["priority_review_status"] == "partial"
                assert set(policy["priority_missing_methods"]) == {
                    "nine_palace_flying_stars",
                    "jinsuo",
                }
                assert reasons["jinsuo"] != "explicitly_excluded"
            else:
                assert policy["priority_missing_methods"] == []
                assert reasons["jinsuo"] == "explicitly_excluded"


def test_published_guidance_and_strict_first_view_work_without_context(
    monkeypatch, tmp_path, capsys
):
    inputs = dict(
        scene="workstation",
        methods=[],
        form_observations=[
            dict(
                object_id="desk",
                purpose="desk",
                observation_basis="user_confirmed",
                entrance_visible=True,
                entrance_direct_line=False,
                solid_backing=True,
                evidence="仅审已确认室内形态",
            )
        ],
    )
    spec = next(s for s in CATALOG if s.key == "fengshui_assess")
    assert (
        "只有提供environmental_context时才追加layout_analysis.environmental_context"
        in mcp_description(spec)
    )
    fields = suggested_fields(spec) + ["method_policy"]
    controls = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    http = rest_client(monkeypatch).post(
        "/api/fengshui/assess", json=inputs, params=controls
    )
    protocol = asyncio.run(mcp_call("assess", {**inputs, **controls}))
    path = tmp_path / "形态.json"
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
            "--response-char-limit",
            "0",
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200, http.text
    assert code == 0 and not protocol.is_error
    assert (
        without_transport(http.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    assert "environmental_context" not in http.json()["layout_analysis"]


def test_live_schema_publishes_usage_and_household_scope():
    async def inspect():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            return next(
                t for t in await client.list_tools() if t.name == "fengshui_assess"
            ).input_schema

    schema = asyncio.run(inspect())
    encoded = json.dumps(schema)
    assert "usage_confirmed" in encoded and "usage_evidence" in encoded
    assert "household_scope" in encoded and "symbolic_reference" in encoded
    Draft202012Validator(schema).validate(case_input("floor_confirmed_absence"))
    Draft202012Validator(schema).validate(case_input("symbolic_only"))


@pytest.mark.parametrize(
    "case", ["current_usage", "candidate_usage", "static_floor", "north_reference"]
)
def test_inconsistent_usage_or_static_scope_is_rejected_by_all_transports(
    monkeypatch, tmp_path, capsys, case
):
    if case == "current_usage":
        inputs = floor_request(True)
        inputs["environmental_context"]["floors"][0]["object_ids"] = ["desk"]
        inputs["placements"] = [
            dict(
                object_id="desk", purpose="desk", location_direction="N", subject_id="p"
            )
        ]
    else:
        from tests.test_fengshui_candidate_features import inputs as candidate_features

        inputs = candidate_features(fresh=True)
        source = dict(
            floor_id="first",
            level=1,
            uses_shared_orientation=True,
            center_confirmed=True,
            floorplan_alignment_confirmed=True,
            object_ids=["furniture", "fixed_wall"],
            evidence="现状两对象属于一层",
        )
        inputs["environmental_context"] = dict(
            orientation=orientation(), floors=[source]
        )
        target = {
            **source,
            "floor_id": "second",
            "level": 2,
            "object_ids": ["furniture"],
        }
        if case == "candidate_usage":
            inputs["placements"][0]["subject_id"] = "user"
            inputs["layout_alternatives"][0]["placement"]["subject_id"] = "user"
            target.update(
                usage_confirmed=True,
                usage_evidence="明确完整名单为空，与家具使用人相矛盾",
            )
        elif case == "static_floor":
            target["object_ids"].append("fixed_wall")
        inputs["layout_alternatives"][0]["environmental_context"] = dict(
            orientation=orientation(), floors=[target]
        )
        if case == "north_reference":
            inputs["layout_alternatives"][0]["environmental_context"]["orientation"][
                "north_reference"
            ] = "true"
    http = rest_client(monkeypatch).post("/api/fengshui/assess", json=inputs)
    protocol = asyncio.run(mcp_call("assess", inputs))
    path = tmp_path / "矛盾范围.json"
    path.write_text(json.dumps(inputs))
    code = run(["fengshui_assess", "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 422 and protocol.is_error and code == 1
    assert (
        http.json()["issues"] == protocol.structured_content["issues"] == cli["issues"]
    )


def test_static_feature_keeps_original_floor_when_candidate_context_omits_it():
    from tests.test_fengshui_candidate_features import inputs as candidate_features

    inputs = candidate_features(fresh=True)
    source = dict(
        floor_id="first",
        level=1,
        uses_shared_orientation=True,
        center_confirmed=True,
        floorplan_alignment_confirmed=True,
        object_ids=["furniture", "fixed_wall"],
        evidence="现状家具和墙分别在一层确认",
    )
    inputs["environmental_context"] = dict(orientation=orientation(), floors=[source])
    target = {**source, "floor_id": "second", "level": 2, "object_ids": ["furniture"]}
    inputs["layout_alternatives"][0]["environmental_context"] = dict(
        orientation=orientation(), floors=[target]
    )
    result = assess(**inputs)
    candidate = result["layout_analysis"]["alternatives_analysis"]["findings"][0]
    assert candidate["status"] == "ready"
    features = {f["object_id"]: f for f in candidate["environment_adjustments"]}
    assert features["fixed_wall"]["floor_id"] == "first"
    assert features["furniture"]["floor_id"] == "second"
    assert candidate["layer_statuses"]["jinsuo"]["status"] == "complete"
    assert {f["method"] for f in candidate["rule_comparisons"]} == {
        "jinsuo",
        "annual_stars",
    }


@pytest.mark.parametrize("natal", [False, True])
def test_candidate_comparisons_include_each_selected_flying_star_layer(natal):
    if natal:
        from tests.test_xuankong_interpretation_contracts import assess_input

        inputs = assess_input()
        inputs.update(
            layout_constraints=[
                dict(object_id="bed", can_relocate=True, evidence="允许搬床")
            ],
            layout_alternatives=[
                dict(
                    candidate_id="new",
                    object_id="bed",
                    changes=["location"],
                    placement=dict(
                        object_id="bed", purpose="bed", location_direction="E"
                    ),
                    physically_feasible=True,
                    evidence="独立确认东宫新床位",
                )
            ],
        )
        expected = {"xuankong_natal"}
    else:
        from tests.test_fengshui_planning import proposal_request

        inputs = proposal_request()
        expected = {"annual_stars", "bazhai"}
    result = assess(**inputs)
    comparisons = result["layout_analysis"]["alternatives_analysis"]["findings"][0][
        "rule_comparisons"
    ]
    assert expected <= {c["method"] for c in comparisons}
    assert all(
        c["comparison_scope"]
        == "computed_star_reference_not_combination_fortune_judgment"
        for c in comparisons
        if c["method"] in {"annual_stars", "xuankong_natal"}
    )
