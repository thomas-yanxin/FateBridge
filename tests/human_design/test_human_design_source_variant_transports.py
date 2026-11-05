"""Complete original conflict evidence through actual REST, native MCP and CLI."""

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


@pytest.fixture
def rest(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        yield client


@pytest.mark.parametrize("empty_files", [False, True])
@pytest.mark.parametrize("day", ["2000-08-18", "2000-01-01"])
def test_full_conflict_reading_and_grounding_projection_on_three_surfaces(
    rest, capsys, monkeypatch, tmp_path, empty_files, day
):
    if empty_files:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    year, month, date = map(int, day.split("-"))
    params = dict(
        birth_year=year,
        birth_month=month,
        birth_day=date,
        birth_hour=0,
        birth_minute=0,
        birth_timezone="UTC",
    )
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
                    "fields": evidence_views(SPEC)["grounding"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not card.is_error
            assert (
                card.structured_content["source_consistency"]
                == expected["source_consistency"]
            )
            return result.structured_content

    native = asyncio.run(call())
    flags = ["human_design"]
    for key, value in params.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for value in (expected, native, cli):
        check = verify_human_design_reading(value)
        assert check["status"] == "verified_fixed_template_reading", check
        assert check["checked_statement_count"] == 10
        impacts = value["source_consistency"]["activation_impacts"]
        if day == "2000-08-18":
            assert (
                impacts["conditional_printed_line_effects"]["status"]
                == "inconsistent_printed_sun_earth_lines"
            )
        else:
            names = value["source_consistency"]["cross_name_comparison"]
            assert names["observed_labels"][0]["literal_match"] is False
            assert names["disagreement_resolved"] is False
        assert (
            value["source_consistency"]["version_comparison"]["literal_name_matches"]
            == 4
        )
        value.pop("run_metadata")
    assert expected == native == cli
