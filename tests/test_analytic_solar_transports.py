"""Actual returned Sun identity survives all protocols and strict projection."""

import asyncio

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core.analytic_solar import MODEL_ID
from tests.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)


@pytest.mark.parametrize("project", [False, True])
def test_named_analytic_solar_source_matches_three_protocols(
    project, rest, tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "analytic")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["sixyao"]
    payload = {
        **inputs(spec),
        "date": "2000-01-07",
        "time": "12:00:00",
        "gua_code": "111111",
    }
    fields = [
        "calendar_context.current_solar_term",
        "calendar_context.next_solar_term",
        "calendar_context.bazi_month_boundary",
        "liuyao_evidence.calendar_conventions",
    ]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    response = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    mcp = asyncio.run(native(spec, payload, **options))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    results = [response.json(), cli, mcp.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        term = result["calendar_context"]["current_solar_term"]
        assert term["resolution_provider"] == "fatebridge_analytic"
        assert term["ephemeris_model"] == MODEL_ID
        details = term["solar_model_details"]
        assert details["native_choice_probe_model"] == "moshier"
        assert details["accuracy_certified"] is False
        assert details["root_time_scale"] == "TT"
        assert details["civil_time_method"]
        assert result["run_metadata"]["engine_is_approximate"] is True
        assert (
            result["run_metadata"]["runtime"]["solar_term_policy"]["mode"] == "analytic"
        )
        assert MODEL_ID in result["run_metadata"]["provenance"]["ephemeris_model"]
        assert not result.get("projection_warnings")
