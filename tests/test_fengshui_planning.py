"""General scene, permission and independent-proposal contracts, not lucky cases."""

import asyncio
import json

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui.models import AssessRequest
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.services.fengshui import assess
from tests.fixtures.fengshui import payload
from tests.test_fengshui_surfaces import rest_client, without_transport


def observation(object_id="furniture", purpose="desk", **changes):
    return {
        "object_id": object_id,
        "purpose": purpose,
        "entrance_visible": True,
        "entrance_direct_line": False,
        "solid_backing": True,
        "observation_basis": "user_confirmed",
        "evidence": "合成资料：独立核对使用位置",
        **changes,
    }


def proposal_request(purpose="desk", role="desk_facing"):
    current = {
        "object_id": "furniture",
        "purpose": purpose,
        "location_direction": "N",
        "facing_direction": "S",
        "facing_role": role,
    }
    return {
        "scene": "home",
        "methods": ["bazhai", "annual_stars"],
        "house": {"sitting_trigram": "坎"},
        "effective_year": 2026,
        "occupants": [
            {
                "subject_id": "user",
                "effective_birth_year": 1990,
                "gender_convention": "male",
            }
        ],
        "placements": [current],
        "layout_constraints": [
            {
                "object_id": "furniture",
                "can_relocate": True,
                "can_rotate": True,
                "evidence": "允许搬位和转向",
            }
        ],
        "layout_alternatives": [
            {
                "candidate_id": "proposal",
                "object_id": "furniture",
                "changes": ["location", "facing"],
                "placement": {
                    **current,
                    "location_direction": "E",
                    "facing_direction": "N",
                },
                "physically_feasible": True,
                "evidence": "新位置可容纳且不妨碍操作、通行",
            }
        ],
    }


@pytest.mark.parametrize("scene", [None, "workstation", "home"])
@pytest.mark.parametrize("purpose", ["desk", "bed", "stove"])
def test_authored_only_does_not_request_unused_birth_compass_or_year(scene, purpose):
    inputs = {"form_observations": [observation(purpose=purpose)]}
    if scene:
        inputs["scene"] = scene
    result = assess(**inputs)
    assert result["layers"] == {}
    assert result["layout_analysis"]["missing_inputs"] == []
    assert result["coverage"]["requested_analysis_status"] == "complete"
    assert result["rulesets"] and result["rule_trace"]


def test_scene_selection_uses_inputs_and_explicit_choice_wins():
    base = proposal_request()
    explicit = assess(**base)
    automatic = assess(**{k: v for k, v in base.items() if k != "methods"})
    assert set(automatic["layers"]) == {"bazhai", "annual_stars"}
    assert automatic["layers"] == explicit["layers"]
    assert (
        automatic["coverage"]["scene_scope"]["selection_policy"]
        == "explicit_methods_override_input_driven_default"
    )
    assert "全宅审查" in automatic["snapshot_text"]
    assert "jinsuo" not in automatic["layers"]
    assert assess(**{**base, "methods": ["annual_stars"]})["coverage"]["scene_scope"][
        "selected_methods"
    ] == ["annual_stars"]


def test_empty_scene_is_partial_and_legacy_raw_request_keeps_its_layers():
    result = assess(scene="workstation", analyze_layout=True)
    assert result["status"] == "partial"
    assert result["coverage"]["analysis_progress"]["assessment_complete"] is False
    assert set(assess()["layers"]) == {"bazhai", "jinsuo", "annual_stars"}


@pytest.mark.parametrize(
    "purpose,role",
    [
        ("door", "door_facing"),
        ("bed", "headboard"),
        ("desk", "desk_facing"),
        ("stove", "fire_mouth"),
    ],
)
@pytest.mark.parametrize(
    "permission,feasible,expected",
    [
        (True, True, "ready"),
        (False, True, "blocked"),
        (True, False, "blocked"),
        (None, True, "conditional_option"),
        (True, None, "conditional_option"),
    ],
)
def test_feasibility_is_distinct_from_permission_for_every_purpose(
    purpose, role, permission, feasible, expected
):
    inputs = proposal_request(purpose, role)
    inputs["layout_constraints"][0]["can_relocate"] = permission
    inputs["layout_alternatives"][0]["physically_feasible"] = feasible
    result = assess(**inputs)
    actual = result["layout_analysis"]["alternatives_analysis"]["findings"][0]
    assert actual["status"] == expected
    if expected == "blocked":
        assert actual["pending_confirmations"] == []
    assert result["coverage"]["analysis_progress"]["assessment_complete"] is True
    assert "score" not in actual


@pytest.mark.parametrize("location", ["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
@pytest.mark.parametrize(
    "purpose,role",
    [
        ("door", "door_facing"),
        ("bed", "headboard"),
        ("desk", "desk_facing"),
        ("stove", "fire_mouth"),
    ],
)
def test_proposals_match_independent_recalculation_across_directions_and_purposes(
    location, purpose, role
):
    inputs = proposal_request(purpose, role)
    inputs["layout_alternatives"][0]["placement"]["location_direction"] = location
    actual = assess(**inputs)["layout_analysis"]["alternatives_analysis"]["findings"][0]
    independent = assess(
        **{
            **inputs,
            "layout_alternatives": [],
            "placements": [inputs["layout_alternatives"][0]["placement"]],
        }
    )
    assert (
        actual["placement_findings"]
        == independent["layout_analysis"]["placement_findings"]
    )
    # Annual stars follow the new location, never the new facing direction.
    annual = next(
        f for f in actual["placement_findings"] if f["method"] == "annual_stars"
    )
    assert annual["direction"] == location


def test_new_position_never_reuses_previous_entrance_and_backing():
    inputs = proposal_request()
    inputs["form_observations"] = [observation()]
    actual = assess(**inputs)["layout_analysis"]["alternatives_analysis"]["findings"][0]
    assert actual["status"] == "candidate_only"
    assert actual["form_analysis"]["findings"] == []
    inputs["layout_alternatives"][0]["form_observation"] = observation(
        entrance_visible=False, solid_backing=False
    )
    actual = assess(**inputs)["layout_analysis"]["alternatives_analysis"]["findings"][0]
    assert actual["status"] == "ready"  # executable is distinct from matches-rule
    checks = actual["form_analysis"]["findings"][0]["checks"]
    assert (
        next(c for c in checks if c["criterion"] == "entrance_visible")["finding"]
        == "opposes_rule"
    )
    assert (
        next(c for c in checks if c["criterion"] == "solid_backing")["finding"]
        == "opposes_rule"
    )


@pytest.mark.parametrize(
    "field",
    [
        "passage_direct_line",
        "exposed_beam_over_user",
        "sharp_corner_points_at_user",
        "window_position",
    ],
)
def test_candidate_cannot_hide_a_previously_assessed_form_criterion(field):
    inputs = proposal_request()
    inputs["form_observations"] = [
        observation(**{field: "front" if field == "window_position" else True})
    ]
    inputs["layout_alternatives"][0]["form_observation"] = observation()
    candidate = assess(**inputs)["layout_analysis"]["alternatives_analysis"][
        "findings"
    ][0]
    assert candidate["status"] == "candidate_only"
    assert any(p.endswith(field) for p in candidate["missing_inputs"])


def test_candidate_cannot_hide_a_previously_assessed_facing():
    inputs = proposal_request()
    for key in ("facing_direction", "facing_role"):
        del inputs["layout_alternatives"][0]["placement"][key]
    candidate = assess(**inputs)["layout_analysis"]["alternatives_analysis"][
        "findings"
    ][0]
    assert candidate["status"] == "candidate_only"
    assert any(p.endswith("facing_direction") for p in candidate["missing_inputs"])


def test_unknown_or_photo_proposal_does_not_reopen_current_review_or_become_ready():
    inputs = {
        "scene": "workstation",
        "form_observations": [observation()],
        "layout_constraints": [
            {"object_id": "furniture", "can_rotate": True, "evidence": "允许转向"}
        ],
        "layout_alternatives": [
            {
                "candidate_id": "turn",
                "object_id": "furniture",
                "changes": ["facing"],
                "form_observation": observation(observation_basis="image_observed"),
                "physically_feasible": True,
                "evidence": "照片候选",
            }
        ],
    }
    actual = assess(**inputs)
    assert (
        actual["layout_analysis"]["alternatives_analysis"]["findings"][0]["status"]
        == "candidate_only"
    )
    assert actual["coverage"]["analysis_progress"]["assessment_complete"] is True


def test_fixed_furniture_blocks_moves_and_additions_but_preserves_findings():
    base = proposal_request()
    base["form_observations"] = [
        observation(
            entrance_visible=False, entrance_direct_line=True, solid_backing=False
        )
    ]
    original = assess(**base)
    base["layout_constraints"][0].update(
        can_relocate=False, can_rotate=False, can_add_items=False
    )
    result = assess(**base)
    assert original["layers"] == result["layers"]
    form = result["layout_analysis"]["form_analysis"]["findings"][0]
    assert all(
        c["action_status"] == "blocked" and c["pending_confirmations"] == []
        for c in form["checks"]
        if c["adjustment"]
    )
    assert form["object_options"][0]["status"] == "blocked"
    assert form["object_options"][0]["pending_confirmations"] == []


def test_proposal_only_forms_publish_their_sources_without_changing_current_forms():
    inputs = proposal_request()
    inputs["layout_alternatives"][0]["form_observation"] = observation()
    result = assess(**inputs)
    assert result["layout_analysis"]["form_analysis"]["status"] == "not_requested"
    assert any(
        r["ruleset_id"] == "indoor_command_authored_v1" for r in result["rulesets"]
    )
    assert any(
        r["ruleset_id"] == "indoor_command_authored_v1" for r in result["rule_trace"]
    )


def test_desk_wide_addition_prohibition_filters_desktop_without_faking_a_surface():
    from tests.test_fengshui_surfaces_authored import surface_input

    inputs = surface_input()
    inputs["surface_layouts"][0]["items"] = []
    inputs["surface_constraints"] = []
    inputs["form_observations"] = [observation(object_id="work-surface")]
    inputs["layout_constraints"] = [
        {
            "object_id": "work-surface",
            "can_add_items": False,
            "evidence": "桌面不能新增",
        }
    ]
    result = assess(**inputs)
    surface = result["layout_analysis"]["surface_analysis"]
    assert all(
        a["status"] == "blocked" and a["pending_confirmations"] == []
        for f in surface["findings"]
        for a in f["action_options"]
    )
    assert surface["analysis_progress"]["action_readiness"] == "blocked"
    inputs["surface_constraints"] = [
        {"object_id": "work-surface", "can_add_items": True, "evidence": "矛盾许可"}
    ]
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(inputs)


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_constraint",
        "duplicate_constraint",
        "unknown_object",
        "duplicate_candidate",
        "identity",
        "purpose",
        "changes",
        "users",
        "permission_string",
        "empty_evidence",
    ],
)
def test_invalid_candidate_or_constraint_is_rejected(mutation):
    inputs = proposal_request()
    candidate = inputs["layout_alternatives"][0]
    if mutation == "unknown_constraint":
        inputs["layout_constraints"][0]["object_id"] = "unknown"
    elif mutation == "duplicate_constraint":
        inputs["layout_constraints"] *= 2
    elif mutation == "unknown_object":
        candidate["object_id"] = "unknown"
    elif mutation == "duplicate_candidate":
        inputs["layout_alternatives"] *= 2
    elif mutation == "identity":
        candidate["placement"]["object_id"] = "unknown"
    elif mutation == "purpose":
        candidate["placement"].update(purpose="bed", facing_role="headboard")
    elif mutation == "changes":
        candidate["changes"] = ["facing"]
    elif mutation == "users":
        inputs["occupants"].append(
            {
                "subject_id": "other",
                "effective_birth_year": 1991,
                "gender_convention": "female",
            }
        )
        candidate["placement"]["subject_id"] = "user"
    elif mutation == "permission_string":
        inputs["layout_constraints"][0]["can_rotate"] = "true"
    elif mutation == "empty_evidence":
        candidate["evidence"] = " "
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(inputs)


def test_natal_scene_never_replaces_history_with_annual_year():
    inputs = {
        "scene": "home",
        "xuankong": payload("xuankong_natal"),
        "effective_year": 2026,
        "placements": [
            {"object_id": "bed", "purpose": "bed", "location_direction": "E"}
        ],
    }
    current = assess(**inputs)
    later = assess(**{**inputs, "effective_year": 2027})
    assert current["layers"]["xuankong_natal"] == later["layers"]["xuankong_natal"]
    assert current["layers"]["annual_stars"] != later["layers"]["annual_stars"]
    assert (
        "complete_natal_combination_interpretation_and_external_activation"
        in current["layout_analysis"]["unsupported_queries"]
    )


@pytest.mark.parametrize("automatic", [False, True])
def test_scene_constraints_and_proposals_match_all_transports(
    monkeypatch, tmp_path, capsys, automatic
):
    from fatebridge.mcp_server import create_mcp_app

    inputs = proposal_request()
    if automatic:
        del inputs["methods"]
    controls = {
        "fields": [
            "coverage",
            "layout_analysis.alternatives_analysis",
            "rulesets",
            "rule_trace",
        ],
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }

    async def call():
        async with Client(create_mcp_app()) as client:
            public = {t.name: t for t in await client.list_tools()}["fengshui_assess"]
            Draft202012Validator(
                public.model_dump(by_alias=True)["inputSchema"]
            ).validate(inputs)
            return await client.call_tool("fengshui_assess", {**inputs, **controls})

    rest = rest_client(monkeypatch).post(
        "/api/fengshui/assess", params=controls, json=inputs
    )
    mcp = asyncio.run(call())
    path = tmp_path / "proposal.json"
    path.write_text(json.dumps(inputs))
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
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200 and not mcp.is_error
    assert (
        without_transport(rest.json())
        == without_transport(mcp.structured_content)
        == without_transport(cli)
    )
    for result in (rest.json(), mcp.structured_content, cli):
        Draft202012Validator(FengshuiOutput.model_json_schema()).validate(result)
        assert result["layout_analysis"]["alternatives_analysis"][
            "ready_candidate_ids"
        ] == ["proposal"]


@pytest.mark.parametrize("mutation", ["unknown_object", "purpose", "permission_string"])
def test_invalid_planning_inputs_fail_on_every_transport(
    monkeypatch, tmp_path, capsys, mutation
):
    from fatebridge.mcp_server import create_mcp_app

    inputs = proposal_request()
    if mutation == "unknown_object":
        inputs["layout_constraints"][0]["object_id"] = "unknown"
    elif mutation == "purpose":
        inputs["layout_alternatives"][0]["placement"].update(
            purpose="bed", facing_role="headboard"
        )
    else:
        inputs["layout_constraints"][0]["can_rotate"] = "true"

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_assess", inputs, raise_on_error=False
            )

    rest = rest_client(monkeypatch).post("/api/fengshui/assess", json=inputs)
    assert rest.status_code == 422
    assert asyncio.run(call()).is_error
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(inputs))
    assert run(["fengshui_assess", "--request-file", str(path)]) != 0
    capsys.readouterr()
