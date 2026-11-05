"""Source table, incomplete cells and printed stages through three real transports."""

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


def _roundtrip(
    monkeypatch, capsys, tmp_path, key, variant, zodiacal, *, full_rows=False
):
    specs = {spec.key: spec for spec in CATALOG}
    spec = specs[key]
    fields = evidence_views(specs["astro_germany"])["witte1925_table"]["fields"]
    if full_rows:
        fields = ["midpoint_analysis.solar_arc_analysis.original_table_1925"]
    payload = dict(
        name="虚构：Witte1925原表来源验收",
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
        table = layer["original_table_1925"]
        assert table["computed_for_current_chart"] is False
        assert table["coverage"]["date_rows"] == 38
        assert table["coverage"]["raw_age_cells"] == 342
        assert table["coverage"]["resolved_age_cells"] == 318
        assert table["coverage"]["unresolved_age_cells"] == 24
        assert table["coverage"]["all_degrees_resolved"] is False
        assert table["worked_example"]["literal_arithmetic_matches_print"] is True
        assert table["worked_example"]["printed_total_arcminutes"] == 3347
        assert table["worked_example"]["hypothetical_total_fraction"] == [133917, 40]
        assert (
            table["worked_example"]["hypothetical_unrounded_policy_adopted_as_original"]
            is False
        )
        assert table["full_original_method_accepted"] is False
        assert table["real_world_efficacy"] == "not_tested"
        if full_rows:
            assert len(table["rows"]) == 38
            unknown = [
                (row["row"], age)
                for row in table["rows"]
                for age, value in zip(
                    table["age_columns_years"],
                    row["normalized_arcminutes"],
                    strict=True,
                )
                if value is None
            ]
            assert unknown == [(row, 20) for row in range(6, 30)]
            assert table["rows"][0]["raw_until_january_zero_arcminutes"] == 61
            assert table["rows"][-1]["printed_date"] == "01-06+1"
        else:
            assert "rows" not in table  # Published first view is a selected summary.


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_summary_preserves_source_scope_across_three_surfaces(
    monkeypatch, capsys, tmp_path, key, variant, zodiacal
):
    _roundtrip(monkeypatch, capsys, tmp_path, key, variant, zodiacal)


@pytest.mark.skipif(runtime.swe is None, reason="Swiss Ephemeris required")
def test_full_rows_preserve_every_unknown_through_three_surfaces(
    monkeypatch, capsys, tmp_path
):
    _roundtrip(monkeypatch, capsys, tmp_path, "astro_germany", None, 0, full_rows=True)
