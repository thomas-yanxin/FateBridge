"""Fixing roles, mechanism prose and compact summary on actual protocols."""

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
INPUT = dict(
    birth_year=1971,
    birth_month=1,
    birth_day=1,
    birth_hour=12,
    birth_minute=0,
    birth_timezone="UTC",
)


@pytest.mark.parametrize("empty_files", [False, True])
def test_all_26_fixing_mechanisms_and_node_recipients_match_three_surfaces(
    monkeypatch, tmp_path, capsys, empty_files
):
    if empty_files:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as rest:
        response = rest.post(SPEC.rest_path, json=INPUT)
    assert response.status_code == 200, response.text
    expected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", {**INPUT, "response_char_limit": 0}
            )
            assert not result.is_error
            card = await client.call_tool(
                "human_design",
                {
                    **INPUT,
                    "fields": evidence_views(SPEC)["fixing"]["fields"],
                    "strict_fields": True,
                    "response_char_limit": 0,
                    "include_snapshot_text": False,
                },
            )
            assert not card.is_error
            assert (
                card.structured_content["depth_evidence"]["fixing_summary"]
                == expected["depth_evidence"]["fixing_summary"]
            )
            assert (
                card.structured_content["interpretation"]["line_fixing_meaning"]
                == expected["interpretation"]["line_fixing_meaning"]
            )
            assert "line_fixings" not in card.structured_content["depth_evidence"]
            return result.structured_content

    native = asyncio.run(call())
    flags = ["human_design"]
    for key, value in INPUT.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for value in (expected, native, cli):
        check = verify_human_design_reading(value)
        assert check["status"] == "verified_fixed_template_reading", check
        assert check["checked_fixing_reading_count"] == 26
        nodes = [
            r
            for r in value["depth_evidence"]["line_fixings"]
            if r["recipient_kind"] == "node_activation"
        ]
        assert len(nodes) == 4
        assert all(r["fixing_state"] != "node_activation_not_assessed" for r in nodes)
        assert any(r["fixing_state"] == "detriment" for r in nodes)
        value.pop("run_metadata")
    assert expected == native == cli
