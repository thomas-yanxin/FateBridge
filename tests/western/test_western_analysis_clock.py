"""Exact target clocks, distinct from natal clocks, through all public surfaces."""

import asyncio
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
import fatebridge.mcp_server as mcp
from fatebridge.cli import build_parser, run
from fatebridge.core.execution_context import call_clock
from fatebridge.core.predictive._common import (
    build_analysis_datetime,
    build_predictive_birth_info,
)
from fatebridge.core.requests.western_timing import (
    WesternTimingModuleRequest,
    WesternTimingRequest,
)
from fatebridge.services.catalog.western_timing import SPECS
from fatebridge.services.western_timing import calculate_western_timing_analysis
from fatebridge.services.western_timing_tools import calculate_transit
from tests.fixtures.transports import mcp_parameters

BIRTH = {
    "name": "演示甲",
    "birth_year": 1990,
    "birth_month": 5,
    "birth_day": 15,
    "birth_hour": 10,
    "birth_minute": 30,
    "birth_place": "北京",
    "birth_timezone": "Asia/Shanghai",
    "birth_longitude": 116.4074,
    "birth_latitude": 39.9042,
}
DATE = {"analysis_year": 2026, "analysis_month": 10, "analysis_day": 14}
AS_OF = "2026-10-14T12:00:00+08:00"


@pytest.mark.parametrize(
    "clock,expected",
    [
        ({}, "10:30"),
        ({"analysis_hour": 12, "analysis_minute": 0}, "12:00"),
        ({"analysis_hour": 0, "analysis_minute": 0}, "00:00"),
        ({"analysis_hour": 23, "analysis_minute": 59}, "23:59"),
        ({"analysis_hour": 12}, "12:30"),
        ({"analysis_minute": 7}, "10:07"),
    ],
)
def test_target_clock_overrides_preserve_date_only_defaults(clock, expected):
    info = build_predictive_birth_info(**BIRTH)
    with call_clock("2031-01-01T00:00:00Z"):
        target = build_analysis_datetime(info, **DATE, **clock)
    assert target.isoformat() == f"2026-10-14T{expected}:00+08:00"
    assert info.local_datetime.isoformat() == "1990-05-15T10:30:00+09:00"


def test_partial_target_date_uses_local_call_clock_and_explicit_minutes():
    info = build_predictive_birth_info(**BIRTH)
    # Frozen instant is March 31 locally. A default day must still fit February.
    with call_clock("2026-03-30T20:00:00Z"):
        target = build_analysis_datetime(
            info, analysis_month=2, analysis_hour=0, analysis_minute=7
        )
    assert target.isoformat() == "2026-02-28T00:07:00+08:00"


@pytest.mark.parametrize("model", [WesternTimingRequest, WesternTimingModuleRequest])
@pytest.mark.parametrize(
    "field,value,code",
    [
        ("analysis_hour", -1, "greater_than_equal"),
        ("analysis_hour", 24, "less_than_equal"),
        ("analysis_minute", -1, "greater_than_equal"),
        ("analysis_minute", 60, "less_than_equal"),
    ],
)
def test_target_clock_bounds(model, field, value, code):
    with pytest.raises(ValidationError) as exc:
        model(**BIRTH, **DATE, **{field: value})
    assert [(e["loc"], e["type"]) for e in exc.value.errors()] == [((field,), code)]


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.key)
def test_every_timing_surface_exposes_the_same_clock_contract(spec):
    from fatebridge.api import app

    rest_schema = app.openapi()["components"]["schemas"][spec.request_model.__name__]
    mcp_schema = mcp_parameters(spec.tool_name)
    args = build_parser().parse_args(
        [
            spec.key,
            "--birth-year",
            "1990",
            "--birth-month",
            "5",
            "--birth-day",
            "15",
            "--birth-hour",
            "10",
            "--birth-longitude",
            "116.4074",
            "--birth-latitude",
            "39.9042",
            "--analysis-hour",
            "0",
            "--analysis-minute",
            "7",
        ]
    )
    assert (args.analysis_hour, args.analysis_minute) == (0, 7)
    for field, maximum in [("analysis_hour", 23), ("analysis_minute", 59)]:
        rest_property = rest_schema["properties"][field]
        mcp_property = mcp_schema["properties"][field]
        # OpenAPI omits a null default and adds a display title; MCP keeps the
        # explicit default. Compare validation semantics, not annotations.
        assert rest_property["anyOf"] == mcp_property["anyOf"]
        assert rest_property["description"] == mcp_property["description"]
        assert rest_property.get("default") is None
        assert mcp_property["default"] is None
        assert spec.request_model.model_fields[field].default is None
        assert field not in rest_schema["required"]
        assert field not in mcp_schema["required"]
        assert {"type": "integer", "minimum": 0, "maximum": maximum} in rest_property[
            "anyOf"
        ]


def _cli_arguments(tool, payload):
    args = [tool]
    for field, value in payload.items():
        args.extend(["--" + field.replace("_", "-"), str(value)])
    return args + [
        "--as-of",
        AS_OF,
        "--no-include-snapshot-text",
        "--strict-fields",
        "--fields",
        "analysis_context",
        "summary",
    ]


def _all_transports(monkeypatch, capsys, tool, path, payload):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        path,
        json=payload,
        params=[
            ("as_of", AS_OF),
            ("include_snapshot_text", "false"),
            ("strict_fields", "true"),
            ("fields", "analysis_context"),
            ("fields", "summary"),
        ],
    )

    async def native_call():
        async with Client(mcp.app) as client:
            return await client.call_tool(
                tool,
                {
                    **payload,
                    "as_of": AS_OF,
                    "include_snapshot_text": False,
                    "strict_fields": True,
                    "fields": ["analysis_context", "summary"],
                },
                raise_on_error=False,
            )

    protocol = asyncio.run(native_call())
    assert json.loads(protocol.content[0].text) == protocol.structured_content
    capsys.readouterr()
    exit_code = run(_cli_arguments(tool, payload))
    cli_payload = json.loads(capsys.readouterr().out)
    return response, protocol, exit_code, cli_payload


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.key)
def test_exact_clock_reaches_every_timing_engine_through_all_transports(
    monkeypatch, capsys, spec
):
    payload = {**BIRTH, **DATE, "analysis_hour": 12, "analysis_minute": 7}
    response, protocol, code, cli_payload = _all_transports(
        monkeypatch, capsys, spec.tool_name, spec.rest_path, payload
    )
    assert response.status_code == 200 and not protocol.is_error and code == 0
    outputs = [response.json(), protocol.structured_content, cli_payload]
    for output in outputs:
        context = output["analysis_context"]
        assert context["analysis_datetime"] == "2026-10-14T12:07:00+08:00"
        assert context["birth_datetime"] == "1990-05-15T10:30:00+09:00"
        assert (
            output["run_metadata"]["determinism"]["current_time_fields_defaulted"] == []
        )
    business = [
        {k: v for k, v in output.items() if k != "run_metadata"} for output in outputs
    ]
    assert business[0] == business[1] == business[2]
    assert (
        len({output["run_metadata"]["business_output_sha256"] for output in outputs})
        == 1
    )


@pytest.mark.parametrize("spec", [SPECS[0], SPECS[3]], ids=lambda spec: spec.key)
@pytest.mark.parametrize(
    "field,value,code",
    [
        ("analysis_hour", -1, "greater_than_equal"),
        ("analysis_hour", 24, "less_than_equal"),
        ("analysis_minute", -1, "greater_than_equal"),
        ("analysis_minute", 60, "less_than_equal"),
    ],
)
def test_invalid_clock_is_rejected_consistently(
    monkeypatch, capsys, spec, field, value, code
):
    payload = {**BIRTH, **DATE, **{field: value}}
    response, protocol, exit_code, cli_payload = _all_transports(
        monkeypatch, capsys, spec.tool_name, spec.rest_path, payload
    )
    assert response.status_code == 422 and protocol.is_error and exit_code == 1
    for output in [response.json(), protocol.structured_content, cli_payload]:
        assert output["error_code"] == "validation_error"
        assert [(i["path"], i["code"]) for i in output["issues"]] == [(field, code)]


def test_exact_clock_changes_computed_transit_and_matches_standalone():
    kwargs = {**BIRTH, **DATE}
    legacy = calculate_transit(**kwargs)
    noon = calculate_western_timing_analysis(
        **kwargs, analysis_hour=12, analysis_minute=0
    )
    standalone = calculate_transit(**kwargs, analysis_hour=12, analysis_minute=0)
    later = calculate_transit(**kwargs, analysis_hour=12, analysis_minute=37)
    assert noon["analysis_context"]["analysis_datetime"] == "2026-10-14T12:00:00+08:00"
    assert noon["transits"]["current_transit"] == standalone["transit"]
    assert noon["natal_reference"]["sun"] == legacy["natal_reference"]["sun"]
    assert (
        standalone["transit"]["moon"]["absolute_degree"]
        != legacy["transit"]["moon"]["absolute_degree"]
    )
    assert (
        later["transit"]["moon"]["absolute_degree"]
        != standalone["transit"]["moon"]["absolute_degree"]
    )
    assert (
        later["transit"]["ascendant"]["absolute_degree"]
        != standalone["transit"]["ascendant"]["absolute_degree"]
    )


def test_target_clock_keeps_the_instant_when_return_location_changes():
    result = calculate_transit(
        **BIRTH,
        **DATE,
        analysis_hour=0,
        analysis_minute=0,
        return_longitude=-74,
        return_latitude=40.7,
        return_timezone="America/New_York",
    )
    target = result["analysis_context"]["analysis_datetime"]
    transit_target = result["transit"]["analysis_datetime"]
    assert target == "2026-10-14T00:00:00+08:00"
    assert transit_target == "2026-10-13T12:00:00-04:00"
    assert datetime.fromisoformat(target) == datetime.fromisoformat(transit_target)
