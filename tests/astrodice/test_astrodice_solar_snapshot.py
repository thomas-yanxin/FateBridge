"""Solar convention statements follow the returned geometry across transports."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from fatebridge.cli import run
from fatebridge.mcp_server import create_mcp_app
from tests.fixtures.astrodice_transports import SPEC, rest
from tests.support.ephemeris_case_runtime import native_ephemeris_files
from tests.support.transports import call_calculation


@pytest.mark.parametrize("zodiac_type", ["Tropic", "Sidereal"])
def test_native_extension_is_explained_without_rewriting_the_dice(
    rest: TestClient,
    capsys: pytest.CaptureFixture[str],
    zodiac_type: str,
    native_ephemeris_files,
) -> None:
    inputs = dict(
        planet="Mars",
        sign="Aries",
        house=0,
        date="2022-11-08",
        time="21:00",
        timezone="UTC",
        latitude=51.5,
        longitude=0,
        zodiac_type=zodiac_type,
    )
    fields = [
        "planet",
        "sign",
        "house",
        "chart.params.chart_profile.apparent_position_policy",
    ]
    response = rest.post(
        SPEC.rest_path,
        json=inputs,
        params={"fields": fields},
    )
    assert response.status_code == 200, response.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await call_calculation(
                client,
                "interpret_astrology_dice",
                {
                    **inputs,
                    "fields": fields,
                },
            )
            assert not result.is_error
            return result.structured_content

    mcp = asyncio.run(invoke())
    flags = ["interpret_astrology_dice"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert run([*flags, "--fields", *fields]) == 0
    cli = json.loads(capsys.readouterr().out)
    values = [response.json(), mcp, cli]
    for result in values:
        assert (result["planet"], result["sign"], result["house"]) == (
            "Mars",
            "Aries",
            0,
        )
        policy = result["chart"]["params"]["chart_profile"]["apparent_position_policy"]
        assert policy["bodies"]["Mercury"]["unbent_ray_domain"] == "behind_solar_disc"
        assert policy["source_model_regularity"]["axis_continuity_certified"] is False
        result.pop("run_metadata")
    assert values[0] == values[1] == values[2]
