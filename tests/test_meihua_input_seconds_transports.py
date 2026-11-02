"""REST, local MCP and CLI preserve the supplied second and reject coercion."""

import asyncio

import pytest

from tests.meihua_input_seconds_reference import cases, parameters
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

FIELDS = [
    "analysis_context",
    "meihua.seed",
    "meihua.calendar_policy.civil_clock_resolution",
    "meihua.seasonal_strength",
    "calendar_context.bazi_month_boundary",
]


@pytest.mark.parametrize(
    "index,side", [(0, "before"), (0, "after"), (2, "after"), (26, "after")]
)
def test_boundary_seconds_reach_all_local_surfaces(index, side, rest, tmp_path, capsys):
    case = cases()[index]
    payload = parameters(case[side])
    spec = SPECS["meihua_analysis"]
    response = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            *(("fields", f) for f in FIELDS),
            ("strict_fields", "true"),
            ("response_char_limit", "0"),
        ],
    )
    code, cli = call_cli(
        spec,
        payload,
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
    mcp = asyncio.run(native(spec, payload, fields=FIELDS, strict_fields=True))
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert (
        cli["calendar_context"]["bazi_month_boundary"]["branch"]
        == case[side + "_month_branch"]
    )
    assert cli["analysis_context"]["current_jieqi"] == case[side + "_current_term"]


@pytest.mark.parametrize("second", [True, 60, -1, 1.5, "1"])
def test_invalid_seconds_are_rejected_on_all_local_surfaces(
    second, rest, tmp_path, capsys
):
    payload = parameters(cases()[0]["after"])
    payload["analysis_second"] = second
    spec = SPECS["meihua_analysis"]
    response = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    mcp = asyncio.run(native(spec, payload))
    assert response.status_code == 422 and code != 0 and mcp.is_error
    for result in [response.json(), cli, mcp.structured_content]:
        assert (
            result["error_code"] == "validation_error" and result["retryable"] is False
        )
