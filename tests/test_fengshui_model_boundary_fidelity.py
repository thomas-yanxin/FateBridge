"""Real named solvers retain their own precision reasons through Feng Shui."""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastmcp import Client

from fatebridge.cli import run
from fatebridge.core.analytic_solar import MODEL_ID
from fatebridge.core.fengshui import bazhai as bazhai_module
from fatebridge.core.fengshui.calendar import (
    boundary_candidate_dates,
    boundary_model_policy,
    boundary_uncertainty_reason,
    lichun_resolution,
    year_context,
)
from fatebridge.core.fengshui.models import HousePeriod, MingguaRequest
from fatebridge.core.fengshui.monthly_time import solar_month_context
from fatebridge.core.fengshui.xuankong import period_context
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.fengshui import calculate_annual_stars, calculate_minggua
from tests.fixtures.fengshui import payload
from tests.test_fengshui_surfaces import rest_client, without_transport


@pytest.fixture(scope="module")
def empty_ephemeris(tmp_path_factory):
    return tmp_path_factory.mktemp("model-boundary-fidelity")


@pytest.fixture(params=["native", "analytic"])
def actual_model(request, monkeypatch, empty_ephemeris):
    monkeypatch.setenv("SE_EPHE_PATH", str(empty_ephemeris))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", request.param)
    model = "moshier" if request.param == "native" else MODEL_ID
    resolution = lichun_resolution(2024, "UTC")
    assert resolution["ephemeris_model"] == model
    assert resolution["approximate"] is False
    return model


def reason(model):
    prefix = "moshier_numeric_model" if model == "moshier" else "analytic_solar_model"
    return prefix + "_guard_not_accuracy_certification"


def test_actual_model_year_reason_survives_without_relabelling(actual_model):
    root = datetime.fromisoformat(lichun_resolution(2024, "UTC")["moment"])
    context = year_context(None, root, "UTC")
    assert context["effective_year_status"] == "requires_confirmation"
    assert context["candidate_effective_years"] == [2023, 2024]
    resolution = context["boundary_resolution"]
    assert resolution["ephemeris_model"] == actual_model
    assert resolution["uncertainty_reason"] == reason(actual_model)
    assert resolution["operational_guard_seconds"] == 5.0


def test_actual_model_house_period_is_not_mislabelled_linear(actual_model):
    root = datetime.fromisoformat(lichun_resolution(2024, "UTC")["moment"])
    result = period_context(
        HousePeriod(
            basis="construction_completion",
            event_at=root,
            timezone_name="UTC",
            evidence="虚构边界回归事件",
        )
    )
    assert result["number"] is None
    assert result["candidate_period_numbers"] == [8, 9]
    prefix = "moshier" if actual_model == "moshier" else "analytic_solar"
    assert (
        result["confirmation_reason"]
        == prefix + "_model_precision_guard_in_period_changeover_year"
    )


def test_actual_model_month_policy_identifies_each_boundary(actual_model):
    root = datetime.fromisoformat(lichun_resolution(2024, "UTC")["moment"])
    result = solar_month_context(None, None, root, "UTC")
    policies = result["precision_policy"]["boundary_model_policies"]
    assert [p["boundary"] for p in policies] == ["start", "end"]
    assert all(p["ephemeris_model"] == actual_model for p in policies)
    assert all(p["operational_guard_seconds"] == 5.0 for p in policies)
    assert all(
        p["scope"] == "candidate_preservation_not_numerical_accuracy_acceptance"
        for p in policies
    )
    assert result["precision_policy"]["numeric_acceptance_gate_seconds"] == 1.0


@pytest.mark.parametrize("delta", [-6, -5, 0, 5, 6])
def test_guard_does_not_change_numbers_or_expand_accuracy_gate(actual_model, delta):
    root = datetime.fromisoformat(lichun_resolution(2024, "UTC")["moment"])
    result = calculate_annual_stars(
        query_at=root + timedelta(seconds=delta), timezone_name="UTC"
    )
    annual = result["layers"]["annual_stars"]
    if abs(delta) <= 5:
        assert annual["status"] == "partial" and annual["palaces"] == {}
        assert annual["time_context"]["candidate_effective_years"] == [2023, 2024]
    else:
        assert annual["status"] == "complete"
        assert annual["effective_year"] == (2023 if delta < 0 else 2024)


@pytest.mark.parametrize("model", ["moshier", MODEL_ID])
def test_synthetic_midnight_crossing_keeps_model_reason_without_a_birth_hour(
    monkeypatch, model
):
    # Synthetic geometry only. Never count this clock as an observed Lichun.
    monkeypatch.setattr(
        bazhai_module,
        "lichun_resolution",
        lambda *a, **k: {
            "moment": "2024-02-04T00:00:02+08:00",
            "approximate": False,
            "provider": "swisseph" if model == "moshier" else "fatebridge_analytic",
            "ephemeris_model": model,
        },
    )
    result = bazhai_module.minggua(
        MingguaRequest(birth_date="2024-02-03", gender_convention="male")
    )
    assert result["status"] == "partial" and result["candidates"] == []
    policy = result["time_context"]["boundary_precision_policy"]
    assert policy["ephemeris_model"] == model
    prefix = "moshier" if model == "moshier" else "analytic_solar"
    assert (
        policy["reason"]
        == prefix + "_guard_crosses_civil_date_not_fabricated_birth_hour"
    )
    assert policy["boundary_possible_civil_dates"] == ["2024-02-03", "2024-02-04"]
    assert "birth_at" not in result["time_context"]


def test_actual_model_reading_names_its_solver_without_claiming_seconds(actual_model):
    result = calculate_annual_stars(effective_year=2024, timezone_name="UTC")
    text = result["snapshot_text"]
    if actual_model == MODEL_ID:
        assert "FateBridge解析太阳模型" in text
        assert "不表示秒级精度已获认证" in text
        assert "星历为Moshier" not in text
    else:
        assert "星历为Moshier" in text
        assert "FateBridge解析太阳模型" not in text


def test_confirmed_minggua_year_does_not_invent_a_solver_observation(actual_model):
    result = calculate_minggua(effective_birth_year=2024, gender_convention="male")
    context = result["layers"]["minggua"]["time_context"]
    assert result["status"] == "complete"
    assert "boundary_resolution" not in context
    assert "boundary_precision_policy" not in context
    assert "FateBridge解析太阳模型" not in result["snapshot_text"]
    assert "星历为Moshier" not in result["snapshot_text"]


@pytest.mark.parametrize("model", ["moshier", MODEL_ID, "unknown_model"])
def test_linear_fallback_does_not_borrow_stale_numerical_model_metadata(model):
    # Synthetic contradictory metadata exercises precedence, not solar accuracy.
    resolution = {
        "moment": "2024-02-04T00:00:02+00:00",
        "approximate": True,
        "ephemeris_model": model,
    }
    assert boundary_model_policy(resolution) is None
    assert (
        boundary_uncertainty_reason(
            datetime.fromisoformat(resolution["moment"]), resolution
        )
        == "linear_fallback_adjacent_civil_dates"
    )
    assert sorted(
        d.isoformat() for d in boundary_candidate_dates(resolution, "UTC")
    ) == [
        "2024-02-03",
        "2024-02-04",
        "2024-02-05",
    ]


def test_returned_analytic_provenance_cannot_poison_the_cached_term(
    monkeypatch, empty_ephemeris
):
    monkeypatch.setenv("SE_EPHE_PATH", str(empty_ephemeris))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    original = lichun_resolution(2024, "UTC")
    observed = lichun_resolution(2024, "UTC")
    observed["solar_model_details"]["model_id"] = "forged-model"
    observed["solar_model_details"]["native_choice_probe_retflags"].append(-1)
    # A caller owns its response; it must not alter another calculation's
    # cached model identity or nested provenance. No numerical score is added.
    assert lichun_resolution(2024, "UTC") == original


@pytest.mark.parametrize("name", ["annual_stars", "minggua", "xuankong_natal"])
def test_model_reason_and_reading_match_rest_real_mcp_cli(
    actual_model, monkeypatch, tmp_path, capsys, name
):
    root = lichun_resolution(2024, "UTC")["moment"]
    if name == "annual_stars":
        inputs = {"query_at": root, "timezone_name": "UTC"}
    elif name == "minggua":
        inputs = {"birth_at": root, "timezone_name": "UTC", "gender_convention": "male"}
    else:
        inputs = payload(name)
        inputs["period"] = {
            "basis": "construction_completion",
            "event_at": root,
            "timezone_name": "UTC",
            "evidence": "虚构协议回归事件",
        }
    response = rest_client(monkeypatch).post("/api/fengshui/" + name, json=inputs)

    async def call():
        async with Client(create_mcp_app(families="fengshui")) as client:
            return await client.call_tool(
                "fengshui_" + name, {**inputs, "response_char_limit": 0}
            )

    protocol = asyncio.run(call())
    request = tmp_path / "request.json"
    request.write_text(json.dumps(inputs))
    assert run(["fengshui_" + name, "--request-file", str(request)]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert response.status_code == 200 and not protocol.is_error
    body = response.json()
    assert (
        without_transport(body)
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    assert body["status"] == "partial"
    layer = body["layers"][name]
    context = (
        layer["period_context"]["event_time_context"]
        if name == "xuankong_natal"
        else layer["time_context"]
    )
    assert context["boundary_resolution"]["ephemeris_model"] == actual_model
    assert context["boundary_resolution"]["uncertainty_reason"] == reason(actual_model)
