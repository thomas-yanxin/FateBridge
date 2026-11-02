"""Geocentric frame meaning agrees on actual REST, MCP and CLI surfaces."""

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
def test_solar_angle_vertex_and_distances_match_three_protocols(
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
    params = dict(
        birth_year=2236,
        birth_month=3,
        birth_day=1,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
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
                    "fields": evidence_views(SPEC)["apparent_positions"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
            )
            assert not card.is_error
            assert (
                card.structured_content["apparent_position_context"][
                    "coordinate_context"
                ]
                == expected["apparent_position_context"]["coordinate_context"]
            )
            assert (
                card.structured_content["interpretation"]["coordinate_frame_meaning"]
                == expected["interpretation"]["coordinate_frame_meaning"]
            )
            return result.structured_content

    native = asyncio.run(call())
    flags = ["human_design"]
    for k, v in params.items():
        flags.extend(["--" + k.replace("_", "-"), str(v)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for r in (expected, native, cli):
        assert (
            r["apparent_position_context"]["coordinate_context"][
                "angular_separation_vertex"
            ]
            == "earth_geocenter"
        )
        assert (
            verify_human_design_reading(r)["status"]
            == "verified_fixed_template_reading"
        )
        r.pop("run_metadata")
    assert expected == native == cli
