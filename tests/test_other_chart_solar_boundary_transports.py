"""REST, native MCP and CLI preserve partial range samples on both chart entries."""

import asyncio
import json
from datetime import timedelta

from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.test_other_chart_solar_boundary import BIRTH, PAYLOAD

AS_OF = "2026-01-01T00:00:00Z"
FIELDS = [
    "midpoint_analysis.status",
    "midpoint_analysis.time_sensitivity.status",
    "midpoint_analysis.time_sensitivity.sample_count",
    "midpoint_analysis.solar_arc_analysis.status",
    "midpoint_analysis.solar_arc_analysis.profile.key_years",
    "midpoint_analysis.solar_arc_analysis.birth_time_sensitivity",
    "midpoint_analysis.solar_arc_analysis.daily_meridian.status",
    "midpoint_analysis.solar_arc_analysis.daily_meridian.birth_time_sensitivity",
]


def test_both_entry_points_keep_all_boundary_samples_on_all_three_surfaces(
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
                ]:
                    spec = specs[key]
                    for years in (0, 150):
                        target = BIRTH + timedelta(days=years * 365.25)
                        payload = {**PAYLOAD, "analysis_datetime": target.isoformat()}
                        if variant:
                            payload["chart_variant"] = variant
                        response = rest.post(
                            spec.rest_path,
                            json=payload,
                            params=[
                                ("as_of", AS_OF),
                                ("strict_fields", "true"),
                                ("include_snapshot_text", "false"),
                                ("response_char_limit", "0"),
                                *[("fields", field) for field in FIELDS],
                            ],
                        )
                        native = await client.call_tool(
                            spec.tool_name,
                            {
                                **payload,
                                "as_of": AS_OF,
                                "fields": FIELDS,
                                "strict_fields": True,
                                "include_snapshot_text": False,
                                "response_char_limit": 0,
                            },
                            raise_on_error=False,
                        )
                        path = tmp_path / f"{key}-{years}.json"
                        path.write_text(json.dumps(payload))
                        capsys.readouterr()
                        code = run(
                            [
                                spec.tool_name,
                                "--subject-file",
                                str(path),
                                "--as-of",
                                AS_OF,
                                "--strict-fields",
                                "--no-include-snapshot-text",
                                "--response-char-limit",
                                "0",
                                "--fields",
                                *FIELDS,
                            ]
                        )
                        local = json.loads(capsys.readouterr().out)
                        assert response.status_code == 200, response.text
                        assert not native.is_error, native.content
                        assert code == 0, local
                        native_body = native.structured_content
                        assert native_body == json.loads(native.content[0].text)
                        bodies = [
                            {k: v for k, v in body.items() if k != "run_metadata"}
                            for body in [response.json(), native_body, local]
                        ]
                        assert bodies[0] == bodies[1] == bodies[2]
                        layer = bodies[0]["midpoint_analysis"]
                        assert layer["status"] == "computed"
                        assert layer["time_sensitivity"] == {
                            "status": "sampled",
                            "sample_count": 5,
                        }
                        direction = layer["solar_arc_analysis"]
                        assert direction["status"] == "computed"
                        assert direction["profile"]["key_years"] == years
                        for branch in [direction, direction["daily_meridian"]]:
                            assert branch["status"] == "computed"
                            sensitivity = branch["birth_time_sensitivity"]
                            assert sensitivity["status"] == "partial"
                            assert sensitivity["sample_count"] == 5
                            assert sensitivity["computed_sample_count"] == 3
                            assert sensitivity["unavailable_sample_count"] == 2
                            assert len(sensitivity["samples"]) == 5
                            unknown = [
                                r
                                for r in sensitivity["samples"]
                                if r["status"] == "unavailable"
                            ]
                            assert len(unknown) == 2
                            assert all(
                                r.get("source_condition_met") is None for r in unknown
                            )
                            assert all("reason_code" in r for r in unknown)
                        pattern = direction["birth_time_sensitivity"]["source_pattern"]
                        assert pattern["sampled_status"] == "underdetermined"
                        assert (
                            pattern["present_sample_count"]
                            + pattern["absent_sample_count"]
                            + pattern["unavailable_sample_count"]
                            == 5
                        )
                        seen.append((key, years))

    asyncio.run(exercise())
    assert seen == [
        ("astro_germany", 0),
        ("astro_germany", 150),
        ("astro_chart", 0),
        ("astro_chart", 150),
    ]
