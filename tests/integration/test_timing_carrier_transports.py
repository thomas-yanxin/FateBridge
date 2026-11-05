"""Real three-transport receipts and same-run explanations for timing carriers."""

import asyncio
import json

import pytest
from fastmcp import Client

import fatebridge.mcp_server as mcp
from fatebridge.application.examples import evidence_views
from fatebridge.core.timing_carriers import timing_carrier_snapshot_lines
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.bazi.test_bazi_timing_transports import INPUT
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.support.mcp_result_assertions import same_run_projected_response


async def carrier_view(spec, payload, fields):
    async with Client(mcp.app) as client:
        result = await client.call_tool(
            spec.tool_name,
            {
                **payload,
                "as_of": AS_OF,
                "fields": fields,
                "strict_fields": True,
                "include_snapshot_text": False,
                "response_char_limit": 8192,
            },
            raise_on_error=False,
        )
        await same_run_projected_response(client, result)
        return result


def test_same_calculated_carrier_and_text_on_rest_mcp_cli(rest, tmp_path, capsys):
    spec = SPECS["timing_analysis"]
    response = rest.post(spec.rest_path, json=INPUT, params={"response_char_limit": 0})
    code, local = call_cli(
        spec, INPUT, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, INPUT))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    result = response.json()
    assert business(result) == business(local) == business(protocol.structured_content)
    interactions = result["interaction_analysis"]
    carrier = interactions["pillar_carriers"][0]
    assert carrier["node_id"] == "timing.dayun" and carrier["pillar"] == "乙酉"
    assert carrier["principal_relation"] == "branch_overcomes_stem"
    assert carrier["own_hidden_root_present"] is False
    assert carrier["external_natal_roots"]
    for line in timing_carrier_snapshot_lines(interactions):
        assert line in result["snapshot_text"]
    run = result["run_metadata"]
    claim = CalculationClaim(
        path="interaction_analysis.pillar_carriers.0.own_hidden_root_present",
        value=False,
        run_id=run["run_id"],
        business_output_sha256=run["business_output_sha256"],
    )
    assert (
        verify_calculation_claims(result, [claim])["status"]
        == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(result, [claim.model_copy(update={"value": True})])[
            "status"
        ]
        == "rejected"
    )


def test_compact_published_carrier_view_and_no_array_descent(rest):
    spec = SPECS["timing_analysis"]
    fields = evidence_views(spec)["carriers"]["fields"]
    protocol = asyncio.run(carrier_view(spec, INPUT, fields))
    assert not protocol.is_error
    output = protocol.structured_content
    assert len(json.dumps(output, ensure_ascii=False, separators=(",", ":"))) <= 8192
    assert len(output["interaction_analysis"]["pillar_carrier_summary"]) == 5
    result = rest.post(
        spec.rest_path,
        json=INPUT,
        params={
            "fields": ["interaction_analysis.pillar_carriers.own_hidden_root_present"],
            "strict_fields": True,
        },
    )
    assert result.status_code == 422
    assert result.json()["issues"][0]["code"] == "non_object_projection_path"


@pytest.mark.parametrize(
    "topic",
    [
        "career",
        "wealth",
        "health",
        "children",
        "education",
        "personality",
        "relatives",
        "marriage",
        "romance",
    ],
)
def test_same_carrier_facts_in_all_nine_topic_views(topic):
    spec = SPECS["bazi_" + topic]
    payload = {k: v for k, v in INPUT.items() if k != "analysis_hour"}
    fields = evidence_views(spec)["carriers"]["fields"]
    result = asyncio.run(carrier_view(spec, payload, fields))
    assert not result.is_error
    body = result.structured_content
    facts = body[topic + "_analysis"]["evidence_chain"]["topic"]["timing"]
    assert len(facts["pillar_carriers"]) == 2
    dayun = facts["pillar_carriers"][0]
    assert dayun["pillar"] == "乙酉" and not dayun["own_hidden_root_present"]
    assert dayun["external_natal_roots"]
    assert dayun["source_ref"] == facts["carrier_source"]["id"]


def test_unknown_direction_input_does_not_invent_dayun_carrier():
    spec = SPECS["bazi_career"]
    payload = {k: v for k, v in INPUT.items() if k != "analysis_hour"}
    payload["gender"] = None
    result = asyncio.run(
        carrier_view(
            spec,
            payload,
            evidence_views(spec)["carriers"]["fields"],
        )
    )
    assert not result.is_error
    rows = result.structured_content["career_analysis"]["evidence_chain"]["topic"][
        "timing"
    ]["pillar_carriers"]
    assert len(rows) == 1 and rows[0]["node_id"] == "timing.liunian"
