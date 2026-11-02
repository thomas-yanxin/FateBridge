"""Date-only evidence travels through real REST, native MCP and CLI."""

import pytest

from tests.test_sukuyo_transports import (
    test_calendar_and_relations_across_all_real_transports as check_surfaces,
)


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"zone": "Asia/Tokyo"},
        {"calendar_day_part": "first_half"},
        {"calendar_day_part": "second_half"},
        {
            "date": "0806-09-20",
            "zone": "+08:00",
            "calendar_basis": "japanese_naoj_historical_utc09",
        },
        {
            "date": "2031-01-22",
            "zone": "UTC",
            "calendar_basis": "japanese_hutime_1002_1_utc09",
        },
    ],
)
def test_omitted_clock_across_all_surfaces(monkeypatch, capsys, extra):
    payload = {
        "date": "2024-08-04",
        "zone": "+08:00",
        "calendar_profile": "hinoo_t1299_host27",
        "activity": "travel",
        "natal_mansion": "室",
        **extra,
    }
    check_surfaces(
        monkeypatch,
        capsys,
        "suzhan",
        payload,
        [
            "input_normalized",
            "params",
            "chart",
            "astronomy",
            "sukuyo.calendar",
            "sukuyo.candidate_days",
            "sukuyo.candidate_mansion_days",
            "sukuyo.personal_day",
            "sukuyo.reading_text",
            "validation",
            "summary",
        ],
    )


def test_null_clock_rest_and_native_mcp_equal_cli_omission(monkeypatch, capsys):
    import asyncio
    import json

    from fastapi.testclient import TestClient
    from fastmcp import Client
    from jsonschema import Draft202012Validator

    import fatebridge.api as api
    from fatebridge.cli import run
    from fatebridge.mcp_server import create_mcp_app
    from tests.test_sukuyo_transports import AS_OF, SPECS

    spec = SPECS["suzhan"]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    fields = [
        "input_normalized",
        "params",
        "chart",
        "astronomy",
        "sukuyo",
        "validation",
        "summary",
    ]
    payload = {
        "date": "2024-08-04",
        "time": None,
        "zone": "+08:00",
        "calendar_profile": "hinoo_t1299_host27",
    }
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
            *[("fields", v) for v in fields],
        ],
    )

    async def call():
        async with Client(create_mcp_app()) as client:
            schemas = await client.list_tools()
            schema = next(t.inputSchema for t in schemas if t.name == spec.tool_name)
            assert "time" not in schema.get("required", [])
            return await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(call())
    capsys.readouterr()
    code = run(
        [
            spec.tool_name,
            "--date",
            "2024-08-04",
            "--zone",
            "+08:00",
            "--calendar-profile",
            "hinoo_t1299_host27",
            "--as-of",
            AS_OF,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
            "--fields",
            *fields,
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200, response.text
    assert not native.is_error, native.structured_content
    assert code == 0, cli
    bodies = [response.json(), native.structured_content, cli]
    for body in bodies:
        assert body["input_normalized"]["time"] is None
        assert body["chart"] is None and body["astronomy"] is None
        spec.output_model.model_validate(body)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
    stripped = [
        {k: v for k, v in body.items() if k != "run_metadata"} for body in bodies
    ]
    assert stripped[0] == stripped[1] == stripped[2]
