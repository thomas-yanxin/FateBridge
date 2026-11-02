"""Same-run topology sets and qualified source readings on actual protocols."""

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
    birth_year=1990,
    birth_month=4,
    birth_day=6,
    birth_hour=9,
    birth_minute=33,
    birth_timezone="Asia/Shanghai",
)


@pytest.mark.parametrize("empty_files", [False, True])
def test_topology_source_and_full_reading_match_actual_three_surfaces(
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
                    "fields": evidence_views(SPEC)["topology"]["fields"],
                    "strict_fields": True,
                    "response_char_limit": 8192,
                    "include_snapshot_text": False,
                },
            )
            assert not card.is_error
            assert (
                card.structured_content["bodygraph"]["circuitry"]["topology_completion"]
                == expected["bodygraph"]["circuitry"]["topology_completion"]
            )
            assert (
                card.structured_content["interpretation"]["circuit_topology_meaning"]
                == expected["interpretation"]["circuit_topology_meaning"]
            )
            assert (
                card.structured_content["source_consistency"]["archival_channel_pages"][
                    "source_label_disagreements"
                ]
                == expected["source_consistency"]["archival_channel_pages"][
                    "source_label_disagreements"
                ]
            )
            return result.structured_content

    native = asyncio.run(call())
    flags = ["human_design"]
    for key, value in INPUT.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        check = verify_human_design_reading(result)
        assert check["status"] == "verified_fixed_template_reading", check
        assert (
            result["source_consistency"]["archival_channel_pages"][
                "publisher_master_authenticity_certified"
            ]
            is False
        )
        result.pop("run_metadata")
    assert expected == native == cli
