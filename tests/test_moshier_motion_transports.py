"""Actual context transports retain the executed Moshier frame and method."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.core.astro import moshier_motion
from fatebridge.core.astro.native_motion import context_motion
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.test_moshier_motion_frames import analytical  # noqa: F401


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_complete_moshier_frame_receipt_roundtrips_actual_interfaces(
    analytical, monkeypatch, capsys, zodiacal
):
    spec = next(spec for spec in CATALOG if spec.key == "otherbu")
    payload = dict(
        planet="Saturn",
        sign="Aries",
        house=0,
        date="2000-01-01",
        time="12:00",
        zone="UTC",
        gps_lat=51.5,
        gps_lon=0,
        zodiacal=zodiacal,
    )
    fields = ["chart.chart.objects", "chart.params.chart_profile.longitude_motion"]
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
        as_of="2000-01-02T12:00:00Z",
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[("fields", field) for field in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            ("as_of", options["as_of"]),
        ],
    )
    assert response.status_code == 200, response.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                spec.tool_name, {**payload, **options}, raise_on_error=False
            )

    native = asyncio.run(invoke())
    assert not native.is_error, native
    args = [spec.tool_name]
    for key, value in payload.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    args += [
        "--as-of",
        options["as_of"],
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    results = [
        {k: v for k, v in result.items() if k != "run_metadata"}
        for result in (response.json(), native.structured_content, cli)
    ]
    assert results[0] == results[1] == results[2]
    for result in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        chart = result["chart"]
        policy = chart["params"]["chart_profile"]["longitude_motion"]
        objects = {row["id"]: row for row in chart["chart"]["objects"]}
        frame = "lahiri" if zodiacal else "tropical"
        for body in moshier_motion.TARGETS:
            actual = objects[body]["motion"]
            receipt = policy["complete_position_derivatives"][body + ":" + frame]
            assert actual["source_model"] == "moshier"
            assert actual["reference_frame"] == receipt["reference_frame"]
            assert actual["method_id"] == receipt["method_id"]
            assert receipt["status"] == actual["correction_status"] == "applied"
            assert actual["longitude_speed"] == (
                actual["native_longitude_speed"]
                + actual.get("rotation_correction", 0)
                + actual["position_derivative_correction"]
            )
            if zodiacal:
                assert "rotation_correction" not in actual


def test_missing_derivative_receipt_does_not_invent_an_algorithm_version():
    motion = context_motion(
        "Moon",
        {"Moon": 13.0},
        {"Moon": "moshier"},
        "tropical_ecliptic_of_date",
        {
            "longitude_speed_native": 12.9,
            "longitude_speed_position_derivative_correction": 0.1,
        },
    )
    assert motion["method_id"] == "complete_position_derivative_method_unavailable"
    assert motion["correction_status"] == "applied"
