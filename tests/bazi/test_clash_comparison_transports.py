"""The same clash proxy and limits reach every published BaZi surface."""

import asyncio

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.core.clash_comparison import clash_comparison_snapshot_lines
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.bazi.test_bazi_year_contract import TOPICS
from tests.support.transports import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
    surface_calls,
)

PAYLOAD = {
    "name": "虚构冲力回执验证",
    "gender": "男",
    "birth_year": 1992,
    "birth_month": 2,
    "birth_day": 6,
    "birth_hour": 10,
    "birth_minute": 30,
    "birth_timezone": "Asia/Shanghai",
    "use_true_solar_time": False,
}


def walk(result, path):
    for part in path.split("."):
        result = result[part]
    return result


@pytest.mark.parametrize("topic", TOPICS)
def test_clash_reasoning_view_matches_rest_native_mcp_cli(topic, surface_calls):
    spec = SPECS["bazi_" + topic]
    fields = suggested_fields(spec, view="clash_reasoning")
    opts = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    response, protocol, code, cli = surface_calls(
        spec,
        PAYLOAD,
        params=opts,
        options=opts,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
        cli_first=False,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(protocol.structured_content)
        == business(cli)
    )
    receipt = walk(response.json(), fields[-1])
    assert receipt["method_id"] == "initial_hidden_budget_clash_trace_v1"
    assert any(
        e["calculation_branch"] == "initial_hidden_budget" for e in receipt["events"]
    )
    assert receipt["classical_effective_force"] == "not_adjudicated"
    assert "visible_stem_activation" in receipt["not_included_factors"]


def test_full_snapshot_same_run_claims_and_invalid_array_projection(rest):
    spec = SPECS["bazi_birth"]
    response = rest.post(
        spec.rest_path, json=PAYLOAD, params={"response_char_limit": 0}
    )
    assert response.status_code == 200
    result = response.json()
    a = result["bazi_birth"]["day_master"]["assessment"]
    for line in clash_comparison_snapshot_lines(a):
        assert line in result["snapshot_text"]
    meta = result["run_metadata"]
    claim = CalculationClaim(
        path="bazi_birth.structure_profile.evidence_chain.strength_context.clash_comparison.events.0.powers.0.raw_budget",
        value=a["clash_comparison"]["events"][0]["powers"][0]["raw_budget"],
        run_id=meta["run_id"],
    )
    assert (
        verify_calculation_claims(result, [claim])["status"]
        == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(result, [claim.model_copy(update={"value": 999})])[
            "status"
        ]
        == "rejected"
    )
    invalid = rest.post(
        spec.rest_path,
        json=PAYLOAD,
        params={
            "fields": [
                "bazi_birth.structure_profile.evidence_chain.strength_context.clash_comparison.events.powers"
            ],
            "strict_fields": True,
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["issues"][0]["code"] == "non_object_projection_path"


def test_root_alias_keeps_the_identical_receipt_on_native_mcp_and_cli(tmp_path, capsys):
    spec = SPECS["analyze_destiny"]
    fields = suggested_fields(spec, view="clash_reasoning")
    protocol = asyncio.run(
        native(
            spec,
            PAYLOAD,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    code, cli = call_cli(
        spec,
        PAYLOAD,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert not protocol.is_error and code == 0
    assert business(protocol.structured_content) == business(cli)
    assert walk(cli, fields[-1])["method_id"] == "initial_hidden_budget_clash_trace_v1"
