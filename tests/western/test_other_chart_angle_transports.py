"""Actual REST/MCP/CLI must preserve the unresolved specialty reference."""

import asyncio
import json

from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.house_roles import audit_specialty_house_roles
from tests.western.test_other_chart_angle_qualification import LOCATIONS, PAYLOAD


def test_unresolved_reference_survives_four_entries_and_three_surfaces(
    monkeypatch, tmp_path, capsys
):
    specs = {s.key: s for s in CATALOG}
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    seen = []

    async def exercise():
        with TestClient(api.app) as rest:
            async with Client(create_mcp_app()) as client:
                for key, variant in [
                    ("astro_germany", None),
                    ("astro_chart", "germany"),
                    ("astro_chart13", None),
                    ("astro_chart", "chart13"),
                ]:
                    germany = key == "astro_germany" or variant == "germany"
                    fields = (
                        [
                            "base_chart.chart_profile.house_system",
                            "base_chart.chart_profile.house_system_code",
                            "base_chart.chart_profile.house_system_label_zh",
                            "midpoint_analysis.profile.reference_angle_model",
                            "midpoint_analysis.meridian_houses.profile.house_code",
                            "midpoint_analysis.profile.angle_definition",
                            "midpoint_analysis.factors",
                            "midpoint_analysis.time_sensitivity.samples",
                            "midpoint_analysis.time_sensitivity.factor_spans",
                            "midpoint_analysis.dials.90.two_factor_contacts",
                        ]
                        if germany
                        else [
                            "chart_profile.house_system",
                            "chart_profile.house_system_code",
                            "chart_profile.house_system_label_zh",
                            "sector_profile",
                            "thirteen_sectors",
                            "planets",
                            "time_sensitivity.samples",
                            "time_sensitivity.sector_assignments",
                        ]
                    )
                    spec = specs[key]
                    longitude, latitude = LOCATIONS[0]
                    payload = {
                        **PAYLOAD,
                        "birth_longitude": longitude,
                        "birth_latitude": latitude,
                    }
                    if variant:
                        payload["chart_variant"] = variant
                    options = {
                        "as_of": "2026-01-01T00:00:00Z",
                        "strict_fields": True,
                        "include_snapshot_text": False,
                        "response_char_limit": 0,
                        "fields": fields,
                    }
                    response = rest.post(
                        spec.rest_path,
                        json=payload,
                        params=[
                            ("as_of", options["as_of"]),
                            ("strict_fields", "true"),
                            ("include_snapshot_text", "false"),
                            ("response_char_limit", "0"),
                            *[("fields", field) for field in fields],
                        ],
                    )
                    native = await client.call_tool(
                        spec.tool_name, {**payload, **options}, raise_on_error=False
                    )
                    path = tmp_path / f"{key}-{variant}.json"
                    path.write_text(json.dumps(payload))
                    capsys.readouterr()
                    code = run(
                        [
                            spec.tool_name,
                            "--subject-file",
                            str(path),
                            "--as-of",
                            options["as_of"],
                            "--strict-fields",
                            "--no-include-snapshot-text",
                            "--response-char-limit",
                            "0",
                            "--fields",
                            *fields,
                        ]
                    )
                    local = json.loads(capsys.readouterr().out)
                    assert response.status_code == 200, response.text
                    assert not native.is_error, native.content
                    assert code == 0, local
                    assert native.structured_content == json.loads(
                        native.content[0].text
                    )
                    bodies = [
                        {k: v for k, v in body.items() if k != "run_metadata"}
                        for body in [response.json(), native.structured_content, local]
                    ]
                    assert bodies[0] == bodies[1] == bodies[2]
                    layer = bodies[0].get("midpoint_analysis", bodies[0])
                    role_audit = audit_specialty_house_roles(
                        bodies[0],
                        requested_hsys=1,
                        declared_base_house_system="Alcabitus",
                    )
                    assert (
                        role_audit["status"] == "consistent_recorded_roles"
                    ), role_audit
                    assert role_audit["base_house_system"]["swiss_house_code"] == "B"
                    assert (
                        audit_specialty_house_roles(
                            bodies[0],
                            requested_hsys=1,
                            declared_base_house_system="Equal",
                        )["status"]
                        == "mismatch"
                    )
                    assert len(layer["time_sensitivity"]["samples"]) == 5
                    assert (
                        layer["time_sensitivity"]["samples"][2]["angle_definition"][
                            "geometric_ascendant_resolved"
                        ]
                        is False
                    )
                    if germany:
                        assert (
                            layer["profile"]["angle_definition"][
                                "geometric_ascendant_resolved"
                            ]
                            is False
                        )
                        assert len(layer["factors"]) == 22
                        rows = layer["dials"]["90"]["two_factor_contacts"]
                        affected = [
                            row
                            for row in rows
                            if "Ascendant" in [row["id_a"], row["id_b"]]
                        ]
                        assert affected
                        assert all(
                            row["physical_reference_geometry_resolved"] is False
                            for row in affected
                        )
                    else:
                        assert (
                            layer["sector_profile"]["status"]
                            == "underdetermined_ascendant"
                        )
                        assert layer["thirteen_sectors"] == []
                        assert all(row["sector13"] is None for row in layer["planets"])
                        assert all(
                            row["sector_by_sample"][2] is None
                            and row["unresolved_sample_count"] == 1
                            for row in layer["time_sensitivity"]["sector_assignments"]
                        )
                    seen.append((key, variant))

    asyncio.run(exercise())
    assert len(seen) == 4
