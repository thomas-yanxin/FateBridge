"""Selected key evidence through real HTTP, native MCP and CLI dispatch."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.application.examples import evidence_views
from fatebridge.cli import run
from fatebridge.core.astro import runtime
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG

AS_OF = "2026-01-01T00:00:00Z"


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_selected_key_and_failed_original_rows_survive_all_three_surfaces(
    monkeypatch, capsys, tmp_path, key, variant, zodiacal
):
    specs = {spec.key: spec for spec in CATALOG}
    spec = specs[key]
    fields = evidence_views(specs["astro_germany"])["progression_key"]["fields"]
    payload = dict(
        name="虚构：年长钥匙来源验收",
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=4,
        birth_minute=30,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        zodiacal=zodiacal,
        analysis_datetime="2000-02-01T00:00:00Z",
    )
    if variant:
        payload["chart_variant"] = variant
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", field) for field in fields],
        ],
    )

    async def native():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "as_of": AS_OF,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )

    mcp = asyncio.run(native())
    subject = tmp_path / "subject.json"
    subject.write_text(json.dumps(payload))
    capsys.readouterr()
    code = run(
        [
            spec.tool_name,
            "--subject-file",
            str(subject),
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
    assert not mcp.is_error and code == 0
    results = [response.json(), mcp.structured_content, cli]
    bodies = [
        {k: v for k, v in result.items() if k != "run_metadata"} for result in results
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    for result in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        layer = result["midpoint_analysis"]["solar_arc_analysis"]
        profile = layer["profile"]
        comparison = profile["key_source_comparison"]
        assert profile["year_days"] == 365.25
        assert profile["key_years"] == pytest.approx((30 + 19.5 / 24) / 365.25)
        assert comparison["selected_key_from_compared_source"] is False
        assert comparison["computed_for_current_chart"] is False
        assert comparison["printed_arithmetic_consistent"] is False
        assert comparison["original_progression_time_key_accepted"] is False
        rows = {row["id"]: row for row in comparison["operations"]}
        assert rows["event_time_arc"]["printed_minus_computed_time_seconds"] == -60
        assert (
            rows["progressed_meridian_sum"]["printed_minus_computed_time_seconds"]
            == 3600
        )
        assert layer["original_text_conformance"] == "not_assessed"
        assert layer["real_world_efficacy"] == "not_tested"
