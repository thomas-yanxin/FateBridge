"""Known-zone requirements across real REST, MCP and CLI dispatchers."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.test_jyotish_timezone_source import PROTOCOL


def request_payload(key, case):
    payload = dict(case["payload"])
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    if key == "astro_vimshottari":
        payload.update(analysis_year=2001, analysis_timezone="UTC")
    return payload


def three_surfaces(tmp_path, monkeypatch, capsys, key, payload):
    spec = next(s for s in CATALOG if s.key == key)
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = ["person_info.utc_datetime", "india.profile.clock_context"]
    options = {
        "as_of": PROTOCOL["as_of"],
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    params = [("fields", f) for f in fields] + [
        (k, str(v).lower() if isinstance(v, bool) else str(v))
        for k, v in options.items()
        if k != "fields"
    ]
    response = TestClient(api.app).post(spec.rest_path, json=payload, params=params)

    async def protocol_call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    mcp = asyncio.run(protocol_call())
    request_file = tmp_path / "synthetic-input.json"
    request_file.write_text(json.dumps(payload))
    capsys.readouterr()
    # JSON preserves the original scalar strings, including negative offsets.
    # The initial shared helper's '--birth-timezone -04:00' was parsed as a
    # new option. That failure and the unchanged negative vector are retained.
    code = run(
        [
            spec.tool_name,
            "--subject-file",
            str(request_file),
            "--as-of",
            PROTOCOL["as_of"],
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    return response, mcp, code, cli


@pytest.mark.parametrize("key", PROTOCOL["tool_keys"])
@pytest.mark.parametrize("case", PROTOCOL["unknown_cases"], ids=lambda c: c["id"])
def test_unresolved_birth_zone_is_the_same_typed_error_on_all_three_surfaces(
    tmp_path, monkeypatch, capsys, key, case
):
    response, mcp, code, cli = three_surfaces(
        tmp_path, monkeypatch, capsys, key, request_payload(key, case)
    )
    assert response.status_code == 400
    assert mcp.is_error and code == 1
    for body in [response.json(), json.loads(mcp.content[0].text), cli]:
        assert body["error_code"] == "validation_error", body
        assert not body["retryable"]
        assert "birth_timezone" in body["error"]
        assert "india" not in body and "vimshottari" not in body


@pytest.mark.parametrize("key", PROTOCOL["tool_keys"])
@pytest.mark.parametrize("case", PROTOCOL["valid_controls"], ids=lambda c: c["id"])
def test_resolved_and_explicit_solar_clocks_remain_usable_on_all_surfaces(
    tmp_path, monkeypatch, capsys, key, case
):
    response, mcp, code, cli = three_surfaces(
        tmp_path, monkeypatch, capsys, key, request_payload(key, case)
    )
    assert response.status_code == 200, response.text
    assert not mcp.is_error and code == 0
    bodies = [response.json(), mcp.structured_content, cli]
    stripped = [{k: v for k, v in b.items() if k != "run_metadata"} for b in bodies]
    assert stripped[0] == stripped[1] == stripped[2]
    result = bodies[0]
    clock = result["india"]["profile"]["clock_context"]
    assert clock["calculation_utc_datetime"] == result["person_info"]["utc_datetime"]
    if case["expected_utc"] is not None:
        assert result["person_info"]["utc_datetime"] == case["expected_utc"]
    else:
        assert clock["input_clock_basis"] == case["id"]
        assert clock["birth_timezone_role"] == "UTC_carrier_for_solar_input"


@pytest.mark.parametrize("key", PROTOCOL["tool_keys"])
def test_negative_offset_also_works_as_an_explicit_equals_bound_cli_flag(
    tmp_path, capsys, key
):
    case = next(c for c in PROTOCOL["valid_controls"] if c["id"] == "negative_fixed")
    payload = request_payload(key, case)
    zone = payload.pop("birth_timezone")
    spec = next(s for s in CATALOG if s.key == key)
    path = tmp_path / "synthetic-with-zone-flag.json"
    path.write_text(json.dumps(payload))
    capsys.readouterr()
    code = run(
        [
            spec.tool_name,
            "--subject-file",
            str(path),
            "--birth-timezone=" + zone,
            "--fields",
            "person_info.utc_datetime",
            "--strict-fields",
            "--no-include-snapshot-text",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    assert code == 0, result
    assert result["person_info"]["utc_datetime"] == case["expected_utc"]
