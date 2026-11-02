"""Every BaZi surface publishes literal hidden targets and source conditions."""

import asyncio

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.core.hidden_carriers import (
    describe_hidden_targets,
    hidden_carrier_snapshot_lines,
)
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.test_bazi_timing_transports import INPUT as TIMING_INPUT
from tests.test_bazi_year_contract import TOPICS

INPUT = {
    "name": "虚构藏干盖头验证",
    "gender": "男",
    "birth_year": 1980,
    "birth_month": 1,
    "birth_day": 14,
    "birth_hour": 20,
    "birth_minute": 0,
    "birth_timezone": "Asia/Shanghai",
    "use_true_solar_time": False,
}


def walk(value, path):
    for k in path.split("."):
        value = value[k]
    return value


@pytest.mark.parametrize(
    "name,view",
    [("bazi_" + t, "hidden_carriers") for t in TOPICS]
    + [("analyze_destiny", "hidden_carriers"), ("timing_analysis", "hidden_carriers")]
    + [("bazi_" + t, "hidden_carriers_timing") for t in TOPICS if t != "birth"],
)
def test_published_hidden_target_view_on_available_protocols(
    name, view, rest, tmp_path, capsys
):
    spec = SPECS[name]
    fields = suggested_fields(spec, view=view)
    payload = TIMING_INPUT if name == "timing_analysis" else INPUT
    controls = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
        "as_of": AS_OF,
    }
    rest_fields = fields if spec.rest_path else ["bazi_birth." + f for f in fields]
    response = rest.post(
        spec.rest_path or SPECS["bazi_birth"].rest_path,
        json=payload,
        params={**controls, "fields": rest_fields},
    )
    protocol = asyncio.run(native(spec, payload, **controls))
    code, cli = call_cli(
        spec,
        payload,
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
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    comparable = business(response.json())
    if not spec.rest_path:
        comparable = comparable["bazi_birth"]
    assert comparable == business(protocol.structured_content) == business(cli)
    if view == "hidden_carriers_timing":
        value = walk(
            comparable, next(f for f in fields if f.endswith(".hidden_target_carriers"))
        )
        reference = walk(comparable, fields[-1])
    else:
        value = walk(comparable, fields[0])
        reference = comparable.get("interaction_analysis", {}).get(
            "hidden_target_reference"
        )
    if name == "timing_analysis" or view == "hidden_carriers_timing":
        if name == "timing_analysis":
            value = comparable["interaction_analysis"]["hidden_target_carriers"]
        assert len(value) == (5 if name == "timing_analysis" else 2)
        principal = walk(
            comparable, next(f for f in fields if f.endswith(".pillar_carriers"))
        )
        principal_by_id = {r["node_id"]: r for r in principal}
        assert {r["node_id"] for r in value} == set(principal_by_id)
        for row in value:
            # Common metadata and the existing pillar reconstruct every fact.
            assert {
                **reference,
                "pillar": row["pillar"],
                "targets": row["targets"],
            } == describe_hidden_targets(*row["pillar"])
            assert principal_by_id[row["node_id"]]["pillar"] == row["pillar"]
            assert (
                principal_by_id[row["node_id"]]["effective_force_status"]
                == "not_adjudicated"
            )
    else:
        month = value["pillars"][1]
        assert month["pillar"] == "丁丑"
        assert [
            r["hidden_stem"]
            for r in month["targets"]
            if r["covering_candidate_if_target_desired"]
        ] == ["辛"]
        assert month["targets"][-1]["ten_god"] == "正财"
        assert value["source"]["pdf_pages"] == [391]


def test_snapshot_uses_same_receipt_and_full_cover_claim_is_rejected(rest):
    spec = SPECS["bazi_birth"]
    response = rest.post(spec.rest_path, json=INPUT, params={"response_char_limit": 0})
    assert response.status_code == 200
    result = response.json()
    receipt = result["bazi_birth"]["structure_profile"]["evidence_chain"][
        "natal_hidden_carriers"
    ]
    for line in hidden_carrier_snapshot_lines(receipt):
        assert line in result["snapshot_text"]
    run = result["run_metadata"]
    claim = CalculationClaim(
        path="bazi_birth.structure_profile.evidence_chain.natal_hidden_carriers.pillars.1.targets.0.covering_candidate_if_target_desired",
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
