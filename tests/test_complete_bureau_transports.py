"""Repeated-bureau and surviving-root receipts agree across public transports."""

import asyncio
import json

from fatebridge.application.examples import suggested_fields
from fatebridge.core.complete_bureaus import complete_bureau_snapshot_lines
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.mcp_receipt import verified_inline_business
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

PAYLOAD = {
    "name": "虚构同局重支回归",
    "birth_year": 2001,
    "birth_month": 10,
    "birth_day": 1,
    "birth_hour": 1,
    "birth_minute": 0,
    "birth_timezone": "Asia/Shanghai",
    "use_true_solar_time": False,
    "gender": "男",
    "analysis_year": 2026,
    "analysis_month": 10,
    "analysis_day": 12,
}


def test_full_bureau_roots_and_text_are_same_run_facts_on_rest_native_mcp_cli(
    rest, tmp_path, capsys
):
    # A fictional civil fixture yielding the exposed source pillars; it does
    # not reconstruct that historical person's birth date or validate calendars.
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
    b = result["bazi_birth"]
    assert [r["stem"] + r["branch"] for r in b["four_pillars"].values()] == [
        "辛巳",
        "丁酉",
        "丁酉",
        "辛丑",
    ]
    a = b["day_master"]["assessment"]
    assert a["method_id"] == "season_root_revelation_relations_v10"
    (event,) = [e for e in a["relations"] if e["kind"] == "三合"]
    assert event["positions"] == ["year", "month", "day", "hour"]
    assert event["status"] == "conditioned_transformation"
    assert not a["root_qualifications"][0]["qualified_for_structural_rule"]
    for line in complete_bureau_snapshot_lines(a):
        assert line in result["snapshot_text"]
    components = b["structure_profile"]["evidence_chain"]["force_components"][
        "components"
    ]
    assert sorted(
        (row for c in components.values() for row in c["remaining_hidden_roots"]),
        key=lambda r: (r["pillar"], r["stem"]),
    ) == sorted(a["hidden_stem_ledger"], key=lambda r: (r["pillar"], r["stem"]))
    metadata = result["run_metadata"]
    claim = CalculationClaim(
        path="bazi_birth.day_master.assessment.hidden_stem_ledger.0.remaining_mass",
        value=a["hidden_stem_ledger"][0]["remaining_mass"],
        run_id=metadata["run_id"],
        business_output_sha256=metadata["business_output_sha256"],
    )
    assert (
        verify_calculation_claims(result, [claim])["status"]
        == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(result, [claim.model_copy(update={"value": 2.0})])[
            "status"
        ]
        == "rejected"
    )


def test_published_surviving_roots_view_retains_original_and_remaining_mass(rest):
    spec = SPECS["bazi_birth"]
    response = rest.post(
        spec.rest_path,
        json=PAYLOAD,
        params={
            "fields": suggested_fields(spec, view="surviving_roots"),
            "strict_fields": "true",
            "include_snapshot_text": "false",
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200, response.text
    a = response.json()["bazi_birth"]["day_master"]["assessment"]
    assert (
        a["hidden_stem_ledger"][0]["remaining_mass"]
        < a["hidden_stem_ledger"][0]["initial_mass"]
    )
    assert a["root_activation_policy"] == "remaining_physical_hidden_stems_only_v1"


def test_published_roots_view_fits_default_native_mcp_delivery_budget():
    result = asyncio.run(
        native(
            SPECS["bazi_birth"],
            PAYLOAD,
            fields=suggested_fields(SPECS["bazi_birth"], view="surviving_roots"),
            strict_fields=True,
            include_snapshot_text=False,
            response_char_limit=8192,
        )
    )
    assert not result.is_error
    output = result.structured_content

    async def check_receipt():
        from fastmcp import Client

        from fatebridge.mcp_server import create_mcp_app

        async with Client(create_mcp_app()) as client:
            return await verified_inline_business(client, output)

    restored = asyncio.run(check_receipt())
    assert restored["bazi_birth"] == output["bazi_birth"]
    assert len(json.dumps(output, ensure_ascii=False, separators=(",", ":"))) <= 8192
    assert output["bazi_birth"]["day_master"]["assessment"]["hidden_stem_ledger"]
