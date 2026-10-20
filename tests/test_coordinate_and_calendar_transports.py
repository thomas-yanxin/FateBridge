"""Coordinate, neutral-score and calendar-option repairs agree across transports."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
from fatebridge.cli import run
from fatebridge.mcp_server import app as mcp_app
from fatebridge.services.tool_catalog import CATALOG


def invoke(tool, inputs, monkeypatch, capsys):
    spec = next(spec for spec in CATALOG if spec.tool_name == tool)
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(spec.rest_path, json=inputs)
    args = [tool, "--response-char-limit", "0"]
    for key, value in inputs.items():
        if isinstance(value, list):
            args.extend(["--" + key.replace("_", "-"), *map(str, value)])
            continue
        args.extend(
            [
                "--" + key.replace("_", "-"),
                str(value).lower() if isinstance(value, bool) else str(value),
            ]
        )
    code = run(args)
    local = json.loads(capsys.readouterr().out)

    async def call():
        async with Client(mcp_app) as client:
            return await client.call_tool(
                tool, {**inputs, "response_char_limit": 0}, raise_on_error=False
            )

    protocol = asyncio.run(call())
    assert json.loads(protocol.content[0].text) == protocol.structured_content
    return (
        response,
        code,
        protocol,
        [response.json(), local, protocol.structured_content],
    )


def test_zero_gps_coordinates_drive_the_actual_chart_on_every_transport(
    monkeypatch, capsys
):
    response, code, protocol, outputs = invoke(
        "suzhan",
        {
            "date": "2026-10-20",
            "time": "12:00",
            "zone": "UTC",
            "gps_lat": 0,
            "gps_lon": 0,
        },
        monkeypatch,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in outputs:
        assert output["params"]["birthLatitude"] == output["params"]["gpsLat"] == 0
        assert output["params"]["birthLongitude"] == output["params"]["gpsLon"] == 0
    assert outputs[0]["chart"] == outputs[1]["chart"] == outputs[2]["chart"]


@pytest.mark.parametrize(
    "changes", [{"lon": "190"}, {"lat": "31N90"}, {"gps_lon": -181}]
)
def test_bad_calendar_coordinates_fail_identically(monkeypatch, capsys, changes):
    response, code, protocol, outputs = invoke(
        "nongli_time",
        {"date": "2026-10-20", "time": "12:00", **changes},
        monkeypatch,
        capsys,
    )
    assert response.status_code == 400 and code == 1 and protocol.is_error
    assert all(output["error_code"] == "validation_error" for output in outputs)
    assert all("run_metadata" not in output for output in outputs)


def test_unknown_gender_love_score_is_neutral_on_every_transport(monkeypatch, capsys):
    response, code, protocol, outputs = invoke(
        "liushi_analysis",
        dict(
            birth_year=1990,
            birth_month=5,
            birth_day=15,
            birth_hour=10,
            gender="未知",
            birth_timezone="Asia/Shanghai",
            use_true_solar_time=False,
            analysis_year=2026,
            analysis_month=10,
            analysis_day=20,
            analysis_hour=12,
        ),
        monkeypatch,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert all(output["life_dimensions"]["love"] == 50 for output in outputs)


def test_removed_rollover_switch_is_rejected_on_every_transport(monkeypatch, capsys):
    response, code, protocol, outputs = invoke(
        "nongli_time",
        {"date": "2026-10-20", "time": "23:30", "after23_new_day": False},
        monkeypatch,
        capsys,
    )
    assert response.status_code == 422 and code == 2 and protocol.is_error
    assert outputs[0]["error_code"] == outputs[2]["error_code"] == "validation_error"
    assert outputs[1]["error_code"] == "usage_error"


@pytest.mark.parametrize(
    "tool,inputs,canonical,removed",
    [
        ("jieqi_year", {"year": 2028}, "jieqi_year", {"jieqi24"}),
        (
            "nongli_time",
            {"date": "2028-04-01", "time": "09:00:00"},
            "timeGanZi",
            {"year", "time"},
        ),
        ("gua_meiyi", {"name": ["111", "000"]}, "results", {"111", "000"}),
    ],
)
def test_canonical_helper_results_agree_without_duplicate_fields(
    monkeypatch, capsys, tool, inputs, canonical, removed
):
    response, code, protocol, outputs = invoke(tool, inputs, monkeypatch, capsys)
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert all(removed.isdisjoint(output) for output in outputs)
    assert outputs[0][canonical] == outputs[1][canonical] == outputs[2][canonical]


def test_birth_strength_uses_one_assessment_on_every_transport(monkeypatch, capsys):
    response, code, protocol, outputs = invoke(
        "bazi_birth",
        {
            "birth_year": 1990,
            "birth_month": 5,
            "birth_day": 15,
            "birth_hour": 10,
            "gender": "男",
            "use_true_solar_time": False,
        },
        monkeypatch,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    births = [output["bazi_birth"] for output in outputs]
    assert births[0] == births[1] == births[2]
    for birth in births:
        assert "element_distribution_adjusted" not in birth
        assert "element_relations" not in birth
        assessment = birth["day_master"]["assessment"]
        assert set(assessment["effective_elements"]) == {"木", "火", "土", "金", "水"}
