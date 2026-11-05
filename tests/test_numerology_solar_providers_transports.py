"""Actual model attribution and runtime range errors on REST, MCP and CLI."""

import asyncio
import json

import pytest
from jsonschema import Draft202012Validator

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_numerology_solar_providers import (
    REFERENCE,
    TRACE_ID,
    assert_actual_source,
)
from tests.test_numerology_solar_providers import (
    solar_aa1996_build as shared_build_fixture,
)
from tests.test_numerology_solar_providers import (
    solar_provider_environment as shared_provider_fixture,
)

rest = shared_rest


@pytest.mark.parametrize("mode", REFERENCE["provider_modes"])
@pytest.mark.parametrize("family", ["heluo", "canping"])
def test_actual_source_profiles_survive_all_adapters(
    mode, family, monkeypatch, solar_provider_environment, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    spec = SPECS[family]
    payload = REFERENCE["valid_input"]
    response = rest.post(
        spec.rest_path, json=payload, params={"response_char_limit": 0}
    )
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    mcp = asyncio.run(native(spec, {**payload, "response_char_limit": 0}))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        spec.output_model.model_validate(out)
        Draft202012Validator(spec.output_model.model_json_schema()).validate(out)
        assert_actual_source(out, family, mode)


@pytest.mark.parametrize("family", ["heluo", "canping"])
def test_source_only_projection_keeps_actual_source_identity(
    family, monkeypatch, solar_provider_environment, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    spec = SPECS[family]
    fields = ["numerology_evidence.rulesets", "numerology_evidence.rule_trace"]
    payload = REFERENCE["valid_input"]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", name) for name in fields]
        + [("strict_fields", "true"), ("response_char_limit", "0")],
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    mcp = asyncio.run(
        native(
            spec,
            {
                **payload,
                "fields": fields,
                "strict_fields": True,
                "response_char_limit": 0,
            },
        )
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        facts = next(
            r
            for r in out["numerology_evidence"]["rule_trace"]
            if r["rule_id"] == TRACE_ID
        )["facts"]
        assert facts["all_source_urls_available"] is True
        assert {p["source_url"] for p in facts["source_profiles"]} == {
            "https://moshier.net/"
        }
        assert all(
            p["model_metadata"]["binary_sha256"]
            == p["model_metadata"]["loaded_image_sha256"]
            for p in facts["source_profiles"]
        )


def test_aa1996_lower_endpoint_keeps_120_years_on_all_adapters(
    monkeypatch, solar_provider_environment, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    spec = SPECS["canping"]
    payload = {**REFERENCE["valid_input"], "date": "1800-01-03"}
    response = rest.post(
        spec.rest_path, json=payload, params={"response_char_limit": 0}
    )
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    mcp = asyncio.run(native(spec, {**payload, "response_char_limit": 0}))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        assert len(out["liunian_series"]["rows"]) == 120
        assert len(out["liunian_series"]["year_boundaries"]) == 121
        assert_actual_source(out, "canping", "aa1996")


def test_aa1996_source_exhaustion_is_nonretryable503_on_all_adapters(
    monkeypatch, solar_provider_environment, rest, tmp_path, capsys
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    spec = SPECS["canping"]
    payload = {**REFERENCE["valid_input"], "date": "2200-05-15"}
    response = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    mcp = asyncio.run(native(spec, payload))
    assert response.status_code == 503 and code == 1 and mcp.is_error
    assert cli["status_code"] == 503
    text = "\n".join(block.text for block in mcp.content if hasattr(block, "text"))
    mcp_error = json.loads(text)
    for error in [response.json(), cli, mcp_error]:
        assert error["retryable"] is False
        assert error["issues"][0]["code"] == "solar_aa1996_range"
