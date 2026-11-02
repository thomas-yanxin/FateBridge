"""Solar convention statements follow the returned geometry across transports."""

import asyncio
import json

import pytest
from fastmcp import Client

from fatebridge.cli import run
from fatebridge.core.local_techniques.otherbu import _solar_position_snapshot
from fatebridge.mcp_server import create_mcp_app
from tests.ephemeris_case_runtime import native_ephemeris_files
from tests.test_astrodice_transports import SPEC
from tests.test_astrodice_transports import rest as rest_fixture

rest = rest_fixture


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_native_extension_is_explained_without_rewriting_the_dice(
    rest, capsys, zodiacal, native_ephemeris_files
):
    inputs = dict(
        planet="Mars",
        sign="Aries",
        house=0,
        date="2022-11-08",
        time="21:00",
        zone="UTC",
        gps_lat=51.5,
        gps_lon=0,
        zodiacal=zodiacal,
    )
    fields = [
        "planet",
        "sign",
        "house",
        "snapshot_text",
        "chart.params.chart_profile.apparent_position_policy",
    ]
    response = rest.post(
        SPEC.rest_path,
        json=inputs,
        params={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": True,
            "response_char_limit": 0,
        },
    )
    assert response.status_code == 200, response.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "otherbu",
                {
                    **inputs,
                    "fields": fields,
                    "strict_fields": True,
                    "include_snapshot_text": True,
                    "response_char_limit": 0,
                },
            )
            assert not result.is_error
            return result.structured_content

    mcp = asyncio.run(invoke())
    flags = ["otherbu"]
    for key, value in inputs.items():
        flags.extend(["--" + key.replace("_", "-"), str(value)])
    assert (
        run(
            [
                *flags,
                "--fields",
                *fields,
                "--strict-fields",
                "--include-snapshot-text",
                "true",
                "--response-char-limit",
                "0",
            ]
        )
        == 0
    )
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
        assert (
            "Mercury：太阳盘后方；视位置来自透明太阳质量模型的虚拟延拓"
            in result["snapshot_text"]
        )
        assert "不代表采用 Horizons 的全部视位置约定" in result["snapshot_text"]
        assert "不是可见性、遮掩接触时刻或观测精度证明" in result["snapshot_text"]
        assert policy["source_url"] in result["snapshot_text"]
        assert "连续延拓" not in result["snapshot_text"]
        assert policy["source_model_regularity"]["axis_continuity_certified"] is False
        result.pop("run_metadata")
    assert values[0] == values[1] == values[2]


def test_unverified_model_and_geometry_are_not_described_as_verified():
    text = _solar_position_snapshot(
        {
            "solar_deflection_model": "unverified_native_model",
            "bodies": {
                "Venus": {
                    "status": "not_evaluated",
                    "reason": "unverified_native_version",
                }
            },
            "source_url": "https://www.astro.com/swisseph/swisseph.htm",
            "source_section": "Appendix A",
            "native_version": "unknown",
        }
    )
    assert "未经版本核验" in text and "几何未计算" in text
    assert "透明太阳质量模型的虚拟延拓" not in text
