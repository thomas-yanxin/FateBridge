"""Published motion evidence and source failures across REST, MCP and CLI."""

import asyncio
import hashlib
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from jsonschema import Draft202012Validator

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.cli import run
from fatebridge.core.astro import ephemeris, runtime
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from tests.ephemeris_case_runtime import native_ephemeris_files

pytestmark = pytest.mark.usefixtures("native_ephemeris_files")

SPEC = next(s for s in CATALOG if s.key == "otherbu")
INPUTS = {
    "planet": "Saturn",
    "sign": "Aries",
    "house": 0,
    "date": "2000-01-01",
    "time": "12:00",
    "zone": "UTC",
    "gps_lat": 51.5,
    "gps_lon": 0,
}


async def invoke(inputs, fields):
    async with Client(create_mcp_app()) as client:
        result = await client.call_tool(
            "otherbu",
            {
                **inputs,
                "fields": fields,
                "strict_fields": True,
                "include_snapshot_text": False,
            },
            raise_on_error=False,
        )
        if result.is_error:
            return result
        first = result.structured_content
        if "result_delivery" not in first:
            return first
        ref = first["result_delivery"]
        parts = []
        uri = ref["first_page_uri"]
        while uri is not None:
            page = json.loads((await client.read_resource(uri))[0].text)
            parts.append(page["text"])
            uri = page["next_uri"]
        text = "".join(parts)
        assert hashlib.sha256(text.encode()).hexdigest() == ref["sha256"]
        full = json.loads(text)
        assert full["run_metadata"]["run_id"] == first["run_metadata"]["run_id"]
        return full


def flags(inputs):
    return [
        "otherbu",
        *(
            flag
            for key, value in inputs.items()
            for flag in ("--" + key.replace("_", "-"), str(value))
        ),
    ]


@pytest.fixture
def rest(monkeypatch):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    with TestClient(api.app) as client:
        yield client


@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("failed", [None, "Saturn", "North Node"])
def test_published_motion_view_retains_unknowns_and_schema_in_all_transports(
    rest, capsys, monkeypatch, zodiacal, failed
):
    original = ephemeris._swisseph_planet_state
    if failed:
        monkeypatch.setattr(
            ephemeris,
            "_swisseph_planet_state",
            lambda name, *a, **kw: None if name == failed else original(name, *a, **kw),
        )
    inputs = {**INPUTS, "zodiacal": zodiacal}
    fields = suggested_fields(SPEC, view="astronomical_motion")
    assert "chart.params.motionPolicy" in fields and "chart.chart.objects" in fields
    assert "chart.params.chart_profile.physical_ephemeris_source" in fields
    response = rest.post(
        SPEC.rest_path,
        json=inputs,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
    )
    assert response.status_code == 200, response.text
    expected = response.json()
    Draft202012Validator(SPEC.output_model.model_json_schema()).validate(expected)
    source = expected["chart"]["params"]["chart_profile"]["physical_ephemeris_source"]
    assert source["accuracy_certified"] is False
    known_ids = {row["id"] for row in source["files"]}

    def check_ids(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "file_ids":
                    assert set(child) <= known_ids
                else:
                    check_ids(child)
        elif isinstance(value, list):
            for child in value:
                check_ids(child)

    check_ids(expected["chart"]["params"]["chart_profile"])
    points = {o["id"]: o["motion"] for o in expected["chart"]["chart"]["objects"]}
    moon = points["Moon"]
    assert "spatial_aberration_correction" in moon
    assert "lunar_source_remainder_correction" in moon
    assert moon["longitude_speed"] == (
        moon["native_longitude_speed"]
        + moon["light_time_correction"]
        + moon["spatial_aberration_correction"]
        + moon["lunar_source_remainder_correction"]
        + moon.get("rotation_correction", 0)
        + moon.get("analytic_frame_correction", 0)
    )
    assert ("analytic_frame_correction" in moon) is (not zodiacal)
    policy = expected["chart"]["params"]["motionPolicy"]
    assert policy["reference_frame"] == (
        "lahiri_sidereal_ecliptic_of_date" if zodiacal else "tropical_ecliptic_of_date"
    )
    assert points["Saturn"]["direction"] == (
        "not_computed" if failed == "Saturn" else "retrograde"
    )
    if failed:
        assert failed in policy["uncomputed_points"]
        assert points[failed]["longitude_speed"] is None
    assert points["Pars Fortuna"]["longitude_speed"] is None
    native = asyncio.run(invoke(inputs, fields))
    assert run([*flags(inputs), "--fields", *fields, "--strict-fields"]) == 0
    cli = json.loads(capsys.readouterr().out)
    for current in (expected, native, cli):
        current.pop("run_metadata")
    assert expected == native == cli


def test_missing_requested_speed_is_a_safe_source_error_in_every_transport(
    rest, capsys, monkeypatch
):
    original = runtime.ephemeris_call
    swe = runtime.swe
    assert swe is not None

    def without_speed(operation, *args, **kwargs):
        if operation == "calc" and args[1] == swe.SATURN:
            return original(operation, args[0], args[1], args[2] & ~swe.FLG_SPEED)
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", without_speed)
    response = rest.post(SPEC.rest_path, json=INPUTS)
    assert response.status_code == 503
    expected = response.json()
    assert expected["error_code"] == "ephemeris_source_inconsistent"
    assert expected["issues"] == [
        {"path": "runtime.ephemeris_data", "code": "coordinate_motion_unavailable"}
    ]
    result = asyncio.run(
        invoke(INPUTS, suggested_fields(SPEC, view="astronomical_motion"))
    )
    assert result.is_error
    assert "coordinate_motion_unavailable" in str(result)
    assert run(flags(INPUTS)) != 0
    cli = json.loads(capsys.readouterr().out)
    assert cli["error_code"] == expected["error_code"]
    assert cli["issues"] == expected["issues"]
