"""Opt-in natal interpretation preserves calculations and public transports."""

import asyncio
import hashlib
import json
from copy import deepcopy

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator

from fatebridge.application import result_delivery as delivery
from fatebridge.application.examples import call_guidance, suggested_fields
from fatebridge.cli import run
from fatebridge.core.fengshui.models import (
    XuankongInterpretationRequest,
    XuankongRequest,
)
from fatebridge.core.fengshui.natal_interpretation import analyze_natal_interpretation
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import assess, calculate_xuankong_natal
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.fengshui import payload
from tests.test_fengshui_surfaces import mcp_call, rest_client, without_transport


def interpretation_input():
    return {
        "current_period_number": 9,
        "period_evidence": "已确认按九运评价，非宅盘历史定运",
        "external_forms": [
            {
                "direction": "N",
                "mountain_present": True,
                "water_present": False,
                "observation_basis": "user_confirmed",
                "evidence": "明确确认北宫外部有山形、无水形",
            }
        ],
    }


def natal_input():
    return {**payload("xuankong_natal"), "interpretation": interpretation_input()}


def assess_input():
    return {
        "methods": ["xuankong_natal"],
        "analyze_layout": True,
        "xuankong": natal_input(),
        "placements": [
            {"object_id": "bed", "purpose": "bed", "location_direction": "N"}
        ],
    }


@pytest.mark.parametrize("name", ["xuankong_natal", "assess"])
def test_opt_in_interpretation_matches_actual_rest_mcp_cli(
    monkeypatch, tmp_path, capsys, name
):
    inputs = natal_input() if name == "xuankong_natal" else assess_input()
    response = rest_client(monkeypatch).post("/api/fengshui/" + name, json=inputs)
    protocol = asyncio.run(mcp_call(name, inputs))
    path = tmp_path / "玄空解释.json"
    path.write_text(json.dumps(inputs, ensure_ascii=False))
    code = run(["fengshui_" + name, "--request-file", str(path)])
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
        assert body["layers"]["xuankong_natal"]["interpretation"]


@pytest.mark.parametrize(
    "bad",
    [
        {"unknown_interpretation_option": True},
        {"ruleset_id": "future_unreviewed_rules"},
        {"current_period_number": True, "period_evidence": "布尔值不是运数"},
        {"current_period_number": 0, "period_evidence": "确认"},
        {"current_period_number": 10, "period_evidence": "确认"},
        {"current_period_number": 9},
        {"period_evidence": "孤立依据"},
        {"current_period_number": 9, "period_evidence": " "},
        {"external_forms": [{"direction": "N", "evidence": "缺观察"}]},
        {
            "external_forms": [
                {
                    "direction": "N",
                    "mountain_present": "true",
                    "observation_basis": "user_confirmed",
                    "evidence": "不能由字符串推测布尔值",
                }
            ]
        },
        {
            "external_forms": [
                {
                    "direction": "N",
                    "water_present": True,
                    "observation_basis": "user_confirmed",
                    "evidence": " ",
                }
            ]
        },
        {
            "external_forms": [
                {
                    "direction": "N",
                    "water_present": True,
                    "observation_basis": "user_confirmed",
                    "evidence": "同宫第一条",
                },
                {
                    "direction": "N",
                    "mountain_present": False,
                    "observation_basis": "user_confirmed",
                    "evidence": "同宫第二条不得静默覆盖",
                },
            ]
        },
        {
            "external_forms": [
                {
                    "direction": "C",
                    "mountain_present": True,
                    "observation_basis": "user_confirmed",
                    "evidence": "外局只支持八方",
                }
            ]
        },
        {
            "external_forms": [
                {
                    "direction": "N",
                    "water_present": True,
                    "observation_basis": "guessed",
                    "evidence": "猜测不合法",
                }
            ]
        },
    ],
)
@pytest.mark.parametrize("name", ["xuankong_natal", "assess"])
def test_invalid_nested_interpretation_is_rejected_on_all_transports(
    monkeypatch, tmp_path, capsys, bad, name
):
    inputs = {**payload("xuankong_natal"), "interpretation": bad}
    if name == "assess":
        inputs = {"methods": ["xuankong_natal"], "xuankong": inputs}
    response = rest_client(monkeypatch).post("/api/fengshui/" + name, json=inputs)
    protocol = asyncio.run(mcp_call(name, inputs))
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(inputs))
    code = run(["fengshui_" + name, "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 422 and protocol.is_error and code == 1
    assert (
        response.json()["issues"]
        == protocol.structured_content["issues"]
        == cli["issues"]
    )


def test_published_mcp_schema_exposes_the_same_opt_in_contract():
    inputs = natal_input()
    Draft202012Validator(XuankongRequest.model_json_schema()).validate(inputs)

    async def check():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            schemas = {t.name: t.input_schema for t in await client.list_tools()}
            Draft202012Validator(schemas["fengshui_xuankong_natal"]).validate(inputs)
            Draft202012Validator(schemas["fengshui_assess"]).validate(assess_input())
            invalid = deepcopy(inputs)
            invalid["interpretation"]["unexpected"] = True
            assert list(
                Draft202012Validator(schemas["fengshui_xuankong_natal"]).iter_errors(
                    invalid
                )
            )

    asyncio.run(check())


def test_interpretation_does_not_change_natal_numbers_or_add_an_annual_layer():
    before = calculate_xuankong_natal(**payload("xuankong_natal"))
    after = calculate_xuankong_natal(**natal_input())
    old = before["layers"]["xuankong_natal"]
    new = after["layers"]["xuankong_natal"]
    assert "interpretation" not in old
    for field in ("chart", "candidates", "period_context", "orientation_context"):
        assert new[field] == old[field]
    assert new["period_context"]["number"] == 8
    assert "annual_stars" not in after["layers"]
    assert new["interpretation"]


def test_annual_year_never_replaces_history_or_interpretation_period():
    inputs = assess_input()
    inputs["methods"].append("annual_stars")
    earlier = assess(**inputs, effective_year=2026)
    later = assess(**inputs, effective_year=2027)
    assert earlier["layers"]["xuankong_natal"] == later["layers"]["xuankong_natal"]
    assert earlier["layers"]["annual_stars"] != later["layers"]["annual_stars"]


def test_ordered_pairs_keep_five_element_direction_and_all_three_numbers():
    result = calculate_xuankong_natal(**natal_input())
    layer = result["layers"]["xuankong_natal"]
    interpreted = layer["interpretation"]["candidates"][0]["palaces"]
    expected = {
        "C": (6, 1, "mountain_generates_facing"),
        "N": (1, 6, "facing_generates_mountain"),
        "SW": (9, 7, "mountain_controls_facing"),
        "SE": (7, 9, "facing_controls_mountain"),
        "E": (8, 8, "same_element"),
    }
    for direction, (mountain, facing, relationship) in expected.items():
        palace = interpreted[direction]
        original = layer["chart"]["palaces"][direction]
        for key in ("period_star_number", "mountain_star_number", "facing_star_number"):
            assert palace[key] == original[key]
        assert palace["mountain_star_number"] == mountain
        assert palace["facing_star_number"] == facing
        assert palace["ordered_pair"]["relationship"] == relationship
        assert palace["ordered_pair"]["rule_id"]
        assert palace["ordered_pair"]["source_ids"]
    assert interpreted["SW"]["timeliness"]["mountain"]["status"] == "current"
    assert interpreted["SW"]["timeliness"]["facing"]["status"] == "not_current"
    assert interpreted["SE"]["timeliness"]["facing"]["status"] == "current"


def test_all_81_ordered_star_element_relationships_against_handwritten_matrix():
    # Rows are mountain stars 1..9; columns are facing stars 1..9. The oracle
    # is hand-transcribed from the five-element cycle, not production mappings.
    expected_rows = [
        "S FC MG MG FC FG FG FC MC",
        "MC S FC FC S MG MG S FG",
        "FG MC S S MC FC FC MC MG",
        "FG MC S S MC FC FC MC MG",
        "MC S FC FC S MG MG S FG",
        "MG FG MC MC FG S S FG FC",
        "MG FG MC MC FG S S FG FC",
        "MC S FC FC S MG MG S FG",
        "FC MG FG FG MG MC MC MG S",
    ]
    vocabulary = {
        "S": "same_element",
        "MG": "mountain_generates_facing",
        "FG": "facing_generates_mountain",
        "MC": "mountain_controls_facing",
        "FC": "facing_controls_mountain",
    }
    charts = [
        {
            "candidate_id": f"pair-{mountain}-{facing}",
            "period_number": 8,
            "palaces": {
                "C": {
                    "period_star_number": 8,
                    "mountain_star_number": mountain,
                    "facing_star_number": facing,
                }
            },
        }
        for mountain in range(1, 10)
        for facing in range(1, 10)
    ]
    result = analyze_natal_interpretation(
        XuankongInterpretationRequest.model_validate(interpretation_input()),
        {"candidates": charts},
        [],
    )
    assert len(result["candidates"]) == 81
    for chart in result["candidates"]:
        pair = chart["palaces"]["C"]["ordered_pair"]
        mountain, facing = pair["mountain_star_number"], pair["facing_star_number"]
        token = expected_rows[mountain - 1].split()[facing - 1]
        assert pair["relationship"] == vocabulary[token], (mountain, facing)


def test_missing_explicit_period_is_not_filled_from_current_annual_or_natal_period():
    inputs = assess_input()
    inputs["methods"].append("annual_stars")
    inputs["effective_year"] = 2026
    inputs["xuankong"]["interpretation"] = {}
    result = assess(**inputs)
    interpretation = result["layers"]["xuankong_natal"]["interpretation"]
    assert interpretation["current_period_context"]["number"] is None
    assert interpretation["status"] == "partial"
    assert result["layers"]["xuankong_natal"]["period_context"]["number"] == 8
    assert result["layers"]["annual_stars"]["current_period"]["number"] == 9
    assert "interpretation.current_period_number" in interpretation["missing_inputs"]


def test_moved_proposal_recalculates_its_purpose_at_its_new_house_palace():
    inputs = assess_input()
    inputs["xuankong"]["interpretation"]["external_forms"] = [
        {
            "direction": "SW",
            "mountain_present": True,
            "observation_basis": "user_confirmed",
            "evidence": "整宅西南外局有山形",
        }
    ]
    inputs["layout_constraints"] = [
        {"object_id": "bed", "can_relocate": True, "evidence": "已明确允许搬床"}
    ]
    inputs["layout_alternatives"] = [
        {
            "candidate_id": "move-bed",
            "object_id": "bed",
            "changes": ["location"],
            "placement": {
                "object_id": "bed",
                "purpose": "bed",
                "location_direction": "SW",
            },
            "physically_feasible": True,
            "evidence": "西南实际空间可容纳床且保持通行",
        }
    ]
    result = assess(**inputs)
    current = result["layers"]["xuankong_natal"]["interpretation"]["candidates"][0][
        "placement_findings"
    ][0]
    proposal = result["layout_analysis"]["alternatives_analysis"]["findings"][0]
    moved = proposal["natal_interpretation"]["candidates"][0]["placement_findings"][0]
    assert current["location_direction"] == "N" and current["selected_star_number"] == 1
    assert moved["location_direction"] == "SW" and moved["selected_star_number"] == 9
    assert moved["condition_match"] is True
    assert moved["external_form_condition"]["evidence"] == "整宅西南外局有山形"


def test_boundary_candidates_are_interpreted_individually():
    inputs = natal_input()
    inputs["house"]["facing_degrees"] = 355.5
    layer = calculate_xuankong_natal(**inputs)["layers"]["xuankong_natal"]
    charts = {candidate["candidate_id"]: candidate for candidate in layer["candidates"]}
    findings = layer["interpretation"]["candidates"]
    assert len(findings) == len(charts) > 1
    for finding in findings:
        assert finding["candidate_only"] is True
        for direction, palace in finding["palaces"].items():
            original = charts[finding["candidate_id"]]["palaces"][direction]
            assert palace["mountain_star_number"] == original["mountain_star_number"]
            assert palace["facing_star_number"] == original["facing_star_number"]


@pytest.mark.parametrize("observed", [True, False])
@pytest.mark.parametrize("basis", ["user_confirmed", "image_observed"])
def test_explicit_false_and_photographic_external_forms_keep_their_certainty(
    observed, basis
):
    inputs = natal_input()
    inputs["interpretation"]["external_forms"] = [
        {
            "direction": "SW",
            "mountain_present": observed,
            "observation_basis": basis,
            "evidence": "独立观察西南外部山形",
        }
    ]
    result = calculate_xuankong_natal(**inputs)["layers"]["xuankong_natal"][
        "interpretation"
    ]
    finding = result["candidates"][0]["palaces"]["SW"]["external_form_analysis"][
        "mountain"
    ]
    assert finding["observed"] is observed
    assert finding["candidate_only"] is (basis == "image_observed")
    assert finding["status"] == (
        "candidate_only"
        if basis == "image_observed"
        else ("matches_presence_requirement" if observed else "required_form_absent")
    )
    if basis == "image_observed":
        assert result["missing_inputs"]


def test_confirmed_absence_completes_presence_review_without_inventing_bad_layout():
    inputs = natal_input()
    inputs["interpretation"]["external_forms"] = [
        {
            "direction": "SW",
            "mountain_present": False,
            "observation_basis": "measured",
            "evidence": "西南当令山星宫确认无山形",
        },
        {
            "direction": "SE",
            "water_present": False,
            "observation_basis": "user_confirmed",
            "evidence": "东南当令向星宫确认无水形",
        },
    ]
    result = calculate_xuankong_natal(**inputs)
    interpretation = result["layers"]["xuankong_natal"]["interpretation"]
    assert interpretation["status"] == "complete"
    assert interpretation["missing_inputs"] == []
    assert interpretation["rule_coverage_status"] == "limited"
    assert interpretation["overall_auspiciousness"] == "not_produced"
    assert (
        interpretation["candidates"][0]["palaces"]["SW"]["external_form_analysis"][
            "mountain"
        ]["status"]
        == "required_form_absent"
    )
    center = interpretation["candidates"][0]["palaces"]["C"]["external_form_analysis"]
    assert {f["status"] for f in center.values()} == {"not_applicable_center"}


def test_unknown_required_external_form_remains_partial_without_guessing():
    inputs = natal_input()
    inputs["interpretation"]["external_forms"] = []
    interpretation = calculate_xuankong_natal(**inputs)["layers"]["xuankong_natal"][
        "interpretation"
    ]
    assert interpretation["status"] == "partial"
    assert {
        "interpretation.external_forms.SW.mountain_present",
        "interpretation.external_forms.SE.water_present",
    } <= set(interpretation["missing_inputs"])
    sw = interpretation["candidates"][0]["palaces"]["SW"]["external_form_analysis"][
        "mountain"
    ]
    assert sw["observed"] is None and sw["status"] == "needs_confirmation"


def test_bed_and_door_use_separate_star_roles_at_the_same_palace():
    inputs = assess_input()
    inputs["placements"] = [
        {"object_id": "bed", "purpose": "bed", "location_direction": "SE"},
        {"object_id": "door", "purpose": "door", "location_direction": "SE"},
    ]
    inputs["xuankong"]["interpretation"]["external_forms"] = [
        {
            "direction": "SE",
            "water_present": True,
            "observation_basis": "user_confirmed",
            "evidence": "东南明确确认外部水形",
        }
    ]
    interpretation = assess(**inputs)["layers"]["xuankong_natal"]["interpretation"]
    bed, door = interpretation["candidates"][0]["placement_findings"]
    assert bed["selected_star_role"] == "mountain" and bed["selected_star_number"] == 7
    assert bed["status"] == "rule_not_covered_not_inauspicious"
    assert door["selected_star_role"] == "facing" and door["selected_star_number"] == 9
    assert door["status"] == "conditional_role_assessment"
    assert door["condition_match"] is True


@pytest.mark.parametrize("purpose", ["desk", "bed", "door"])
def test_completed_external_review_does_not_hide_uncovered_purpose_or_invent_action(
    purpose,
):
    inputs = assess_input()
    inputs["placements"][0].update(object_id=purpose, purpose=purpose)
    inputs["xuankong"]["interpretation"]["external_forms"] = [
        {
            "direction": direction,
            "mountain_present": False,
            "water_present": False,
            "observation_basis": "user_confirmed",
            "evidence": "逐宫独立确认外部山形、水形均不存在",
        }
        for direction in ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    ]
    result = assess(**inputs)
    interpretation = result["layout_analysis"]["natal_interpretation"]
    assert interpretation["status"] == "complete"
    assert interpretation["missing_inputs"] == []
    finding = interpretation["candidates"][0]["placement_findings"][0]
    assert finding["status"] == (
        "unsupported" if purpose == "desk" else "rule_not_covered_not_inauspicious"
    )
    progress = result["layout_analysis"]["analysis_progress"]
    assert progress["rule_coverage_status"] == "limited"
    assert progress["rule_coverage_counts"]["confirmed_unsupported"] >= 1
    assert progress["action_readiness"] == "not_evaluated"


def test_guidance_optional_path_can_extend_the_real_strict_mcp_first_view():
    spec = next(s for s in CATALOG if s.key == "fengshui_assess")
    guidance = call_guidance(spec)
    path = "layout_analysis.natal_interpretation"
    assert path in guidance["natal_interpretation"]
    fields = suggested_fields(spec)
    assert path not in fields

    async def call():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            result = await client.call_tool(
                "fengshui_assess",
                {
                    **assess_input(),
                    "fields": [*fields, path],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not result.is_error
            body = result.structured_content
            assert (
                body["layout_analysis"]["natal_interpretation"]["ruleset_id"]
                == "xuankong_conditioned_v1"
            )
            assert body["rulesets"] and body["rule_trace"]
            Draft202012Validator(FengshuiOutput.model_json_schema()).validate(body)

    asyncio.run(call())


def test_object_facing_never_supplies_its_missing_house_location():
    inputs = assess_input()
    inputs["placements"] = [
        {
            "object_id": "bed",
            "purpose": "bed",
            "facing_direction": "SW",
            "facing_role": "headboard",
        }
    ]
    result = assess(**inputs)["layers"]["xuankong_natal"]["interpretation"]
    findings = result["candidates"][0]["placement_findings"]
    assert len(findings) == 1 and findings[0]["object_id"] == "bed"
    assert findings[0]["status"] == "needs_location"


@pytest.mark.parametrize("purpose", ["desk", "stove"])
def test_uncovered_purposes_are_reported_without_borrowing_bed_or_door_rules(purpose):
    inputs = assess_input()
    inputs["placements"][0].update(object_id=purpose, purpose=purpose)
    result = assess(**inputs)["layers"]["xuankong_natal"]["interpretation"]
    findings = result["candidates"][0]["placement_findings"]
    assert findings[0]["status"] == "unsupported"


def test_jinsuo_and_indoor_facts_do_not_fill_missing_natal_external_forms():
    inputs = assess_input()
    inputs["xuankong"]["interpretation"]["external_forms"] = []
    plain = assess(**inputs)["layers"]["xuankong_natal"]["interpretation"]
    inputs["features"] = payload("jinsuo")["features"]
    inputs["form_observations"] = [
        {
            "object_id": "bed",
            "purpose": "bed",
            "solid_backing": True,
            "observation_basis": "user_confirmed",
            "evidence": "仅为床头室内实体依靠",
        }
    ]
    augmented = assess(**inputs)["layers"]["xuankong_natal"]["interpretation"]
    assert augmented == plain


def test_interpretation_rules_and_sources_are_resolvable_separately_from_chart():
    result = calculate_xuankong_natal(**natal_input())
    rules = {r["ruleset_id"]: r for r in result["rulesets"]}
    assert {"xuankong_zhongzhou_v1", "xuankong_conditioned_v1"} <= set(rules)
    authored = rules["xuankong_conditioned_v1"]
    sources = {s["source_id"] for s in authored["sources"]}
    assert sources == set(authored["source_ids"])
    assert authored["version"] and all(
        s["url"].startswith("https://") for s in authored["sources"]
    )
    interpretation = result["layers"]["xuankong_natal"]["interpretation"]
    for entry in interpretation["rule_trace"]:
        assert set(entry["source_ids"]) <= sources
    assert any(
        r["ruleset_id"] == "xuankong_conditioned_v1" for r in result["rule_trace"]
    )


def test_strict_nested_projection_matches_all_transports(monkeypatch, tmp_path, capsys):
    inputs = assess_input()
    fields = ["layers.xuankong_natal.interpretation", "rulesets", "rule_trace"]
    response = rest_client(monkeypatch).post(
        "/api/fengshui/assess",
        json=inputs,
        params={
            "fields": fields,
            "strict_fields": "true",
            "include_snapshot_text": "false",
        },
    )
    protocol = asyncio.run(
        mcp_call(
            "assess",
            {
                **inputs,
                "fields": fields,
                "strict_fields": True,
                "include_snapshot_text": False,
            },
        )
    )
    path = tmp_path / "projection.json"
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
    assert set(cli["layers"]["xuankong_natal"]) == {"interpretation"}
    Draft202012Validator(FengshuiOutput.model_json_schema()).validate(cli)


def test_bounded_interpretation_is_read_back_from_the_original_mcp_run(
    monkeypatch, tmp_path
):
    store = delivery.ResultStore(tmp_path / "results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)

    async def call_and_read():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            result = await client.call_tool(
                "fengshui_assess",
                {
                    **assess_input(),
                    "response_char_limit": 4096,
                    "include_snapshot_text": False,
                },
            )
            assert not result.is_error
            shaped = result.structured_content
            ref = shaped["result_delivery"]
            manifest = json.loads(
                (await client.read_resource(ref["manifest_uri"]))[0].text
            )
            assert manifest["run_metadata"] == shaped["run_metadata"]
            parts = []
            offset = 0
            while True:
                uri = f"fatebridge://results/{ref['result_id']}/pages/{offset}"
                page = json.loads((await client.read_resource(uri))[0].text)
                parts.append(page["text"])
                offset = page["next_offset"]
                if offset is None:
                    break
            raw = "".join(parts)
            assert hashlib.sha256(raw.encode()).hexdigest() == page["sha256"]
            full = json.loads(raw)
            assert full["run_metadata"] == shaped["run_metadata"]
            assert full["layers"]["xuankong_natal"]["interpretation"]
            return full

    asyncio.run(call_and_read())
