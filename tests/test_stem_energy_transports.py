"""Same applied arithmetic and faithful text across the three public transports."""

import asyncio
import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import evidence_views
from fatebridge.core.output_stem_energy import StemEnergyAccounting, StemEnergyRow
from fatebridge.core.stem_effects import stem_energy_snapshot_lines
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.mcp_receipt import verified_inline_business
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

PAYLOAD = {
    "name": "虚构天干完整精度回归",
    "birth_year": 1973,
    "birth_month": 6,
    "birth_day": 20,
    "birth_hour": 8,
    "birth_minute": 0,
    "birth_timezone": "Asia/Shanghai",
    "use_true_solar_time": False,
    "gender": "男",
    "analysis_year": 2026,
    "analysis_month": 10,
    "analysis_day": 22,
}


def test_same_run_stem_energy_receipt_text_and_claims_across_transports(
    rest, tmp_path, capsys
):
    spec = SPECS["bazi_birth"]
    response = rest.post(
        spec.rest_path, json=PAYLOAD, params={"response_char_limit": 0}
    )
    code, local = call_cli(
        spec, PAYLOAD, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, PAYLOAD))
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    result = response.json()
    assert business(result) == business(local) == business(protocol.structured_content)
    birth = result["bazi_birth"]
    assessment = birth["day_master"]["assessment"]
    receipt = assessment["stem_energy_accounting"]
    assert (
        receipt
        == birth["structure_profile"]["evidence_chain"]["strength_context"][
            "stem_energy_accounting"
        ]
    )
    assert birth["four_pillars"]["year"] == {"stem": "癸", "branch": "丑"}
    assert birth["four_pillars"]["month"] == {"stem": "戊", "branch": "午"}
    StemEnergyAccounting.model_validate(receipt)
    for line in stem_energy_snapshot_lines(assessment):
        assert line in result["snapshot_text"]
    run = result["run_metadata"]
    path = "bazi_birth.structure_profile.evidence_chain.strength_context.stem_energy_accounting.ledger.0.energy"
    claim = CalculationClaim(
        path=path,
        value=receipt["ledger"][0]["energy"],
        run_id=run["run_id"],
        business_output_sha256=run["business_output_sha256"],
    )
    assert (
        verify_calculation_claims(result, [claim])["status"]
        == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(result, [claim.model_copy(update={"value": 100})])[
            "status"
        ]
        == "rejected"
    )
    malformed = deepcopy(receipt)
    malformed["ledger"][0]["energy"] = 100
    with pytest.raises(ValidationError, match="未舍入"):
        StemEnergyAccounting.model_validate(malformed)


@pytest.mark.parametrize(
    "topic",
    [
        "birth",
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
def test_published_compact_view_and_partial_contract(topic, rest):
    spec = SPECS["bazi_" + topic]
    fields = evidence_views(spec)["stem_energy"]["fields"]
    from fastmcp import Client

    from fatebridge.mcp_server import create_mcp_app

    async def call_and_read():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                spec.tool_name,
                {
                    **PAYLOAD,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 8192,
                },
            )
            assert not result.is_error
            assert len(result.content[0].text) <= 8192
            return await verified_inline_business(client, result.structured_content)

    body = asyncio.run(call_and_read())
    assert "stem_energy_accounting" in json.dumps(body, ensure_ascii=False)
    assert "result_delivery" not in body
    chain = (
        body["bazi_birth"]["structure_profile"]["evidence_chain"]
        if topic == "birth"
        else body[topic + "_analysis"]["evidence_chain"]
    )
    context = chain["strength_context"]
    assert context["method_id"] == "season_root_revelation_relations_v10"
    StemEnergyAccounting.model_validate(context["stem_energy_accounting"])
    StemEnergyRow.model_validate({"energy": 0.1})  # legal object projection
    with pytest.raises(ValidationError):
        StemEnergyRow.model_validate({"pillar": "day"})
    with pytest.raises(ValidationError, match="原字五行"):
        StemEnergyRow.model_validate({"physical_stem": "癸", "physical_element": "火"})
