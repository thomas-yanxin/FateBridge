"""Authored rule boundaries, tri-state forms and scoped material suggestions."""

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
from tests.fengshui.test_fengshui_layout import facing_only
from tests.fengshui.test_fengshui_surfaces import rest_client, without_transport
from tests.fixtures.fengshui import payload


def form_inputs(**changes):
    return {
        "methods": [],
        "form_observations": [
            {
                "object_id": "x",
                "purpose": "desk",
                "entrance_position": "front_left",
                "entrance_visible": True,
                "entrance_direct_line": False,
                "solid_backing": True,
                "observation_basis": "user_confirmed",
                "evidence": "已确认使用者视野、入口直线与实体支撑",
                **changes,
            }
        ],
    }


def adjustment_inputs(goal="drain"):
    inputs = facing_only()
    inputs["element_adjustments"] = [
        {
            "request_id": "r",
            "object_id": "table",
            "target_method": "bazhai",
            "subject_id": "a",
            "aspect": "facing",
            "goal": goal,
            "evidence": "基于当前作用域判定，按所选版本比较元素调节候选",
        }
    ]
    return inputs


def annual_inputs(direction="S", facing="W", year=2026):
    return {
        "methods": ["annual_stars"],
        "effective_year": year,
        "annual_remedy_ruleset_id": "pang_2026_annual_v1",
        "placements": [
            {
                "object_id": "x",
                "purpose": "desk",
                "location_direction": direction,
                "facing_direction": facing,
                "facing_role": "desk_facing",
            }
        ],
    }


@pytest.mark.parametrize("purpose", ["desk", "bed", "stove"])
def test_forms_independent_of_charts_birth_and_compass(purpose):
    inputs = form_inputs(purpose=purpose)
    if purpose == "stove":
        inputs["form_observations"][0]["solid_backing"] = False
    actual = assess(**inputs)
    assert actual["status"] == "complete" and actual["layers"] == {}
    assert actual["layout_analysis"]["status"] == "complete"
    finding = actual["layout_analysis"]["form_analysis"]["findings"][0]
    assert finding["finding"] == "matches_selected_form_rules"
    assert len(finding["checks"]) == (2 if purpose == "stove" else 3)
    assert actual["coverage"]["supplemental_rulesets"] == ["indoor_command_authored_v1"]
    assert "生辰" not in " ".join(actual["layout_analysis"]["missing_inputs"])


def test_reported_rear_right_and_distance_do_not_become_door_clash():
    inputs = {
        "methods": [],
        "form_observations": [
            {
                "object_id": "x",
                "purpose": "desk",
                "entrance_position": "back_right",
                "backing_distance_m": 1.5,
                "observation_basis": "user_confirmed",
                "evidence": "门在右后，椅背离衣架约1.5米；其余条件尚未确认",
            }
        ],
    }
    actual = assess(**inputs)
    form = actual["layout_analysis"]["form_analysis"]
    finding = form["findings"][0]
    assert actual["status"] == form["status"] == "partial"
    assert finding["derived_geometry"]["entrance_in_rear_half_plane"] is True
    assert finding["derived_geometry"]["entrance_direct_line"] is None
    assert (
        finding["derived_geometry"]["distance_verdict"]
        == "no_sourced_numerical_threshold"
    )
    assert all(c["finding"] == "undetermined" for c in finding["checks"])
    assert all(c["adjustment"] is None for c in finding["checks"])


def test_measured_distance_does_not_invent_lucky_cutoff():
    findings = [
        assess(**form_inputs(backing_distance_m=d))["layout_analysis"]["form_analysis"][
            "findings"
        ][0]
        for d in (0.0, 1.5, 100.0)
    ]
    assert all(f["finding"] == "matches_selected_form_rules" for f in findings)
    assert findings[0]["checks"] == findings[1]["checks"] == findings[2]["checks"]


def test_direct_line_and_view_are_separate_rules():
    actual = assess(**form_inputs(entrance_position="front", entrance_direct_line=True))
    finding = actual["layout_analysis"]["form_analysis"]["findings"][0]
    assert finding["finding"] == "adjust_position_or_layout"
    view, line, backing = finding["checks"]
    assert view["finding"] == backing["finding"] == "matches_rule"
    assert line["finding"] == "opposes_rule" and line["source_ids"] == ["F1"]


def test_image_hypothesis_is_not_confirmed_prescription():
    actual = assess(
        **form_inputs(observation_basis="image_observed", solid_backing=False)
    )
    finding = actual["layout_analysis"]["form_analysis"]["findings"][0]
    assert actual["status"] == "partial" and finding["finding"] == "needs_confirmation"
    assert all(c["candidate_only"] for c in finding["checks"])


def test_mirror_option_has_conditions_and_only_corrects_view():
    actual = assess(
        **form_inputs(entrance_position="back_right", entrance_visible=False)
    )
    form = actual["layout_analysis"]["form_analysis"]["findings"][0]
    mirror = form["object_options"][0]
    assert mirror["status"] == "conditional_option"
    assert len(mirror["conditions"]) == 3
    assert mirror["scope"] == "entrance_view_only_not_universal_sha_cure"
    corrected = assess(
        **form_inputs(
            entrance_position="back_right", entrance_visible=True, view_via_mirror=True
        )
    )
    assert (
        corrected["layout_analysis"]["form_analysis"]["findings"][0]["finding"]
        == "matches_selected_form_rules"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"backing_distance_m": -1},
        {"backing_distance_m": float("nan")},
        {"backing_distance_m": True},
        {"entrance_visible": "false"},
        {"evidence": "  "},
        {"observation_basis": "guessed"},
        {"entrance_position": "back", "entrance_visible": True},
        {"view_via_mirror": True, "entrance_visible": False},
        {"observation_basis": "image_observed", "backing_distance_m": 1.5},
    ],
)
def test_form_validation(changes):
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(form_inputs(**changes))


def test_mutable_response_cannot_corrupt_cached_rule_sources():
    a = assess(**form_inputs())
    a["layout_analysis"]["form_analysis"]["findings"][0]["checks"][0][
        "source_ids"
    ].append("fake")
    a["rulesets"][0]["sources"][0]["url"] = "fake"
    b = assess(**form_inputs())
    assert b["layout_analysis"]["form_analysis"]["findings"][0]["checks"][0][
        "source_ids"
    ] == ["F1"]
    assert b["rulesets"][0]["sources"][0]["url"].startswith("https://")


def test_element_goal_binds_current_star_and_selects_materials():
    plan = assess(**adjustment_inputs())["layout_analysis"]["element_remedies"][0]
    assert plan["status"] == "conditional_options"
    assert (
        plan["target_element"],
        plan["introduced_element"],
        plan["relationship"],
    ) == ("火", "土", "drains_target")
    assert plan["representations"]["objects"] == ["陶土器物", "石质器物"]
    assert (
        plan["representation_precedence"] == "actual_element_before_colour_substitute"
    )
    assert plan["quantity_or_weight"] is None and plan["purchase_required"] is False
    assert (
        plan["target_scope"]["subject_id"] == "a"
        and plan["target_scope"]["aspect"] == "facing"
    )


def test_supporting_bad_star_and_draining_matched_star_are_not_indicated():
    assert (
        assess(**adjustment_inputs("support"))["layout_analysis"]["element_remedies"][
            0
        ]["status"]
        == "not_indicated_by_current_rule"
    )
    inputs = adjustment_inputs()
    inputs["placements"][0]["facing_direction"] = "E"
    plan = assess(**inputs)["layout_analysis"]["element_remedies"][0]
    assert (
        plan["status"] == "not_indicated_by_current_rule"
        and "representations" not in plan
    )


def test_selected_afsi_wood_option_is_living_plant_not_wood_desk():
    inputs = adjustment_inputs()
    inputs["placements"][0]["facing_direction"] = "NW"  # 离命绝命金，泄金取水
    plan = assess(**inputs)["layout_analysis"]["element_remedies"][0]
    assert plan["introduced_element"] == "水"
    inputs["placements"][0]["facing_direction"] = "SW"  # 六煞水，泄水取木
    plan = assess(**inputs)["layout_analysis"]["element_remedies"][0]
    assert plan["introduced_element"] == "木"
    assert plan["representations"]["objects"] == ["健康的活植物"]
    assert plan["representations"]["excluded_objects"] == ["处理过的木家具"]


def test_unknown_gender_candidates_do_not_become_confirmed_cure():
    inputs = adjustment_inputs()
    inputs["occupants"][0].pop("gender_convention")
    actual = assess(**inputs)
    plans = actual["layout_analysis"]["element_remedies"]
    assert any(p["status"] == "candidate_only" for p in plans)
    assert not any(p["status"] == "conditional_options" for p in plans)
    assert (
        actual["layout_analysis"]["supplement_statuses"]["element_adjustments"]
        == "partial"
    )


def test_stove_seat_special_convention_not_treated_as_ordinary_bad_star():
    inputs = {
        **payload("assess"),
        "element_adjustments": [
            {
                "request_id": "r",
                "object_id": "stove",
                "target_method": "bazhai",
                "subject_id": "a",
                "aspect": "location",
                "goal": "drain",
                "evidence": "检验灶座用途边界",
            }
        ],
    }
    plan = assess(**inputs)["layout_analysis"]["element_remedies"][0]
    assert plan["status"] == "unsupported_application" and "representations" not in plan


def test_natal_role_and_candidate_preserved_in_element_requests():
    inputs = {
        "methods": ["xuankong_natal"],
        "xuankong": payload("xuankong_natal"),
        "placements": [{"object_id": "b", "purpose": "bed", "location_direction": "E"}],
        "element_adjustments": [
            {
                "request_id": "r",
                "object_id": "b",
                "target_method": "xuankong_natal",
                "star_role": "mountain",
                "goal": "drain",
                "evidence": "只检验山星调节候选",
            }
        ],
    }
    inputs["xuankong"]["house"]["facing_degrees"] = 355.5
    actual = assess(**inputs)
    plans = actual["layout_analysis"]["element_remedies"]
    assert len(plans) == 2
    assert all(
        p["status"] == "candidate_only" and p["target_scope"]["star_role"] == "mountain"
        for p in plans
    )
    assert len({p["target_scope"]["candidate_id"] for p in plans}) == 2


@pytest.mark.parametrize("direction,number", [("S", 5), ("NW", 2)])
def test_registered_2026_annual_rules_have_exact_location_time_and_goal(
    direction, number
):
    actual = assess(**annual_inputs(direction))
    recipe = actual["layout_analysis"]["annual_remedies"]["findings"][0]
    assert recipe["status"] == "conditional_author_rule"
    assert recipe["direction"] == direction and recipe["annual_star_number"] == number
    assert (
        recipe["introduced_element"] == "金"
        and recipe["relationship"] == "drains_target"
    )
    assert recipe["avoid_elements"] == ["火"]
    assert recipe["time_context"]["effective_year"] == 2026
    assert recipe["quantity_or_weight"] is None
    assert actual["layout_analysis"]["method_disagreements"][0]["source_ids"] == [
        "E1",
        "E2",
        "E3",
    ]


def test_facing_south_is_not_south_palace_cure_and_missing_location_stays_missing():
    recipe = assess(**annual_inputs("W", "S"))["layout_analysis"]["annual_remedies"][
        "findings"
    ][0]
    assert (
        recipe["status"] == "no_registered_prescription"
        and "introduced_element" not in recipe
    )
    inputs = annual_inputs()
    inputs["placements"][0].pop("location_direction")
    actual = assess(**inputs)["layout_analysis"]
    assert actual["annual_remedies"]["status"] == "partial"
    assert actual["annual_remedies"]["findings"][0]["status"] == "needs_location"


def test_policy_not_extrapolated_to_other_year_and_lichun_queries_use_effective_year():
    actual = assess(**annual_inputs(year=2027))["layout_analysis"]
    assert actual["status"] == "partial"
    assert actual["annual_remedies"]["status"] == "unsupported_year"
    assert actual["annual_remedies"]["findings"] == []
    inputs = annual_inputs()
    inputs.pop("effective_year")
    inputs["query_at"] = "2027-01-15T12:00:00+08:00"
    actual = assess(**inputs)["layout_analysis"]["annual_remedies"]
    assert actual["effective_year"] == 2026 and actual["status"] == "complete"


def test_introduced_element_effects_on_other_scopes_are_visible_not_merged():
    inputs = annual_inputs()
    inputs["methods"] = ["bazhai", "annual_stars"]
    inputs["occupants"] = [
        {"subject_id": "a", "effective_birth_year": 2000, "gender_convention": "male"}
    ]
    actual = assess(**inputs)["layout_analysis"]
    effects = actual["annual_remedies"]["findings"][0]["cross_scope_effects"]
    assert any(
        e["method"] == "bazhai"
        and e["target_element"] == "木"
        and e["relationship"] == "controls_target"
        for e in effects
    )
    assert any(
        e["method"] == "annual_stars"
        and e["target_element"] == "土"
        and e["relationship"] == "drains_target"
        for e in effects
    )
    assert all(
        e["scope"] == "relationship_only_no_merged_good_bad_verdict" for e in effects
    )
    assert "score" not in actual


@pytest.mark.parametrize(
    "inputs",
    [
        {"methods": []},
        {"methods": ["bazhai"], "annual_remedy_ruleset_id": "pang_2026_annual_v1"},
        {**adjustment_inputs(), "methods": ["annual_stars"]},
        {
            **adjustment_inputs(),
            "element_adjustments": [
                {
                    "request_id": "r",
                    "object_id": "missing",
                    "target_method": "bazhai",
                    "subject_id": "a",
                    "aspect": "facing",
                    "goal": "drain",
                    "evidence": "x",
                }
            ],
        },
        {**adjustment_inputs(), "element_ruleset_id": "guessed"},
    ],
)
def test_no_silent_ignored_or_invented_policy(inputs):
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(inputs)


@pytest.mark.parametrize(
    "inputs",
    [
        form_inputs(),
        adjustment_inputs(),
        annual_inputs(),
        annual_inputs(year=2027),
        form_inputs(observation_basis="image_observed"),
    ],
)
def test_supplements_match_real_rest_mcp_cli_and_output_schema(
    monkeypatch, tmp_path, capsys, inputs
):
    from fatebridge.mcp_server import create_mcp_app

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_assess",
                {"response_char_limit": 0, **inputs},
                raise_on_error=False,
            )

    rest = rest_client(monkeypatch).post("/api/fengshui/assess", json=inputs)
    protocol = asyncio.run(call())
    path = tmp_path / "layout.json"
    path.write_text(json.dumps(inputs))
    assert run(["fengshui_assess", "--request-file", str(path)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200 and not protocol.is_error
    assert (
        without_transport(rest.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    for result in [rest.json(), protocol.structured_content, cli]:
        Draft202012Validator(FengshuiOutput.model_json_schema()).validate(result)
        assert result["run_metadata"]["tool_name"] == "fengshui_assess"


def test_form_only_first_view_can_project_on_real_mcp_without_missing_chart_path():
    from fatebridge.application.examples import suggested_fields
    from fatebridge.mcp_server import create_mcp_app
    from fatebridge.services.tool_catalog import CATALOG

    spec = next(s for s in CATALOG if s.key == "fengshui_assess")

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_assess",
                {
                    **form_inputs(),
                    "fields": suggested_fields(spec),
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )

    actual = asyncio.run(call()).structured_content
    assert actual["layout_analysis"]["form_analysis"]["status"] == "complete"
    assert "snapshot_text" not in actual and "run_metadata" in actual


@pytest.mark.parametrize(
    "inputs",
    [
        form_inputs(entrance_visible="false"),
        form_inputs(observation_basis="image_observed", backing_distance_m=1.5),
        {"methods": ["bazhai"], "annual_remedy_ruleset_id": "pang_2026_annual_v1"},
    ],
)
def test_new_nested_and_semantic_errors_match_every_surface(
    monkeypatch, tmp_path, capsys, inputs
):
    from fatebridge.mcp_server import create_mcp_app

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_assess", inputs, raise_on_error=False
            )

    rest = rest_client(monkeypatch).post("/api/fengshui/assess", json=inputs)
    protocol = asyncio.run(call())
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(inputs))
    assert run(["fengshui_assess", "--request-file", str(path)]) == 1
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 422 and protocol.is_error
    assert (
        rest.json()["error_code"]
        == protocol.structured_content["error_code"]
        == cli["error_code"]
        == "validation_error"
    )
    assert (
        rest.json()["issues"] == protocol.structured_content["issues"] == cli["issues"]
    )
