"""Invalid internal plates must never become successful public calculations."""

import asyncio
import json
from copy import deepcopy
from unittest.mock import Mock

import pytest
from fastmcp import Client

from fatebridge.cli import run
from fatebridge.core.fengshui import xuankong
from fatebridge.core.fengshui.integrity import FLIGHT_PATH, ROLES, validate_natal_chart
from fatebridge.core.fengshui.models import XuankongRequest
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services import fengshui
from fatebridge.utils.errors import FengshuiCalculationError, handle_calculation_error
from tests.fengshui.test_fengshui_source_comparison import request
from tests.fengshui.test_fengshui_surfaces import rest_client


def corrupt(chart, fault):
    chart = deepcopy(chart)
    if fault == "duplicate":
        chart["palaces"]["E"]["mountain_star_number"] = 5
        chart["mountain_chart"]["E"] = 5
    elif fault == "permutation":
        first, second = chart["mountain_chart"]["E"], chart["mountain_chart"]["W"]
        for direction, value in (("E", second), ("W", first)):
            chart["mountain_chart"][direction] = value
            chart["palaces"][direction]["mountain_star_number"] = value
    elif fault == "representation":
        chart["mountain_chart"]["E"] = 5
    elif fault == "trace":
        trace = chart["trace"]["mountain"]
        trace["flight"] = "reverse" if trace["flight"] == "forward" else "forward"
    elif fault == "identity":
        chart["period_number"] = 8
    elif fault == "shape":
        del chart["palaces"]["SE"]["mountain_star_number"]
    else:
        raise AssertionError(fault)
    return chart


@pytest.mark.parametrize(
    "fault",
    ["duplicate", "permutation", "representation", "trace", "identity", "shape"],
)
@pytest.mark.parametrize("name", ["xuankong_natal", "assess"])
def test_public_calculation_rejects_internal_faults_before_interpretation(
    monkeypatch, tmp_path, capsys, fault, name
):
    original = xuankong._chart
    monkeypatch.setattr(
        xuankong, "_chart", lambda *a, **k: corrupt(original(*a, **k), fault)
    )
    interpreter = Mock(wraps=fengshui.analyze_natal_interpretation)
    monkeypatch.setattr(fengshui, "analyze_natal_interpretation", interpreter)
    inputs = request(
        interpretation={
            "current_period_number": 9,
            "period_evidence": "虚构评价运，仅作异常回归",
        }
    )
    if name == "assess":
        inputs = {
            "methods": ["xuankong_natal"],
            "house": inputs["house"],
            "xuankong": {k: v for k, v in inputs.items() if k != "house"},
        }
    controls = {
        "fields": ["summary"],
        "strict_fields": True,
        "trace_id": "natal-integrity-fault",
        "parent_run_id": "prior-safe-run",
    }

    async def call():
        async with Client(create_mcp_app()) as client:
            return await client.call_tool(
                "fengshui_" + name,
                {**inputs, **controls, "response_char_limit": 0},
                raise_on_error=False,
            )

    http = rest_client(monkeypatch).post(
        "/api/fengshui/" + name,
        json=inputs,
        params={
            "fields": "summary",
            "strict_fields": "true",
            "trace_id": controls["trace_id"],
            "parent_run_id": controls["parent_run_id"],
        },
    )
    mcp = asyncio.run(call())
    path = tmp_path / "fault.json"
    path.write_text(json.dumps(inputs), encoding="utf-8")
    code = run(
        [
            "fengshui_" + name,
            "--request-file",
            str(path),
            "--fields",
            "summary",
            "--strict-fields",
            "--trace-id",
            controls["trace_id"],
            "--parent-run-id",
            controls["parent_run_id"],
        ]
    )
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 503
    assert mcp.is_error and code == 1

    def business_error(value):
        # HTTP carries the status in its response; MCP additionally describes
        # the operation and HTTP-equivalent status in its error object.
        if "status_code" in value:
            assert value["status_code"] == 503
        return {k: v for k, v in value.items() if k not in {"operation", "status_code"}}

    assert http.json() == business_error(mcp.structured_content) == business_error(cli)
    error = http.json()
    assert error["error_code"] == "fengshui_calculation_inconsistent"
    assert error["retryable"] is False
    assert error["trace_id"] == controls["trace_id"]
    assert error["parent_run_id"] == controls["parent_run_id"]
    assert error["issues"][0]["path"] == "runtime.fengshui.natal_chart"
    assert not {
        "layers",
        "snapshot_text",
        "calculation_reading",
        "result_delivery",
        "run_metadata",
    }.intersection(error)
    interpreter.assert_not_called()


def validate(chart):
    mountains = xuankong.natal_rules()["mountains"]
    validate_natal_chart(
        chart, period=7, facing=mountains[4], sitting=mountains[16], mode="lower"
    )


@pytest.mark.parametrize("period", range(1, 10))
def test_every_declared_lower_and_replacement_branch_retains_valid_arithmetic(period):
    mountains = xuankong.natal_rules()["mountains"]
    for index in range(24):
        for mode in ("lower", "replacement"):
            chart = xuankong._chart(period, (index, mode, "fixed-branch-test"))
            before = deepcopy(chart)
            validate_natal_chart(
                chart,
                period=period,
                facing=mountains[index],
                sitting=mountains[(index + 12) % 24],
                mode=mode,
            )
            assert chart == before


@pytest.mark.parametrize("role", ROLES)
def test_each_permutation_preserving_swap_is_rejected_without_source_comparison(role):
    original = xuankong.xuankong_natal(XuankongRequest.model_validate(request()))[
        "chart"
    ]
    for index, first in enumerate(FLIGHT_PATH):
        second = FLIGHT_PATH[(index + 1) % 9]
        chart = deepcopy(original)
        a, b = chart[role + "_chart"][first], chart[role + "_chart"][second]
        for direction, value in ((first, b), (second, a)):
            chart[role + "_chart"][direction] = value
            chart["palaces"][direction][role + "_star_number"] = value
        assert sorted(chart[role + "_chart"].values()) == list(range(1, 10))
        with pytest.raises(FengshuiCalculationError, match="九宫"):
            validate(chart)


@pytest.mark.parametrize("value", [True, 1.0, "1", None, 10])
def test_invalid_numeric_types_cannot_pass_python_equality(value):
    chart = xuankong.xuankong_natal(XuankongRequest.model_validate(request()))["chart"]
    direction = next(d for d in FLIGHT_PATH if chart["mountain_chart"][d] == 1)
    chart["mountain_chart"][direction] = value
    chart["palaces"][direction]["mountain_star_number"] = value
    with pytest.raises(FengshuiCalculationError):
        validate(chart)


def test_fault_in_flight_primitive_stops_before_numeric_structure(monkeypatch):
    original = xuankong._fly

    def faulty(*a, **k):
        result = original(*a, **k)
        result["E"], result["W"] = result["W"], result["E"]
        return result

    monkeypatch.setattr(xuankong, "_fly", faulty)
    structure = Mock(wraps=xuankong.natal_structure)
    monkeypatch.setattr(xuankong, "natal_structure", structure)
    with pytest.raises(FengshuiCalculationError):
        xuankong.xuankong_natal(XuankongRequest.model_validate(request()))
    structure.assert_not_called()


def test_one_invalid_uncertainty_candidate_cannot_be_silently_discarded(monkeypatch):
    inputs = request(7, 7.5)
    safe = xuankong.xuankong_natal(XuankongRequest.model_validate(inputs))
    assert len(safe["candidates"]) > 1
    target = safe["candidates"][-1]["candidate_id"]
    original = xuankong._chart
    seen = []

    def faulty(*a, **k):
        chart = original(*a, **k)
        seen.append(chart["candidate_id"])
        return (
            corrupt(chart, "permutation") if chart["candidate_id"] == target else chart
        )

    monkeypatch.setattr(xuankong, "_chart", faulty)
    with pytest.raises(FengshuiCalculationError):
        xuankong.xuankong_natal(XuankongRequest.model_validate(inputs))
    assert len(seen) > 1 and target in seen


@pytest.mark.parametrize("reason", list(FengshuiCalculationError.MESSAGES))
def test_consistency_fault_has_safe_nonretryable_server_error(reason):
    result = handle_calculation_error(FengshuiCalculationError(reason), "test")
    assert result["status_code"] == 503 and result["retryable"] is False
    path = (
        "runtime.fengshui.monthly_stars"
        if reason == "monthly_plate_inconsistent"
        else (
            "runtime.fengshui.interpretation"
            if reason
            in {
                "natal_mutual_geometry_inconsistent",
                "natal_author_timeliness_inconsistent",
                "natal_host_guest_inconsistent",
            }
            else "runtime.fengshui.natal_chart"
        )
    )
    assert result["issues"] == [{"path": path, "code": reason}]
    with pytest.raises(ValueError):
        FengshuiCalculationError("arbitrary-secret-or-path")
