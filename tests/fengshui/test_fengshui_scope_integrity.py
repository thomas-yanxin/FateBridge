"""Selected-method boundaries and readiness across independent object types."""

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
from tests.support.mcp_result_assertions import (
    same_run_projected_response,
    without_transport,
)
from tests.support.transports import rest_client

PURPOSE_ROLES = [
    ("door", "door_facing"),
    ("bed", "headboard"),
    ("desk", "desk_facing"),
    ("stove", "fire_mouth"),
]


def facing_placement(purpose="desk", role="desk_facing"):
    return {
        "object_id": "item",
        "purpose": purpose,
        "facing_direction": "W",
        "facing_role": role,
    }


@pytest.mark.parametrize("purpose,role", PURPOSE_ROLES)
@pytest.mark.parametrize("method", ["annual_stars", "xuankong_natal", "jinsuo"])
def test_non_bazhai_methods_never_claim_direction_adjustments(method, purpose, role):
    inputs = {
        "methods": [method],
        "analyze_layout": True,
        "placements": [facing_placement(purpose, role)],
        "effective_year": 2026,
        "features": payload("assess")["features"],
    }
    if method == "xuankong_natal":
        inputs["xuankong"] = payload("xuankong_natal")
    actual = assess(**inputs)
    layout = actual["layout_analysis"]
    assert layout["adjustment_options"] == []
    assert "共同匹配方位" not in actual["snapshot_text"]
    missing_location = "placements.item.location_direction"
    if method == "jinsuo":
        assert missing_location not in layout["missing_inputs"]
        assert layout["status"] == "complete"
        assert layout["environment_adjustments"]
    else:
        assert missing_location in layout["missing_inputs"]
        assert layout["status"] == "partial"
        assert layout["placement_findings"] == []


def test_form_only_does_not_require_unused_compass_location():
    actual = assess(
        methods=[],
        placements=[facing_placement()],
        form_observations=[
            {
                "object_id": "item",
                "purpose": "desk",
                "entrance_visible": True,
                "entrance_direct_line": False,
                "solid_backing": True,
                "observation_basis": "user_confirmed",
                "evidence": "使用位置形态已确认，未测全宅方位",
            }
        ],
    )
    assert actual["status"] == actual["layout_analysis"]["status"] == "complete"
    assert actual["layout_analysis"]["missing_inputs"] == []
    assert actual["layout_analysis"]["adjustment_options"] == []
    ruleset = actual["rulesets"][0]
    assert "床桌灶" in ruleset["scope"] and "门床桌灶" not in ruleset["scope"]


@pytest.mark.parametrize("purpose", ["door", "sofa"])
def test_unsupported_form_purposes_are_not_relabelled_as_supported(purpose):
    with pytest.raises(ValidationError):
        AssessRequest.model_validate(
            {
                "methods": [],
                "form_observations": [
                    {
                        "object_id": "item",
                        "purpose": purpose,
                        "entrance_visible": True,
                        "observation_basis": "user_confirmed",
                        "evidence": "用户明确对象用途",
                    }
                ],
            }
        )


@pytest.mark.parametrize("purpose,role", PURPOSE_ROLES)
def test_coverage_preserves_raw_status_and_reports_requested_readiness(purpose, role):
    actual = assess(
        methods=["annual_stars"],
        effective_year=2026,
        analyze_layout=True,
        placements=[facing_placement(purpose, role)],
    )
    coverage = actual["coverage"]
    assert actual["status"] == "complete"  # raw annual chart remains available
    assert coverage["missing_inputs"] == []
    assert (
        coverage["requested_analysis_status"] == coverage["layout_status"] == "partial"
    )
    assert coverage["layout_missing_inputs"] == ["placements.item.location_direction"]
    assert "layout: partial" in actual["summary"]
    assert "布局缺失输入：placements.item.location_direction" in actual["snapshot_text"]


def test_unsupported_authored_year_is_incomplete_even_without_missing_inputs():
    actual = assess(
        methods=["annual_stars"],
        effective_year=2027,
        annual_remedy_ruleset_id="pang_2026_annual_v1",
        placements=[{"object_id": "item", "purpose": "bed", "location_direction": "S"}],
    )
    assert actual["coverage"]["missing_inputs"] == []
    assert actual["coverage"]["layout_missing_inputs"] == []
    assert actual["coverage"]["requested_analysis_status"] == "partial"


def test_cross_scope_effects_retain_identity_of_gender_candidates():
    actual = assess(
        methods=["bazhai", "annual_stars"],
        effective_year=2026,
        annual_remedy_ruleset_id="pang_2026_annual_v1",
        occupants=[{"subject_id": "person", "effective_birth_year": 2000}],
        placements=[
            {"object_id": "item", "purpose": "desk", "location_direction": "S"}
        ],
    )
    effects = actual["layout_analysis"]["annual_remedies"]["findings"][0][
        "cross_scope_effects"
    ]
    personal = [e for e in effects if e["method"] == "bazhai"]
    assert {e["gender_convention"] for e in personal} == {"male", "female"}
    assert all(
        e["candidate_only"]
        and e["subject_kind"] == "occupant"
        and e["subject_id"] == "person"
        and e["direction"] == "S"
        for e in personal
    )


def test_unknown_scope_snapshot_does_not_claim_no_matching_direction():
    actual = assess(
        methods=["bazhai"],
        analyze_layout=True,
        occupants=[{"subject_id": "person", "effective_birth_year": 2000}],
        placements=[facing_placement()],
    )
    assert "尚无已确认作用域" in actual["snapshot_text"]
    assert "已确认作用域之间没有共同匹配方位" not in actual["snapshot_text"]


def test_projected_readiness_is_identical_on_rest_mcp_cli(
    monkeypatch, tmp_path, capsys
):
    from fatebridge.mcp_server import create_mcp_app

    inputs = {
        "methods": ["annual_stars"],
        "effective_year": 2026,
        "analyze_layout": True,
        "placements": [facing_placement()],
    }
    controls = {
        "fields": ["status", "coverage", "summary"],
        "strict_fields": True,
        "include_snapshot_text": False,
    }

    async def call():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "fengshui_assess", {**inputs, **controls}, raise_on_error=False
            )
            return result, await same_run_projected_response(client, result)

    rest = rest_client(monkeypatch).post(
        "/api/fengshui/assess",
        params=controls,
        json=inputs,
    )
    mcp, mcp_body = asyncio.run(call())
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(inputs))
    assert (
        run(
            [
                "fengshui_assess",
                "--request-file",
                str(path),
                "--fields",
                "status",
                "coverage",
                "summary",
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
        == without_transport(mcp_body)
        == without_transport(cli)
    )
    for result in [rest.json(), mcp.structured_content, mcp_body, cli]:
        Draft202012Validator(FengshuiOutput.model_json_schema()).validate(result)
        assert result["coverage"]["requested_analysis_status"] == "partial"
        assert result["coverage"]["layout_missing_inputs"] == [
            "placements.item.location_direction"
        ]
