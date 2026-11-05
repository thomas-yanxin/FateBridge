"""General layout calculation regressions: dates, scopes, stars and alternatives."""

import asyncio
import json
from datetime import timedelta

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui.calendar import lichun
from fatebridge.core.fengshui.layout import element_relationships
from fatebridge.core.fengshui.models import AssessRequest, BazhaiRequest, MingguaRequest
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.services.fengshui import assess, calculate_bazhai, calculate_minggua
from fatebridge.services.tool_catalog import CATALOG
from tests.fengshui.test_fengshui_surfaces import (
    rest_client,
    same_run_projected_response,
    without_transport,
)
from tests.fixtures.fengshui import payload


def facing_only():
    return {
        "methods": ["bazhai"],
        "analyze_layout": True,
        "occupants": [
            {"subject_id": "a", "birth_date": "2000-12-10", "gender_convention": "male"}
        ],
        "placements": [
            {
                "object_id": "table",
                "purpose": "desk",
                "facing_direction": "W",
                "facing_role": "desk_facing",
                "subject_id": "a",
            }
        ],
    }


def test_nonboundary_date_needs_no_hour_and_preserves_minggua():
    actual = calculate_minggua(birth_date="2000-12-10", gender_convention="male")
    reference = calculate_minggua(effective_birth_year=2000, gender_convention="male")
    assert actual["status"] == "complete"
    assert (
        actual["layers"]["minggua"]["candidates"]
        == reference["layers"]["minggua"]["candidates"]
    )
    time = actual["layers"]["minggua"]["time_context"]
    assert time["input_basis"] == "civil_date_no_fabricated_birth_hour"
    assert "local_moment" not in time


@pytest.mark.parametrize(
    "element,generator,drain,controller,controlled",
    [
        ("木", "水", "火", "金", "土"),
        ("火", "木", "土", "水", "金"),
        ("土", "火", "金", "木", "水"),
        ("金", "土", "水", "火", "木"),
        ("水", "金", "木", "土", "火"),
    ],
)
def test_independent_five_element_relation_table(
    element, generator, drain, controller, controlled
):
    assert element_relationships(element) == {
        "same_element": element,
        "generating_element": generator,
        "draining_element": drain,
        "controlling_element": controller,
        "controlled_element": controlled,
    }


def test_boundary_date_keeps_uncertainty_and_timezone():
    for zone in ["Asia/Shanghai", "UTC", "America/New_York"]:
        day = lichun(2026, zone).date()
        for offset, year in [(-1, 2025), (1, 2026)]:
            actual = calculate_minggua(
                birth_date=(day + timedelta(days=offset)),
                gender_convention="male",
                timezone_name=zone,
            )
            assert actual["layers"]["minggua"]["time_context"]["effective_year"] == year
        actual = calculate_minggua(
            birth_date=day, gender_convention="male", timezone_name=zone
        )
        assert (
            actual["status"] == "partial"
            and actual["layers"]["minggua"]["candidates"] == []
        )
        assert actual["layers"]["minggua"]["missing_inputs"] == [
            "occupants.occupant.birth_at_on_year_boundary"
        ]
    civil = calculate_minggua(
        birth_date="2026-01-01", gender_convention="male", year_boundary="january_1"
    )
    assert civil["status"] == "complete"


def test_date_input_does_not_certify_boundary_when_term_is_approximate(monkeypatch):
    import fatebridge.core.fengshui.bazhai as core

    monkeypatch.setattr(
        core,
        "lichun_resolution",
        lambda *args: {
            "moment": "2026-02-04T04:03:00+08:00",
            "provider": "linear_fallback",
            "approximate": True,
        },
    )
    actual = calculate_minggua(birth_date="2026-02-03", gender_convention="male")
    personal = actual["layers"]["minggua"]
    assert personal["status"] == "partial" and personal["candidates"] == []
    assert personal["time_context"]["boundary_resolution"]["approximate"]
    assert (
        "confirmed_effective_birth_year_due_to_boundary_precision"
        in personal["missing_inputs"][0]
    )
    assert (
        calculate_minggua(effective_birth_year=2025, gender_convention="male")["status"]
        == "complete"
    )


@pytest.mark.parametrize(
    "extra",
    [
        {"birth_date": "2000-02-30"},
        {"birth_date": "1700-12-10"},
        {"birth_date": "2000-12-10", "effective_birth_year": 2000},
        {"birth_date": "2000-12-10", "birth_at": "2000-12-10T09:55:00+08:00"},
    ],
)
def test_birth_date_validation(extra):
    with pytest.raises(ValidationError):
        MingguaRequest.model_validate(extra)


def test_facing_only_is_computed_without_invented_location():
    actual = assess(**facing_only())
    assert actual["status"] == actual["layout_analysis"]["status"] == "partial"
    assert (
        "placements.table.location_direction"
        in actual["layout_analysis"]["missing_inputs"]
    )
    findings = actual["layout_analysis"]["placement_findings"]
    assert len(findings) == 1
    assert findings[0]["aspect"] == "facing" and findings[0]["star"]["name"] == "五鬼"
    options = actual["layout_analysis"]["adjustment_options"][0]
    assert options["agreed_matching_directions"] == ["N", "E", "SE", "S"]
    assert options["scopes"][0]["matches_convention"] is False
    elem = actual["layout_analysis"]["element_relationships"][0]
    assert (
        elem["star_element"],
        elem["draining_element"],
        elem["controlling_element"],
    ) == ("火", "土", "水")
    assert elem["application_scope"] == "element_relation_only_not_object_prescription"


def test_no_house_or_hour_is_required_to_return_existing_personal_finding():
    req = facing_only()
    req.pop("methods")
    req.pop("analyze_layout")
    actual = calculate_bazhai(**req)
    assert actual["layers"]["bazhai"]["placement_findings"][0]["direction"] == "W"
    assert actual["status"] == "partial"
    with pytest.raises(ValidationError):
        BazhaiRequest(placements=[{"object_id": "empty", "purpose": "desk"}])


def test_location_and_facing_options_obey_stove_rules_independently():
    req = payload("assess")
    req["analyze_layout"] = True
    actual = assess(**req)
    options = [
        o
        for o in actual["layout_analysis"]["adjustment_options"]
        if o["object_id"] == "stove"
    ]
    location, facing = options
    # 1990 male 坎: stove seat uses the four inauspicious sectors; fire mouth uses auspicious.
    personal_location = next(
        s for s in location["scopes"] if s["subject_kind"] == "occupant"
    )
    personal_facing = next(
        s for s in facing["scopes"] if s["subject_kind"] == "occupant"
    )
    assert personal_location["matching_directions"] == ["NE", "SW", "W", "NW"]
    assert personal_facing["matching_directions"] == ["N", "E", "SE", "S"]
    assert set(location["agreed_matching_directions"]).isdisjoint(
        facing["agreed_matching_directions"]
    )


def test_unknown_personal_convention_does_not_create_confirmed_consensus():
    req = facing_only()
    req["occupants"][0].pop("gender_convention")
    actual = assess(**req)["layout_analysis"]["adjustment_options"][0]
    assert len(actual["scopes"]) == 2
    assert all(s["candidate_only"] for s in actual["scopes"])
    assert actual["agreed_matching_directions"] == []
    assert actual["resolution"] == "no_confirmed_scope"


def test_house_and_person_disagreement_has_no_single_best_direction():
    req = facing_only()
    req["house"] = {"sitting_trigram": "乾"}
    actual = assess(**req)["layout_analysis"]["adjustment_options"][0]
    assert len(actual["scopes"]) == 2
    assert actual["agreed_matching_directions"] == []
    assert actual["resolution"] == "confirmed_scopes_intersection"
    assert {s["subject_kind"] for s in actual["scopes"]} == {"house", "occupant"}


@pytest.mark.parametrize(
    "purpose,role",
    [
        ("desk", "desk_facing"),
        ("bed", "headboard"),
        ("door", "door_facing"),
        ("stove", "fire_mouth"),
    ],
)
def test_annual_location_is_independent_of_facing_and_object_purpose(purpose, role):
    inputs = {
        "methods": ["annual_stars"],
        "effective_year": 2026,
        "analyze_layout": True,
        "placements": [
            {
                "object_id": "x",
                "purpose": purpose,
                "location_direction": "S",
                "facing_direction": "W",
                "facing_role": role,
            }
        ],
    }
    a = assess(**inputs)["layout_analysis"]
    inputs["placements"][0]["facing_direction"] = "E"
    b = assess(**inputs)["layout_analysis"]
    af = a["placement_findings"][0]
    assert af == b["placement_findings"][0]
    assert af["annual_star_number"] == 5 and af["direction"] == "S"
    assert af["aspect"] == "location"
    elements = a["element_relationships"][0]
    assert (
        elements["star_element"],
        elements["draining_element"],
        elements["controlling_element"],
    ) == ("土", "金", "木")


def test_no_location_does_not_project_facing_into_annual_palace():
    req = facing_only()
    req["methods"] = ["annual_stars"]
    req["effective_year"] = 2026
    actual = assess(**req)
    assert actual["status"] == "complete"  # requested raw annual chart is complete
    assert actual["layout_analysis"]["status"] == "partial"  # layout lookup is not
    assert actual["layout_analysis"]["placement_findings"] == []
    assert actual["layout_analysis"]["element_relationships"] == []


def test_natal_candidates_and_three_roles_are_not_collapsed():
    inputs = {
        "methods": ["xuankong_natal"],
        "analyze_layout": True,
        "xuankong": payload("xuankong_natal"),
        "placements": [
            {"object_id": "bed", "purpose": "bed", "location_direction": "E"}
        ],
    }
    inputs["xuankong"]["house"]["facing_degrees"] = 355.5
    actual = assess(**inputs)
    candidates = actual["layers"]["xuankong_natal"]["candidates"]
    findings = actual["layout_analysis"]["placement_findings"]
    assert len(findings) == len(candidates) > 1
    for c, f in zip(candidates, findings):
        assert f["candidate_id"] == c["candidate_id"] and f["candidate_only"]
        assert f["palace"] == c["palaces"]["E"]
    assert len(actual["layout_analysis"]["element_relationships"]) == 3 * len(
        candidates
    )
    assert {
        e["star_role"] for e in actual["layout_analysis"]["element_relationships"]
    } == {"period", "mountain", "facing"}


def test_unknown_sand_water_produces_no_adjustment_prescription():
    inputs = payload("assess")
    inputs["analyze_layout"] = True
    inputs["features"][0]["classification"] = "unknown"
    actual = assess(**inputs)["layout_analysis"]["environment_adjustments"]
    assert actual[0]["adjustment"] == "needs_confirmed_classification"
    assert actual[0]["target_classification"] is None
    inputs["features"][0]["classification"] = "sand"
    actual = assess(**inputs)["layout_analysis"]["environment_adjustments"]
    assert actual[0]["target_classification"] == "water"
    assert (
        actual[0]["application_scope"]
        == "confirmed_environment_classification_not_small_object_substitution"
    )


def test_opt_in_analysis_preserves_existing_calculation_values():
    inputs = payload("assess")
    base = assess(**inputs)
    extended = assess(**{**inputs, "analyze_layout": True})
    assert extended["layers"] == base["layers"]
    assert extended["conflicts"] == base["conflicts"]
    assert "layout_analysis" not in base
    FengshuiOutput.model_validate(extended)
    assert "布局计算" in extended["snapshot_text"]


@pytest.mark.parametrize(
    "inputs",
    [
        facing_only(),
        {**payload("assess"), "analyze_layout": True},
        {"methods": ["annual_stars"], "effective_year": 2026, "analyze_layout": True},
    ],
)
def test_extended_layout_matches_rest_mcp_cli(monkeypatch, tmp_path, capsys, inputs):
    from fatebridge.mcp_server import create_mcp_app

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_assess",
                {"response_char_limit": 0, **inputs},
                raise_on_error=False,
            )

    rest = rest_client(monkeypatch).post("/api/fengshui/assess", json=inputs)
    mcp = asyncio.run(call())
    request = tmp_path / "layout.json"
    request.write_text(json.dumps(inputs))
    assert run(["fengshui_assess", "--request-file", str(request)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200 and not mcp.is_error
    assert (
        without_transport(rest.json())
        == without_transport(mcp.structured_content)
        == without_transport(cli)
    )
    schema = FengshuiOutput.model_json_schema()
    for result in [rest.json(), mcp.structured_content, cli]:
        Draft202012Validator(schema).validate(result)


def test_strict_projected_analysis_works_on_real_mcp():
    from fatebridge.mcp_server import create_mcp_app

    async def call():
        async with Client(create_mcp_app()) as client:
            response = await client.call_tool(
                "fengshui_assess",
                {
                    **facing_only(),
                    "fields": [
                        "layout_analysis.adjustment_options",
                        "layout_analysis.status",
                        "layout_analysis.unsupported_queries",
                    ],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            return await same_run_projected_response(client, response)

    result = asyncio.run(call())
    assert set(result) == {"layout_analysis", "run_metadata"}
    assert set(result["layout_analysis"]) == {
        "adjustment_options",
        "status",
        "unsupported_queries",
    }
    assert result["run_metadata"]["tool_name"] == "fengshui_assess"


def test_layout_uses_existing_tools_no_special_workspace_entry():
    names = {s.key for s in CATALOG if s.family == "fengshui"}
    assert names == {
        "fengshui_directions",
        "fengshui_minggua",
        "fengshui_bazhai",
        "fengshui_jinsuo",
        "fengshui_annual_stars",
        "fengshui_monthly_stars",
        "fengshui_xuankong_natal",
        "fengshui_assess",
    }
    assert "analyze_layout" in AssessRequest.model_fields
