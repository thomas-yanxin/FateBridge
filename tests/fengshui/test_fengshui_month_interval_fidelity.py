"""An unresolved sectional month cannot certify one validity window."""

import asyncio
import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastmcp import Client

from fatebridge.cli import run
from fatebridge.core.analytic_solar import MODEL_ID
from fatebridge.core.fengshui import monthly_time
from fatebridge.core.fengshui.monthly import monthly_position_reading
from fatebridge.core.fengshui.models import MonthlyRequest
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import calculate_monthly_stars as _calculate_monthly_stars
from tests.support.fengshui_clock import seconds_from_boundary
from tests.support.fengshui_transports import SPECS
from tests.support.mcp_result_assertions import (
    same_run_projected_response,
    without_transport,
)
from tests.support.transports import call_calculation, rest_client


def calculate_monthly_stars(**kwargs):
    return _calculate_monthly_stars(MonthlyRequest.model_validate(kwargs))


@pytest.fixture(params=["native", "analytic"])
def clock(request, monkeypatch, tmp_path):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv(
        "FATEBRIDGE_SOLAR_TERM_MODEL",
        "analytic" if request.param == "analytic" else "native",
    )
    return request.param


def boundary(term="立春"):
    return monthly_time.solar_term_resolution(2026, term, "UTC")


def layer(at, zone="UTC"):
    return calculate_monthly_stars(query_at=at, timezone_name=zone)["layers"][
        "monthly_stars"
    ]


@pytest.mark.parametrize(
    "term,months",
    [
        ("立春", [(2025, 12), (2026, 1)]),
        ("惊蛰", [(2026, 1), (2026, 2)]),
        ("小寒", [(2025, 11), (2025, 12)]),
    ],
)
@pytest.mark.parametrize("delta", [-1, 1])
@pytest.mark.parametrize("clock", ["analytic"], indirect=True)
def test_all_candidate_windows_keep_actual_endpoints_and_conditional_reading(
    clock, term: str, months, delta
) -> None:
    resolution = boundary(term)
    actual_model = resolution["ephemeris_model"]
    assert actual_model == MODEL_ID
    at = datetime.fromisoformat(resolution["moment"]) + timedelta(seconds=delta)
    result = layer(at)
    time = result["time_context"]
    assert result["status"] == "partial" and result["palaces"] == {}
    assert time["valid_from"] is time["valid_until"] is None
    assert time["solar_month_number"] is time["month_branch"] is None
    assert time["effective_solar_year"] == (None if term == "立春" else months[0][0])
    candidates = time["candidate_months"]
    assert [
        (c["effective_solar_year"], c["solar_month_number"]) for c in candidates
    ] == months
    assert candidates[0]["valid_until"] == candidates[1]["valid_from"]
    for candidate in candidates:
        assert candidate["candidate_only"] is True
        assert candidate["valid_from"] == candidate["start_resolution"]["moment"]
        assert candidate["valid_until"] == candidate["end_resolution"]["moment"]
        for endpoint in ("start_resolution", "end_resolution"):
            assert candidate[endpoint]["ephemeris_model"] == actual_model
            assert candidate[endpoint]["provider"] == resolution["provider"]
            path = candidate[endpoint]["full_resolution_path"]
            prefix = "layers.monthly_stars.time_context.candidate_boundary_resolutions."
            assert path.startswith(prefix)
            full = time["candidate_boundary_resolutions"][path.removeprefix(prefix)]
            assert {
                k: v
                for k, v in candidate[endpoint].items()
                if k != "full_resolution_path"
            } == {k: v for k, v in full.items() if k != "solar_model_details"}
            assert full["solar_model_details"]["model_id"] == actual_model
        assert datetime.fromisoformat(candidate["valid_from"]) < datetime.fromisoformat(
            candidate["valid_until"]
        )
    provisional = time["provisional_interval"]
    selected = next(
        c
        for c in candidates
        if (c["effective_solar_year"], c["solar_month_number"])
        == (
            time["provisional_effective_solar_year"],
            time["provisional_solar_month_number"],
        )
    )
    for key in (
        "effective_solar_year",
        "solar_month_number",
        "month_branch",
        "valid_from",
        "valid_until",
    ):
        assert provisional[key] == selected[key]
    assert time["timing"]["interval_basis"] == "provisional_solar_month"
    for endpoint in ("start_resolution", "end_resolution"):
        key = selected[endpoint]["full_resolution_path"].rsplit(".", 1)[1]
        assert time["timing"][endpoint] == time["candidate_boundary_resolutions"][key]
    statement = result["position_reading"]["statements"][0]
    assert statement["basis"]["layers.monthly_stars.time_context"] == time
    assert "暂取区间不表示月份已确认" in statement["text"]
    for c in candidates:
        assert (
            f"有效年{c['effective_solar_year']}第{c['solar_month_number']}节月"
            in statement["text"]
        )
        assert (
            c["valid_from"] in statement["text"]
            and c["valid_until"] in statement["text"]
        )


@pytest.mark.parametrize("delta", [-6, -5, -1, 0, 1, 5, 6])
def test_guard_width_and_numeric_acceptance_are_not_relaxed(clock, delta) -> None:
    resolution = boundary()
    at = datetime.fromisoformat(resolution["moment"]) + timedelta(seconds=delta)
    result = layer(at)
    time = result["time_context"]
    ambiguous = abs(seconds_from_boundary(at, resolution["civil_point"])) <= 5
    assert (result["status"] == "partial") is ambiguous
    assert time["precision_policy"]["numeric_acceptance_gate_seconds"] == 1.0
    assert time["precision_policy"]["moshier_guard_seconds"] == 5
    if not ambiguous:
        assert time["valid_from"] and time["valid_until"]
        assert "provisional_interval" not in time and "candidate_months" not in time
    else:
        pass


@pytest.mark.parametrize("year,month", [(2025, 12), (2026, 1), (2026, 2)])
def test_confirmed_month_preserves_existing_unique_window(
    clock, year: int, month: int
) -> None:
    result = calculate_monthly_stars(
        effective_solar_year=year, solar_month_number=month
    )["layers"]["monthly_stars"]
    time = result["time_context"]
    assert result["status"] == "complete" and len(result["palaces"]) == 9
    assert time["valid_from"] and time["valid_until"]
    assert time["input_basis"] == "confirmed_solar_month"
    assert "candidate_months" not in time and "provisional_interval" not in time


@pytest.mark.parametrize(
    "zone", ["Asia/Shanghai", "America/New_York", "Pacific/Kiritimati"]
)
def test_candidate_instants_are_independent_of_display_timezone(
    clock, zone: str
) -> None:
    at = datetime.fromisoformat(boundary()["moment"])
    utc = layer(at)["time_context"]["candidate_months"]
    displayed = layer(at, zone)["time_context"]["candidate_months"]
    for a, b in zip(utc, displayed):
        for key in ("effective_solar_year", "solar_month_number", "month_branch"):
            assert a[key] == b[key]
        for key in ("valid_from", "valid_until"):
            assert datetime.fromisoformat(a[key]) == datetime.fromisoformat(b[key])


@pytest.mark.parametrize("name", ["monthly_stars", "assess"])
def test_actual_rest_mcp_cli_agree_on_candidate_month_intervals(
    clock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    name: str,
) -> None:
    inputs = {"query_at": boundary()["moment"], "timezone_name": "UTC"}
    if name == "assess":
        inputs = {"methods": ["monthly_stars"], "monthly": inputs}
    else:
        pass

    async def call():
        async with Client(create_mcp_app()) as client:
            return await call_calculation(
                client, SPECS[name].name, {"detail": "audit", **inputs}
            )

    response = rest_client(monkeypatch).post(
        SPECS[name].rest_path, json=inputs, params={"detail": "audit"}
    )
    protocol = asyncio.run(call())
    path = tmp_path / "month.json"
    path.write_text(json.dumps(inputs, ensure_ascii=False))
    code = run([SPECS[name].name, "--request-file", str(path), "--detail", "audit"])
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        without_transport(response.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    time = cli["layers"]["monthly_stars"]["time_context"]
    assert time["valid_from"] is time["valid_until"] is None
    assert len(time["candidate_months"]) == 2


def test_historical_partial_payload_keeps_its_original_generic_reading() -> None:
    old = {
        "status": "partial",
        "time_context": {
            "candidate_months": [
                {
                    "effective_solar_year": 2025,
                    "solar_month_number": 12,
                    "candidate_only": True,
                }
            ]
        },
    }
    result = monthly_position_reading(deepcopy(old))
    assert "未给出唯一月盘" in result["text"]
    assert "暂取区间" not in result["text"]
    assert (
        result["statements"][0]["basis"]["layers.monthly_stars.time_context"]
        == old["time_context"]
    )


@pytest.mark.parametrize("name", ["monthly_stars", "assess"])
def test_default_wire_budget_keeps_selected_candidate_facts(clock, name: str) -> None:
    inputs = {"query_at": boundary()["moment"], "timezone_name": "UTC"}
    if name == "assess":
        inputs = {"methods": ["monthly_stars"], "monthly": inputs}
    else:
        pass
    fields = ["layers.monthly_stars.status"] + [
        "layers.monthly_stars.time_context." + key
        for key in (
            "effective_solar_year",
            "solar_month_number",
            "valid_from",
            "valid_until",
            "candidate_months",
        )
    ]

    async def call():
        async with Client(create_mcp_app()) as client:
            response = await call_calculation(
                client,
                SPECS[name].name,
                {
                    **inputs,
                    "detail": "audit",
                    "fields": fields,
                },
            )
            return response.structured_content

    original = asyncio.run(call())
    time = original["layers"]["monthly_stars"]["time_context"]
    assert time["valid_from"] is time["valid_until"] is None
    assert len(time["candidate_months"]) == 2
    assert all(
        c["start_resolution"]["moment"] == c["valid_from"]
        for c in time["candidate_months"]
    )
