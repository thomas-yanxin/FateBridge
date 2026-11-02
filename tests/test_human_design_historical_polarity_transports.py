"""The conditional source comparison survives actual REST, MCP and CLI."""

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
@pytest.mark.parametrize("day,hour,minute", [(29, 19, 57), (30, 6, 59)])
def test_both_original_sun58_cases_match_all_three_surfaces(
    monkeypatch, tmp_path, capsys, empty_files, day, hour, minute
):
    if empty_files:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    params = dict(
        birth_year=1981,
        birth_month=12,
        birth_day=day,
        birth_hour=hour,
        birth_minute=minute,
        birth_timezone="Europe/London",
    )
    with TestClient(api.app) as rest:
        response = rest.post(SPEC.rest_path, json=params)
    assert response.status_code == 200, response.text
    expected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", {**params, "response_char_limit": 0}
            )
            assert not result.is_error
            card = await client.call_tool(
                "human_design",
                {
                    **params,
                    "fields": evidence_views(SPEC)["historical_polarity"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not card.is_error
            assert (
                card.structured_content["historical_polarity_context"]
                == expected["historical_polarity_context"]
            )
            assert (
                card.structured_content["interpretation"]["historical_polarity_context"]
                == expected["interpretation"]["historical_polarity_context"]
            )
            return result.structured_content

    native = asyncio.run(call())
    flags = ["human_design"]
    for k, v in params.items():
        flags.extend(["--" + k.replace("_", "-"), str(v)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        report = result["historical_polarity_context"]
        assert (
            report["source_conflict_resolved"] is False
            and report["default_changed"] is False
        )
        assert report["nominal_changed_state_count"] == 1
        assert (
            report["nominal_recipients"][0]["selected_2001_fixing_state"] == "detriment"
        )
        assert (
            report["nominal_recipients"][0]["conditional_2002_fixing_state"]
            == "exaltation"
        )
        proof = verify_human_design_reading(result)
        assert proof["status"] == "verified_fixed_template_reading", proof
        result.pop("run_metadata")
    assert expected == native == cli
