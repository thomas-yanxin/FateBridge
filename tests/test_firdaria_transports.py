"""Production firdaria options agree across REST, native MCP and CLI."""

import asyncio
import json
from itertools import product
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import fatebridge.mcp_server as mcp
from fatebridge.cli import build_parser, run
from fatebridge.services.catalog.western_timing import SPECS
from fatebridge.services.western_timing_tools import calculate_firdaria
from tests.fixtures.surface_payloads import _western_payload
from tests.fixtures.transports import mcp_parameters
from tests.test_firdaria_reference import VECTORS

TOOLS = [spec for spec in SPECS if spec.key in {"firdaria", "western_timing_analysis"}]
OPTIONS = list(
    product(
        ("nodes_at_end", "nodes_after_mars"),
        ("fixed_365_2425", "calendar_anniversary"),
    )
)
AS_OF = "2026-10-19T12:00:00+08:00"


def _inputs(case):
    from datetime import datetime

    birth = datetime.fromisoformat(case["birth_local"])
    return {
        "name": "明确虚构的上海测试地点",
        "birth_year": birth.year,
        "birth_month": birth.month,
        "birth_day": birth.day,
        "birth_hour": birth.hour,
        "birth_minute": birth.minute,
        "birth_timezone": case["timezone"],
        "birth_longitude": 121.4737,
        "birth_latitude": 31.2304,
        "house_system": 3,
        "analysis_year": 2026,
        "analysis_month": 10,
        "analysis_day": 19,
        "analysis_hour": 12,
        "analysis_minute": 0,
    }


def _surfaces(monkeypatch, capsys, spec, inputs, fields=None):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    root = "firdaria" if spec.key == "firdaria" else "time_lords.firdaria"
    selected = fields or [root, "analysis_context", "summary"]
    options = {
        "as_of": AS_OF,
        "include_snapshot_text": False,
        "strict_fields": True,
        "fields": selected,
        "response_char_limit": 0,
    }
    response = TestClient(api.app).post(
        spec.rest_path,
        json=inputs,
        params=[
            ("as_of", AS_OF),
            ("include_snapshot_text", "false"),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
            *[("fields", field) for field in selected],
        ],
    )

    async def protocol_call():
        async with Client(mcp.app) as client:
            return await client.call_tool(
                spec.tool_name, {**inputs, **options}, raise_on_error=False
            )

    protocol = asyncio.run(protocol_call())
    protocol_payload = json.loads(protocol.content[0].text)
    assert protocol_payload == protocol.structured_content
    args = [spec.tool_name]
    for name, value in inputs.items():
        args += ["--" + name.replace("_", "-"), str(value)]
    args += [
        "--as-of",
        AS_OF,
        "--no-include-snapshot-text",
        "--strict-fields",
        "--response-char-limit",
        "0",
        "--fields",
        *selected,
    ]
    capsys.readouterr()
    code = run(args)
    cli_payload = json.loads(capsys.readouterr().out)
    return response, protocol, code, [response.json(), protocol_payload, cli_payload]


def _firdaria(output, spec):
    return (
        output["firdaria"]
        if spec.key == "firdaria"
        else output["time_lords"]["firdaria"]
    )


@pytest.mark.parametrize("spec", TOOLS, ids=lambda spec: spec.key)
def test_option_schemas_and_cli_defaults_match(spec):
    rest = api.app.openapi()["components"]["schemas"][spec.request_model.__name__]
    protocol = mcp_parameters(spec.tool_name)
    for field, values, default in [
        ("firdaria_night_order", ["nodes_at_end", "nodes_after_mars"], "nodes_at_end"),
        (
            "firdaria_year_basis",
            ["fixed_365_2425", "calendar_anniversary"],
            "fixed_365_2425",
        ),
    ]:
        for schema in (rest, protocol):
            assert schema["properties"][field]["enum"] == values
            assert schema["properties"][field]["default"] == default
            assert field not in schema["required"]
    inputs = _inputs(VECTORS["examples"][0])
    args = [spec.tool_name]
    for field, value in inputs.items():
        args += ["--" + field.replace("_", "-"), str(value)]
    parsed = build_parser().parse_args(args)
    supplied = {name: getattr(parsed, name) for name in inputs}
    request = spec.request_model.model_validate(supplied)
    assert request.firdaria_night_order == "nodes_at_end"
    assert request.firdaria_year_basis == "fixed_365_2425"


@pytest.mark.parametrize("spec", TOOLS, ids=lambda spec: spec.key)
@pytest.mark.parametrize("night_order,basis", OPTIONS)
def test_all_four_combinations_reach_real_engines_on_all_surfaces(
    monkeypatch, capsys, spec, night_order, basis
):
    inputs = {
        **_inputs(VECTORS["examples"][0]),
        "firdaria_night_order": night_order,
        "firdaria_year_basis": basis,
        "analysis_year": 2039,
        "analysis_month": 12,
        "analysis_day": 28,
        "analysis_hour": 18,
        "analysis_minute": 25,
    }
    response, protocol, code, outputs = _surfaces(monkeypatch, capsys, spec, inputs)
    assert response.status_code == 200 and not protocol.is_error and code == 0
    business = [
        {k: v for k, v in output.items() if k != "run_metadata"} for output in outputs
    ]
    assert business[0] == business[1] == business[2]
    assert (
        len({output["run_metadata"]["business_output_sha256"] for output in outputs})
        == 1
    )
    for output in outputs:
        firdaria = _firdaria(output, spec)
        assert firdaria["sect"] == "night"
        assert (
            output["analysis_context"]["analysis_datetime"]
            == "2039-12-28T18:25:00+08:00"
        )
        if night_order == "nodes_after_mars":
            assert firdaria["current_major"]["planet"] == (
                "South Node" if basis == "calendar_anniversary" else "North Node"
            )
            assert firdaria["current_sub"] is None
        else:
            assert firdaria["current_major"]["planet"] == "Sun"
        first = firdaria["timeline"][0]
        prefix = "reference" if basis == "calendar_anniversary" else "legacy"
        assert first["end"] == VECTORS["examples"][0][prefix + "_major_end"]
        assert (
            first["subperiods"][0]["end"]
            == VECTORS["examples"][0][prefix + "_first_sub_end"]
        )
        if (night_order, basis) != ("nodes_at_end", "fixed_365_2425"):
            assert firdaria["calculation_options"]["night_order"] == night_order
            assert firdaria["calculation_options"]["year_basis"] == basis


@pytest.mark.parametrize("spec", TOOLS, ids=lambda spec: spec.key)
@pytest.mark.parametrize("case", VECTORS["examples"], ids=lambda case: case["id"])
def test_original_reference_examples_and_projection_on_all_surfaces(
    monkeypatch, capsys, spec, case
):
    inputs = {
        **_inputs(case),
        "firdaria_night_order": "nodes_after_mars",
        "firdaria_year_basis": "calendar_anniversary",
    }
    root = "firdaria" if spec.key == "firdaria" else "time_lords.firdaria"
    response, protocol, code, outputs = _surfaces(
        monkeypatch,
        capsys,
        spec,
        inputs,
        fields=[root + ".timeline", root + ".calculation_options.year_basis"],
    )
    assert response.status_code == 200 and not protocol.is_error and code == 0
    assert (
        _firdaria(outputs[0], spec)
        == _firdaria(outputs[1], spec)
        == _firdaria(outputs[2], spec)
    )
    for output in outputs:
        result = _firdaria(output, spec)
        assert result["timeline"][0]["end"] == case["reference_major_end"]
        assert (
            result["timeline"][0]["subperiods"][0]["end"]
            == case["reference_first_sub_end"]
        )
        assert result["calculation_options"] == {"year_basis": "calendar_anniversary"}


@pytest.mark.parametrize("spec", TOOLS, ids=lambda spec: spec.key)
@pytest.mark.parametrize("field", ["firdaria_night_order", "firdaria_year_basis"])
def test_invalid_option_is_rejected_consistently(monkeypatch, capsys, spec, field):
    response, protocol, code, outputs = _surfaces(
        monkeypatch, capsys, spec, {**_inputs(VECTORS["examples"][0]), field: "unknown"}
    )
    assert response.status_code == 422 and protocol.is_error and code == 1
    for output in outputs:
        assert output["error_code"] == "validation_error"
        assert [(issue["path"], issue["code"]) for issue in output["issues"]] == [
            (field, "literal_error")
        ]


@pytest.mark.parametrize("spec", TOOLS, ids=lambda spec: spec.key)
@pytest.mark.parametrize(
    "case", VECTORS["invalid_local_times"], ids=lambda case: case["id"]
)
def test_calendar_dst_rejections_agree_on_all_surfaces(monkeypatch, capsys, spec, case):
    inputs = {**_inputs(case), "firdaria_year_basis": "calendar_anniversary"}
    inputs["analysis_year"] = max(2026, inputs["birth_year"] + 1)
    # Invalid birth clocks are rejected before natal calculation. Valid births
    # with invalid generated anniversaries must also fail in the production core.
    inputs.update(birth_longitude=13.405, birth_latitude=52.52)
    response, protocol, code, outputs = _surfaces(monkeypatch, capsys, spec, inputs)
    assert response.status_code == 400 and protocol.is_error and code == 1
    for output in outputs:
        assert output["error_code"] == "validation_error"
        assert case["reason"] in output["error"]
        assert not output["retryable"]


@pytest.mark.parametrize("spec", TOOLS, ids=lambda spec: spec.key)
@pytest.mark.parametrize(
    "case",
    [case for case in VECTORS["invalid_local_times"] if case["age"] == 0],
    ids=lambda case: case["id"],
)
def test_calendar_invalid_analysis_clocks_are_rejected(monkeypatch, capsys, spec, case):
    from datetime import datetime

    target = datetime.fromisoformat(case["birth_local"])
    inputs = {
        **_inputs(VECTORS["examples"][0]),
        "birth_timezone": case["timezone"],
        "analysis_year": target.year,
        "analysis_month": target.month,
        "analysis_day": target.day,
        "analysis_hour": target.hour,
        "analysis_minute": target.minute,
        "firdaria_year_basis": "calendar_anniversary",
    }
    response, protocol, code, outputs = _surfaces(monkeypatch, capsys, spec, inputs)
    assert response.status_code == 400 and protocol.is_error and code == 1
    for output in outputs:
        assert output["error_code"] == "validation_error"
        assert case["reason"] in output["error"]
        assert "分析钟时" in output["error"]


def test_default_firdaria_payload_matches_existing_frozen_dates_and_structure():
    snapshot = json.loads(
        (
            Path(__file__).parent
            / "golden"
            / "snapshots"
            / "api_astro_timing_firdaria.json"
        ).read_text()
    )
    implicit = calculate_firdaria(**_western_payload())
    explicit = calculate_firdaria(
        **_western_payload(),
        firdaria_night_order="nodes_at_end",
        firdaria_year_basis="fixed_365_2425",
    )
    # No ephemeris float comparison: these are full time-lord payloads only.
    assert implicit["firdaria"] == explicit["firdaria"] == snapshot["firdaria"]


@pytest.mark.parametrize("spec", TOOLS, ids=lambda spec: spec.key)
def test_calendar_iana_analysis_clock_after_2038_on_all_surfaces(
    monkeypatch, capsys, spec
):
    inputs = {
        **_inputs(VECTORS["examples"][0]),
        "birth_year": 2000,
        "birth_month": 1,
        "birth_day": 1,
        "birth_hour": 0,
        "birth_minute": 0,
        "birth_timezone": "Europe/Berlin",
        "birth_longitude": 13.405,
        "birth_latitude": 52.52,
        "analysis_year": 2039,
        "analysis_month": 7,
        "analysis_day": 1,
        "firdaria_year_basis": "calendar_anniversary",
    }
    response, protocol, code, outputs = _surfaces(monkeypatch, capsys, spec, inputs)
    assert response.status_code == 200 and not protocol.is_error and code == 0
    for output in outputs:
        assert output["analysis_context"]["analysis_datetime"] == (
            "2039-07-01T12:00:00+02:00"
        )
        current = _firdaria(output, spec)["current_major"]
        assert current["planet"] == "Sun"
        assert current["start"] == "2039-01-01T00:00:00+01:00"
        assert current["subperiods"][0]["end"] == ("2040-06-05T21:34:17.142857+02:00")
    business = [
        {k: v for k, v in output.items() if k != "run_metadata"} for output in outputs
    ]
    assert business[0] == business[1] == business[2]
