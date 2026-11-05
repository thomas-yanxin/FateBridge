"""Native point metadata and bounded clock failures survive all public surfaces."""

import asyncio
import json

import pytest

from fatebridge.core import solar_term_clock
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    inputs,
    native,
)
from tests.test_agentic_nested_outputs import rest as _shared_rest
from tests.test_bazi_tt_utc_exact_transports import check_terms

rest = _shared_rest


@pytest.mark.parametrize("key", ["bazi_birth", "dayun_analysis", "timing_analysis"])
@pytest.mark.parametrize("project", [False, True])
def test_native_actual_selected_points_are_public_and_identical(
    key, project, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS[key]
    payload = {
        **inputs(spec),
        "birth_year": 2001,
        "birth_month": 6,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_minute": 30,
        "birth_second": 21,
        "birth_timezone": "Asia/Shanghai",
        "use_true_solar_time": False,
    }
    options = {"as_of": AS_OF, "response_char_limit": 0, "include_snapshot_text": False}
    flags = [
        "--as-of",
        AS_OF,
        "--response-char-limit",
        "0",
        "--include-snapshot-text",
        "false",
    ]
    field = "bazi_birth.calendar_context" if key == "bazi_birth" else "calendar_context"
    if project:
        options.update(fields=[field], strict_fields=True)
        flags += ["--fields", field, "--strict-fields", "true"]
    response = rest.post(spec.rest_path, json=payload, params=options)
    mcp = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert response.status_code == 200 and not mcp.is_error and code == 0, response.text
    results = [response.json(), mcp.structured_content, cli]
    for result in results:
        assert business(result) == business(results[0])
        assert check_terms(result) > 0
        spec.output_model.model_validate(result)
        calendar = (
            result["bazi_birth"]["calendar_context"]
            if key == "bazi_birth"
            else result["calendar_context"]
        )
        term = calendar["current_solar_term"]
        details = term["solar_model_details"]
        assert term["resolution_provider"] == "swisseph"
        assert details["model_id"] == "native_swiss_tt_solar_bisection_v2"
        assert details["root_selection_policy"] == "first_post_crossing_tt_float"
        assert term["ephemeris_model"] == details["ephemeris_model"] == "moshier"
        assert details["ephemeris_retflags"] == [4]
        assert (
            details["root_bracket_tt"][0]
            <= details["selected_crossing_jd_tt"]
            <= details["root_bracket_tt"][1]
        )
        assert details["selected_crossing_jd_tt"] == details["root_bracket_tt"][1]
        assert details["accuracy_certified"] is False


@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize(
    "fault,reason",
    [
        (ValueError("private-impossible-time"), "solar_root_civil_unrepresentable"),
        (ImportError("private-clock-package-path"), "solar_root_clock_unavailable"),
    ],
)
def test_native_clock_failure_is_structured_before_projection(
    project, fault, reason, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)

    def fail(*args):
        raise fault

    monkeypatch.setattr(solar_term_clock, "datetime_from_tt_point", fail)
    spec = SPECS["bazi_birth"]
    payload = {**inputs(spec), "use_true_solar_time": False}
    options = {"response_char_limit": 0}
    flags = ["--response-char-limit", "0"]
    if project:
        options.update(fields=["bazi_birth.calendar_context"], strict_fields=True)
        flags += ["--fields", "bazi_birth.calendar_context", "--strict-fields", "true"]
    response = rest.post(spec.rest_path, json=payload, params=options)
    mcp = asyncio.run(native(spec, payload, **options))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert response.status_code == 503 and mcp.is_error and code != 0
    for value in [response.json(), mcp.structured_content, cli]:
        assert value["error_code"] == "ephemeris_source_inconsistent"
        assert value["issues"] == [{"path": "runtime.solar_term_clock", "code": reason}]
        assert value["retryable"] is False
        assert "private" not in json.dumps(value)
