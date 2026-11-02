"""Clock presence and nominal-default notices survive each local transport."""

import asyncio

import pytest

from tests.meihua_clock_input_reference import assert_clock_input, cases
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

FIELDS = [
    "analysis_context",
    "meihua.seed",
    "meihua.calendar_policy.civil_clock_resolution",
    "meihua.rule_trace",
    "interpretation.comprehensive_judgement",
    "interpretation.evidence_scope",
    "summary",
]


@pytest.mark.parametrize("case", cases(), ids=lambda c: c["id"])
def test_all16_component_states_keep_same_values_and_provenance(
    case, rest, tmp_path, capsys
):
    spec = SPECS["meihua_analysis"]
    response = rest.post(
        spec.rest_path,
        json=case["arguments"],
        params=[
            *(("fields", f) for f in FIELDS),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
        ],
    )
    code, cli = call_cli(
        spec,
        case["arguments"],
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *FIELDS,
            "--strict-fields",
            "true",
            "--response-char-limit",
            "0",
        ],
    )
    mcp = asyncio.run(
        native(spec, case["arguments"], fields=FIELDS, strict_fields=True)
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    for value in [response.json(), cli, mcp.structured_content]:
        assert_clock_input(value, case, "bound_request_model_fields_set")
    assert (
        response.json()["run_metadata"]["input_sha256"]
        == cli["run_metadata"]["input_sha256"]
        == mcp.structured_content["run_metadata"]["input_sha256"]
    )


@pytest.mark.parametrize("minute", [True, 60, 1.5, "1"])
def test_invalid_minutes_keep_same_nonretryable_rejection(
    minute, rest, tmp_path, capsys
):
    spec = SPECS["meihua_analysis"]
    payload = {**cases()[0]["arguments"], "analysis_minute": minute}
    response = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    mcp = asyncio.run(native(spec, payload))
    assert response.status_code == 422 and code != 0 and mcp.is_error
    for out in [response.json(), cli, mcp.structured_content]:
        assert out["error_code"] == "validation_error" and not out["retryable"]
