"""Run the same Sukuyo calculation through REST, native MCP and CLI."""

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path

from fastapi.testclient import TestClient
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from jsonschema import Draft202012Validator
from pytest import CaptureFixture, MonkeyPatch

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.support.transports import call_calculation

SPECS = {spec.key: spec for spec in CATALOG}
AS_OF = "2026-10-22T12:00:00+08:00"
FULLMOON_REFERENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data/sukuyo-fullmoon-primary.json"
)


def assert_sukuyo_transport_parity(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    key: str,
    payload: Mapping[str, str | int | float | list[str]],
    fields: list[str],
) -> None:
    spec = SPECS[key]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    options = {
        "as_of": AS_OF,
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def call() -> CallToolResult:
        async with Client(create_mcp_app()) as client:
            return await call_calculation(
                client, spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(call())
    args = [spec.tool_name]
    for name, value in payload.items():
        args += ["--" + name.replace("_", "-")]
        args += [str(v) for v in value] if isinstance(value, list) else [str(value)]
    args += [
        "--as-of",
        AS_OF,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    code = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not native.is_error, native.structured_content
    assert code == 0, cli
    payloads = [response.json(), native.structured_content, cli]
    verifies_host_reference = any(
        field.endswith("host_calculation.source_url") for field in fields
    )
    expected_source_url = (
        json.loads(FULLMOON_REFERENCE_PATH.read_bytes())["source_url"]
        if verifies_host_reference
        else None
    )
    for body in payloads:
        spec.output_model.model_validate(body)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        if verifies_host_reference:
            source = body["sukuyo"] if key == "suzhan" else body["person1"]
            profile = source["calendar"]["profile_calculation"]
            host = profile["host_calculation"]
            assert profile["calendar_profile"] == "hinoo_t1299_host27"
            assert host["ruleset_id"] == "t1299_lower_fullmoon27_v1"
            assert host["source_url"] == expected_source_url
            assert host["direct_locator"] == "T21n1299_p0394c20-0395a04; p0395b01-03"
            assert host["shortcut_locator"] == "T21n1299_p0395b04-08"
        else:
            pass
    business = [
        {k: v for k, v in body.items() if k != "run_metadata"} for body in payloads
    ]
    assert business[0] == business[1] == business[2]
