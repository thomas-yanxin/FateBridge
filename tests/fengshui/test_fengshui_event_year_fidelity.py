"""An invariant twenty-year period cannot certify an ambiguous effective year."""

import asyncio
import json
from datetime import datetime, timedelta

import pytest
from fastmcp import Client

from fatebridge.cli import run
from fatebridge.core.fengshui import calendar, xuankong
from fatebridge.core.fengshui.models import HousePeriod
from fatebridge.core.fengshui.reading import build_natal_reading
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import (
    calculate_annual_stars,
    calculate_minggua,
    calculate_xuankong_natal,
)
from tests.support.mcp_result_assertions import without_transport
from tests.support.transports import rest_client


@pytest.fixture(params=["native", "analytic"])
def clock(request, monkeypatch, tmp_path):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv(
        "FATEBRIDGE_SOLAR_TERM_MODEL",
        "analytic" if request.param == "analytic" else "native",
    )
    return request.param


def instant(year=2025, zone="UTC"):
    return datetime.fromisoformat(calendar.lichun_resolution(year, zone)["moment"])


def natal_input(moment):
    return {
        "house": {"facing_degrees": 270, "north_reference": "magnetic"},
        "period": {
            "basis": "first_occupancy",
            "event_at": moment.isoformat(),
            "timezone_name": "UTC",
            "evidence": "虚构立春边界事件，回归用途",
        },
    }


def test_shared_year_context_never_exposes_a_confirmed_year_or_interval(clock):
    time = calendar.year_context(None, instant(), "UTC")
    assert time["effective_year_status"] == "requires_confirmation"
    assert time["effective_year"] is None
    assert time["provisional_effective_year"] == 2025
    assert time["candidate_effective_years"] == [2024, 2025]
    assert time["valid_from"] is time["valid_until"] is None
    candidates = time["candidate_year_intervals"]
    assert [c["effective_year"] for c in candidates] == [2024, 2025]
    assert candidates[0]["valid_until"] == candidates[1]["valid_from"]
    assert all(c["valid_from"] == c["start_resolution"]["moment"] for c in candidates)
    assert all(c["valid_until"] == c["end_resolution"]["moment"] for c in candidates)


def test_period_stays_resolved_without_manufacturing_a_unique_event_year(clock):
    output = calculate_xuankong_natal(**natal_input(instant()))
    natal = output["layers"]["xuankong_natal"]
    period = natal["period_context"]
    assert natal["status"] == "complete" and natal["chart"]
    assert period["resolution_status"] == "resolved" and period["number"] == 9
    assert period["effective_event_year"] is None
    assert period["effective_event_year_status"] == "requires_confirmation"
    assert period["candidate_effective_event_years"] == [2024, 2025]
    assert period["candidate_period_numbers"] == [9]
    assert period["resolution_scope"] == "period_number_only_event_year_unconfirmed"
    assert period["event_time_context"]["effective_year"] is None
    assert period["start_year"] == 2024 and period["end_year"] == 2043
    assert period["valid_from"] and period["valid_until"]


@pytest.mark.parametrize("year,periods", [(2024, [8, 9]), (2044, [9, 1])])
def test_cross_period_candidates_keep_both_windows_in_chronological_order(
    clock, year, periods
):
    natal = calculate_xuankong_natal(**natal_input(instant(year)))["layers"][
        "xuankong_natal"
    ]
    period = natal["period_context"]
    assert natal["chart"] is None and natal["candidates"] == []
    assert (
        period["number"] is None
        and period["resolution_status"] == "requires_confirmation"
    )
    assert period["effective_event_year"] is None
    assert period["candidate_effective_event_years"] == [year - 1, year]
    assert period["candidate_period_numbers"] == periods
    assert period["event_time_context"]["effective_year"] is None
    assert period["valid_from"] is period["valid_until"] is None
    assert "start" not in period["timing"] and "end" not in period["timing"]
    windows = period["timing"]["candidate_period_intervals"]
    assert [w["number"] for w in windows] == periods
    assert [w["start_year"] for w in windows] == [year - 20, year]
    assert windows[0]["valid_until"] == windows[1]["valid_from"]


def test_annual_and_minggua_keep_model_side_only_as_provisional(clock):
    at = instant()
    annual = calculate_annual_stars(query_at=at, timezone_name="UTC")["layers"][
        "annual_stars"
    ]
    birth = calculate_minggua(
        birth_at=at, timezone_name="UTC", gender_convention="male"
    )["layers"]["minggua"]
    for layer in [annual, birth]:
        assert layer["status"] == "partial"
        time = layer["time_context"]
        assert (
            time["effective_year"] is None
            and time["provisional_effective_year"] == 2025
        )
        assert time["valid_from"] is time["valid_until"] is None
        assert [c["effective_year"] for c in time["candidate_year_intervals"]] == [
            2024,
            2025,
        ]
    assert annual["palaces"] == {} and birth["candidates"] == []


def test_skipping_interval_resolution_does_not_silently_confirm_an_instant(clock):
    time = calendar.year_context(None, instant(), "UTC", resolve_interval=False)
    assert time["input_basis"] == "aware_datetime"
    assert time["effective_year"] is None
    assert time["candidate_effective_years"] == [2024, 2025]
    assert time["provisional_effective_year"] == 2025


@pytest.mark.parametrize("delta", [-6, -5, 0, 5, 6])
def test_existing_guard_width_and_candidate_period_arithmetic_remain_exact(
    clock, delta
):
    at = instant() + timedelta(seconds=delta)
    period = xuankong.period_context(
        HousePeriod.model_validate(natal_input(at)["period"])
    )
    ambiguous = abs(delta) <= 5
    assert period["number"] == 9
    if ambiguous:
        assert period["effective_event_year"] is None
        assert period["candidate_effective_event_years"] == [2024, 2025]
    else:
        assert period["effective_event_year"] == (2024 if delta < 0 else 2025)
        assert "candidate_effective_event_years" not in period


def test_explicit_confirmed_year_and_period_are_not_reinterpreted(clock):
    explicit = xuankong.period_context(
        HousePeriod(
            basis="first_occupancy",
            effective_event_year=2025,
            evidence="显式确认有效年",
        )
    )
    assert explicit["number"] == 9 and explicit["effective_event_year"] == 2025
    assert "candidate_effective_event_years" not in explicit
    confirmed = xuankong.period_context(
        HousePeriod(basis="expert_confirmed", period_number=9, evidence="显式确认宅运")
    )
    assert confirmed["number"] == 9 and confirmed["effective_event_year"] is None
    assert "effective_event_year_status" not in confirmed


def test_snapshot_and_bound_reading_distinguish_event_year_from_period(clock):
    output = calculate_xuankong_natal(**natal_input(instant()))
    text = output["snapshot_text"]
    assert "事件有效年待确认：2024、2025" in text
    assert "所有候选年均属9运" in text
    reading = build_natal_reading(output)
    statement = next(
        s for s in reading["statements"] if s["kind"] == "natal_event_year"
    )
    assert "2024、2025" in statement["text"]
    assert "9运" in statement["text"]
    assert "layers.xuankong_natal.period_context" in statement["basis_paths"]


@pytest.mark.parametrize(
    "name", ["xuankong_natal", "assess", "annual_stars", "minggua"]
)
def test_boundary_year_contract_agrees_on_actual_rest_mcp_cli(
    clock, monkeypatch, tmp_path, capsys, name
):
    at = instant()
    inputs = natal_input(at)
    if name == "assess":
        inputs = {
            "methods": ["xuankong_natal"],
            "house": inputs["house"],
            "xuankong": {"period": inputs["period"]},
        }
    elif name == "annual_stars":
        inputs = {"query_at": at.isoformat(), "timezone_name": "UTC"}
    elif name == "minggua":
        inputs = {
            "birth_at": at.isoformat(),
            "timezone_name": "UTC",
            "gender_convention": "male",
        }

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_" + name, {"response_char_limit": 0, **inputs}
            )

    response = rest_client(monkeypatch).post("/api/fengshui/" + name, json=inputs)
    protocol = asyncio.run(call())
    path = tmp_path / "event.json"
    path.write_text(json.dumps(inputs, ensure_ascii=False))
    code = run(["fengshui_" + name, "--request-file", str(path)])
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        without_transport(response.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    layer = response.json()["layers"]["xuankong_natal" if name == "assess" else name]
    time = layer.get(
        "time_context", layer.get("period_context", {}).get("event_time_context")
    )
    assert time["effective_year"] is None and time["candidate_effective_years"] == [
        2024,
        2025,
    ]
