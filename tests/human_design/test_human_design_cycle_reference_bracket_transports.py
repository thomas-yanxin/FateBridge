"""The actual reference/contact comparison is shared across three surfaces."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading

SPEC = next(s for s in CATALOG if s.key == "human_design")


@pytest.mark.parametrize("empty_files", [False, True])
def test_exact_reference_basis_and_complete_result_agree_in_rest_mcp_cli(
    monkeypatch, tmp_path, capsys, empty_files
):
    if empty_files:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    else:
        from pathlib import Path

        monkeypatch.setenv(
            "SE_EPHE_PATH", str(Path(__file__).resolve().parents[2] / "ephe")
        )
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    params = dict(
        birth_year=1980,
        birth_month=1,
        birth_day=1,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
        cycle_reference_datetime="2009-10-03T20:31:21.470265+00:00",
    )
    with TestClient(api.app) as client:
        reply = client.post(SPEC.rest_path, json=params)
    assert reply.status_code == 200, reply.text
    expected = reply.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)
    context = expected["cycle_context"]
    assert context["ruleset"]["version"] == "1.6.0"
    assert context["status"] == ("partial" if empty_files else "computed_finite_search")
    if not empty_files:
        assert (
            expected["cycle_summary"]["bodies"][0]["reference_relation"]
            == "before_first_observed_contact"
        )

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            full = await client.call_tool(
                "human_design", {**params, "response_char_limit": 0}
            )
            assert not full.is_error
            card = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": evidence_views(SPEC)["cycles"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not card.is_error
            assert (
                card.structured_content["cycle_summary"]["reference_contact_ordering"]
                == expected["cycle_summary"]["reference_contact_ordering"]
            )
            return full.structured_content

    mcp = asyncio.run(call())
    flags = ["human_design"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for payload in (expected, mcp, cli):
        proof = verify_human_design_reading(payload)
        assert proof["status"] == "verified_fixed_template_reading", proof
        identity = proof["native_execution_policy"]
        assert identity["matches_current_declared_policy"] is True
        assert identity["historical_declared_policy_verified"] is False
        assert (
            payload["cycle_summary"]["reference_contact_ordering"][
                "physical_accuracy_certified"
            ]
            is False
        )
        payload.pop("run_metadata")
    assert expected == mcp == cli
