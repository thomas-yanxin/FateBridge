"""Solver fallbacks cannot certify the side of a near-Lichun boundary."""

import asyncio
import json
from datetime import timedelta

import pytest
from fastmcp import Client

from fatebridge.cli import run
from fatebridge.core.fengshui import calendar
from fatebridge.services.fengshui import calculate_annual_stars, calculate_minggua
from tests.test_fengshui_surfaces import rest_client, without_transport


@pytest.mark.parametrize("zone", ["Asia/Shanghai", "UTC", "America/New_York"])
@pytest.mark.parametrize("minutes", [-1, 0, 1])
def test_aware_annual_and_birth_queries_keep_year_uncertain_on_solver_fallback(
    monkeypatch, zone, minutes
):
    instant = calendar.lichun(2026, zone) + timedelta(minutes=minutes)
    original = calendar.lichun_resolution
    monkeypatch.setattr(
        calendar,
        "lichun_resolution",
        lambda year, name: {
            **original(year, name),
            "provider": "linear_fallback",
            "approximate": True,
        },
    )
    annual = calculate_annual_stars(query_at=instant, timezone_name=zone)["layers"][
        "annual_stars"
    ]
    assert annual["status"] == "partial" and annual["palaces"] == {}
    assert annual["time_context"]["effective_year"] is None
    assert annual["time_context"]["candidate_effective_years"] == [2025, 2026]
    birth = calculate_minggua(
        birth_at=instant, timezone_name=zone, gender_convention="male"
    )["layers"]["minggua"]
    assert birth["status"] == "partial" and birth["candidates"] == []
    assert birth["time_context"]["effective_year"] is None
    assert "boundary_precision" in birth["missing_inputs"][0]


def test_explicit_year_and_distant_instant_remain_usable_on_fallback(monkeypatch):
    instant = calendar.lichun(2026, "Asia/Shanghai") + timedelta(days=4)
    original = calendar.lichun_resolution
    monkeypatch.setattr(
        calendar,
        "lichun_resolution",
        lambda year, zone: {
            **original(year, zone),
            "provider": "linear_fallback",
            "approximate": True,
        },
    )
    for inputs in ({"effective_year": 2026}, {"query_at": instant}):
        assert calculate_annual_stars(**inputs)["status"] == "complete"
    assert (
        calculate_minggua(effective_birth_year=2026, gender_convention="male")["status"]
        == "complete"
    )


@pytest.mark.parametrize("name", ["annual_stars", "minggua"])
def test_uncertain_boundary_has_the_same_partial_contract_on_every_transport(
    monkeypatch, tmp_path, capsys, name
):
    from fatebridge.mcp_server import create_mcp_app

    instant = calendar.lichun(2026, "Asia/Shanghai")
    original = calendar.lichun_resolution
    monkeypatch.setattr(
        calendar,
        "lichun_resolution",
        lambda year, zone: {
            **original(year, zone),
            "provider": "linear_fallback",
            "approximate": True,
        },
    )
    inputs = (
        {"query_at": instant.isoformat()}
        if name == "annual_stars"
        else {"birth_at": instant.isoformat(), "gender_convention": "male"}
    )

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_" + name, {**inputs, "response_char_limit": 0}
            )

    http = rest_client(monkeypatch).post("/api/fengshui/" + name, json=inputs)
    protocol = asyncio.run(call())
    path = tmp_path / "boundary.json"
    path.write_text(json.dumps(inputs))
    assert run(["fengshui_" + name, "--request-file", str(path)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not protocol.is_error
    assert (
        without_transport(http.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    assert http.json()["status"] == "partial"
    for body in (http.json(), protocol.structured_content, cli):
        assert body["run_metadata"]["engine_is_approximate"] is True
        assert "approximate_engine" in body["run_metadata"]["warnings"]
