"""The new geometry survives real REST/MCP/CLI projection and typed output."""

import asyncio
import json
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

from fatebridge import api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG


@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_mixed_pair_catalogue_across_three_surfaces(
    monkeypatch, capsys, tmp_path, key, variant, zodiacal
):
    spec = next(s for s in CATALOG if s.key == key)
    payload = {
        "name": "虚构：交错因素接口验收",
        "birth_year": 2000,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 4,
        "birth_minute": 30,
        "birth_timezone": "UTC",
        "birth_longitude": 0.0,
        "birth_latitude": 0.0,
        "zodiacal": zodiacal,
        "analysis_datetime": "2000-02-01T00:00:00Z",
    }
    if variant:
        payload["chart_variant"] = variant
    fields = [
        "midpoint_analysis.factors",
        "midpoint_analysis.solar_arc_analysis.profile",
        "midpoint_analysis.solar_arc_analysis.mixed_pair_geometry",
    ]
    as_of = "2026-01-01T00:00:00Z"
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
            ("as_of", as_of),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            *[("fields", f) for f in fields],
        ],
    )

    async def native():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name,
                {
                    **payload,
                    "as_of": as_of,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": False,
                    "response_char_limit": 0,
                },
                raise_on_error=False,
            )

    protocol = asyncio.run(native())
    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps(payload))
    capsys.readouterr()
    code = run(
        [
            spec.tool_name,
            "--subject-file",
            str(request_file),
            "--as-of",
            as_of,
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
    assert not protocol.is_error, protocol.content
    assert code == 0, cli
    assert protocol.structured_content == json.loads(protocol.content[0].text)
    bodies = []
    for label, body in [
        ("rest", response.json()),
        ("mcp", protocol.structured_content),
        ("cli", cli),
    ]:
        (tmp_path / (label + ".json")).write_text(
            json.dumps(body, sort_keys=True, ensure_ascii=False, allow_nan=False)
        )
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        bodies.append({k: v for k, v in body.items() if k != "run_metadata"})
    assert bodies[0] == bodies[1] == bodies[2]
    layer = bodies[0]["midpoint_analysis"]
    values = {f["id"]: Fraction(f["longitude"]) for f in layer["factors"]}
    direction = layer["solar_arc_analysis"]
    arc = Fraction(direction["profile"]["solar_arc_degrees"])
    mixed = direction["mixed_pair_geometry"]
    assert mixed["profile"]["factor_count"] == len(values) == 22
    assert (
        mixed["profile"]["birth_time_contact_sensitivity"]
        == "not_assessed_for_this_catalogue"
    )
    assert mixed["real_world_efficacy"] == "not_tested"
    for period in (90, 45):
        dial = mixed["dials"][str(period)]
        assert dial["arc_dependent_contacts"] and dial["arc_invariant_contacts"]
        for field in ("arc_dependent_contacts", "arc_invariant_contacts"):
            for row in dial[field]:
                a, b, c, d = [row[k] for k in ("id_a", "id_b", "id_c", "id_d")]
                assert len({a, b, c, d}) == 4
                assert row["arc_invariant"] == (field == "arc_invariant_contacts")
                for assignment in row["factor_layer_assignments"]:
                    x = {
                        n: values[n] + (arc if l == "solar_arc" else 0)
                        for n, l in assignment.items()
                    }
                    delta = (
                        (x[a] + x[b] - x[c] - x[d]) / 2 + Fraction(period, 2)
                    ) % period - Fraction(period, 2)
                    assert abs(delta) <= 1
                    assert float(delta) == row["signed_orb"]
