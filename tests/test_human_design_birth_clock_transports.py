"""Confirmed leap labels, TT and full readings match on real public adapters."""

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
@pytest.mark.parametrize("local", [False, True])
def test_confirmed_leap_birth_and_card_match_all_three_protocols(
    monkeypatch, tmp_path, capsys, empty_files, local
):
    if empty_files:
        monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    data = dict(
        birth_year=2017 if local else 2016,
        birth_month=1 if local else 12,
        birth_day=1 if local else 31,
        birth_hour=7 if local else 23,
        birth_minute=59,
        birth_second=60,
        birth_timezone="Asia/Shanghai" if local else "UTC",
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as rest:
        response = rest.post(SPEC.rest_path, json=data)
        invalid = rest.post(SPEC.rest_path, json={**data, "birth_minute": 58})
        assert invalid.status_code == 422
    assert response.status_code == 200, response.text
    expected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)

    async def call():
        async with Client(create_mcp_app(families="astro")) as client:
            result = await client.call_tool(
                "human_design", {**data, "response_char_limit": 0}
            )
            assert not result.is_error
            card = await client.call_tool(
                "human_design",
                {
                    **data,
                    "fields": evidence_views(SPEC)["birth_clock"]["fields"],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 8192,
                },
            )
            assert (
                not card.is_error and "result_delivery" not in card.structured_content
            )
            assert (
                card.structured_content["birth_clock_evidence"]
                == expected["birth_clock_evidence"]
            )
            assert (
                card.structured_content["interpretation"]["birth_clock_meaning"]
                == expected["interpretation"]["birth_clock_meaning"]
            )
            assert len(json.dumps(card.structured_content, ensure_ascii=False)) < 8192
            return result.structured_content

    native = asyncio.run(call())
    flags = ["human_design"]
    for key, value in data.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run(flags) == 0
    cli = json.loads(capsys.readouterr().out)
    for result in (expected, native, cli):
        check = verify_human_design_reading(result)
        assert check["status"] == "verified_fixed_template_reading", check
        assert result["birth_utc"] == "2016-12-31T23:59:60.000000+00:00"
        assert result["birth_clock_evidence"]["tai_minus_utc_during_leap_seconds"] == 36
        result.pop("run_metadata")
    assert expected == native == cli
