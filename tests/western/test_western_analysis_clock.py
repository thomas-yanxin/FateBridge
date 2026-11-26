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
    WesternTimingBaseRequest,
    WesternTimingRequest,
)
from fatebridge.services.catalog.western_timing import SPECS
from fatebridge.services.western_timing import calculate_western_timing_analysis
from fatebridge.services.western_timing_tools import calculate_timing_tool
from tests.fixtures.transports import mcp_parameters
from tests.support.transports import call_calculation

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
def test_target_clock_overrides_preserve_date_only_defaults(
    clock, expected: str
) -> None:
    info = build_predictive_birth_info(**BIRTH)
    with call_clock("2031-01-01T00:00:00Z"):
        target = build_analysis_datetime(info, **DATE, **clock)
    assert target.isoformat() == f"2026-10-14T{expected}:00+08:00"
    assert info.local_datetime.isoformat() == "1990-05-15T10:30:00+09:00"


@pytest.mark.parametrize(
    "zone,as_of,clock,expected",
    [
        pytest.param(
            "-05:00",
            "0001-01-01T00:00:00Z",
            {"analysis_hour": 0, "analysis_minute": 7},
            "2026-10-14T00:07:00-05:00",
            id="lower",
        ),
        pytest.param(
            "+08:00",
            "9999-12-31T23:59:59.999999Z",
            {},
            "2026-10-14T10:30:00+08:00",
            id="upper",
        ),
    ],
)
def test_complete_target_date_ignores_unrepresentable_local_call_clock(
    zone: str, as_of: str, clock, expected: str
) -> None:
    info = build_predictive_birth_info(**{**BIRTH, "birth_timezone": zone})
    with call_clock(as_of) as execution:
        target = build_analysis_datetime(info, **DATE, **clock)
    assert target.isoformat() == expected
    assert not execution.reads


def test_partial_target_date_uses_local_call_clock_and_explicit_minutes() -> None:
    info = build_predictive_birth_info(**BIRTH)
    # Frozen instant is March 31 locally. A default day must still fit February.
    with call_clock("2026-03-30T20:00:00Z"):
        target = build_analysis_datetime(
            info, analysis_month=2, analysis_hour=0, analysis_minute=7
        )
    assert target.isoformat() == "2026-02-28T00:07:00+08:00"


@pytest.mark.parametrize("model", [WesternTimingRequest, WesternTimingBaseRequest])
@pytest.mark.parametrize(
    "field,value,code",
    [
        ("analysis_hour", -1, "greater_than_equal"),
        ("analysis_hour", 24, "less_than_equal"),
        ("analysis_minute", -1, "greater_than_equal"),
        ("analysis_minute", 60, "less_than_equal"),
    ],
)
def test_target_clock_bounds(model, field: str, value, code: str) -> None:
    with pytest.raises(ValidationError) as exc:
        model(**BIRTH, **DATE, **{field: value})
    assert [(e["loc"], e["type"]) for e in exc.value.errors()] == [((field,), code)]


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_every_timing_surface_exposes_the_same_clock_contract(spec) -> None:
    from fatebridge.api import app

    rest_schema = app.openapi()["components"]["schemas"][spec.request_model.__name__]
    mcp_schema = mcp_parameters(spec.name)
    args = build_parser().parse_args(
        [
            spec.name,
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
        "--detail",
        "audit",
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
            ("detail", "audit"),
            ("fields", "analysis_context"),
            ("fields", "summary"),
        ],
    )

    async def native_call():
        async with Client(mcp.app) as client:
            result = await call_calculation(
                client,
                tool,
                {
                    **payload,
                    "as_of": AS_OF,
                    "detail": "audit",
                    "fields": ["analysis_context", "summary"],
                },
                raise_on_error=False,
            )
            inline = result.structured_content
            return result, inline

    protocol, complete = asyncio.run(native_call())
    capsys.readouterr()
    exit_code = run(_cli_arguments(tool, payload))
    cli_payload = json.loads(capsys.readouterr().out)
    return response, protocol, exit_code, cli_payload, complete


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_exact_clock_reaches_every_timing_engine_through_all_transports(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], spec
) -> None:
    payload = {**BIRTH, **DATE, "analysis_hour": 12, "analysis_minute": 7}
    response, protocol, code, cli_payload, complete = _all_transports(
        monkeypatch, capsys, spec.name, spec.rest_path, payload
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
        {k: v for k, v in output.items() if k != "run_metadata"}
        for output in [response.json(), complete, cli_payload]
    ]
    assert business[0] == business[1] == business[2]


@pytest.mark.parametrize("spec", [SPECS[0], SPECS[3]], ids=lambda spec: spec.name)
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
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    spec,
    field: str,
    value,
    code: str,
) -> None:
    payload = {**BIRTH, **DATE, **{field: value}}
    response, protocol, exit_code, cli_payload, _ = _all_transports(
        monkeypatch, capsys, spec.name, spec.rest_path, payload
    )
    assert response.status_code == 422 and protocol.is_error and exit_code == 1
    for output in [response.json(), protocol.structured_content, cli_payload]:
        assert output["error_code"] == "validation_error"
        assert [(i["path"], i["code"]) for i in output["issues"]] == [(field, code)]


def test_exact_clock_changes_computed_transit_and_matches_standalone() -> None:
    kwargs = {**BIRTH, **DATE}
    legacy = calculate_timing_tool("transit_chart", **kwargs)
    noon = calculate_western_timing_analysis(
        **kwargs, analysis_hour=12, analysis_minute=0
    )
    standalone = calculate_timing_tool(
        "transit_chart", **kwargs, analysis_hour=12, analysis_minute=0
    )
    later = calculate_timing_tool(
        "transit_chart", **kwargs, analysis_hour=12, analysis_minute=37
    )
    assert noon["analysis_context"]["analysis_datetime"] == "2026-10-14T12:00:00+08:00"
    assert noon["transits"]["current_transit"] == standalone["transit_chart"]
    assert noon["natal_reference"]["sun"] == legacy["natal_reference"]["sun"]
    assert (
        standalone["transit_chart"]["moon"]["absolute_degree"]
        != legacy["transit_chart"]["moon"]["absolute_degree"]
    )
    assert (
        later["transit_chart"]["moon"]["absolute_degree"]
        != standalone["transit_chart"]["moon"]["absolute_degree"]
    )
    assert (
        later["transit_chart"]["ascendant"]["absolute_degree"]
        != standalone["transit_chart"]["ascendant"]["absolute_degree"]
    )


def test_target_clock_keeps_the_instant_when_return_location_changes() -> None:
    result = calculate_timing_tool(
        "transit_chart",
        **BIRTH,
        **DATE,
        analysis_hour=0,
        analysis_minute=0,
        return_longitude=-74,
        return_latitude=40.7,
        return_timezone="America/New_York",
    )
    target = result["analysis_context"]["analysis_datetime"]
    transit_target = result["transit_chart"]["analysis_datetime"]
    assert target == "2026-10-14T00:00:00+08:00"
    assert transit_target == "2026-10-13T12:00:00-04:00"
    assert datetime.fromisoformat(target) == datetime.fromisoformat(transit_target)


@pytest.mark.parametrize(
    "zone,hour,minute,label,nominal_jd,return_zone,return_label",
    [
        pytest.param(
            "Asia/Tokyo",
            9,
            18,
            "0001-01-01T09:18:00+09:18:59",
            148731163141 / 86400,
            None,
            "0001-01-01T09:18:00+09:18:59",
            id="tokyo-lmt",
        ),
        pytest.param(
            "+09:00",
            8,
            59,
            "0001-01-01T08:59:00+09:00",
            2478852719 / 1440,
            None,
            "0001-01-01T08:59:00+09:00",
            id="fixed-offset",
        ),
        pytest.param(
            "Asia/Tokyo",
            9,
            18,
            "0001-01-01T09:18:00+09:18:59",
            148731163141 / 86400,
            "+10:00",
            "0001-01-01T09:59:01+10:00",
            id="tokyo-lmt-to-fixed",
        ),
        pytest.param(
            "+09:00",
            8,
            59,
            "0001-01-01T08:59:00+09:00",
            2478852719 / 1440,
            "Asia/Tokyo",
            "0001-01-01T09:17:59+09:18:59",
            id="fixed-offset-to-tokyo-lmt",
        ),
    ],
)
def test_transit_accepts_representable_local_clock_in_utc_year_zero(
    zone: str,
    hour: int,
    minute: int,
    label: str,
    nominal_jd,
    return_zone: str | None,
    return_label: str,
) -> None:
    result = calculate_timing_tool(
        "transit_chart",
        birth_year=1900,
        birth_month=1,
        birth_day=15,
        birth_hour=12,
        birth_minute=0,
        birth_timezone=zone,
        birth_longitude=139.6917,
        birth_latitude=35.6895,
        analysis_year=1,
        analysis_month=1,
        analysis_day=1,
        analysis_hour=hour,
        analysis_minute=minute,
        house_system="W",
        return_timezone=return_zone,
    )
    assert result["analysis_context"]["analysis_datetime"] == label
    assert result["analysis_context"]["age_years"] == -1899.0373
    assert result["transit_chart"]["analysis_datetime"] == return_label
    basis = result["transit_chart"]["calculation_basis"]
    assert basis["time_scale"] == "pre_1972_swiss_UT1_delta_t"
    assert basis["julian_day_ut1"] == nominal_jd
