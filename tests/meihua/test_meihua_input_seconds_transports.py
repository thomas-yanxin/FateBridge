"""REST, local MCP and CLI preserve the supplied second and reject coercion."""

import pytest

from tests.support.meihua_input_seconds_reference import cases, parameters
from tests.support.transports import SPECS, business, rest, surface_calls

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
def test_boundary_seconds_reach_all_local_surfaces(index, side, surface_calls):
    case = cases()[index]
    payload = parameters(case[side])
    spec = SPECS["meihua_analysis"]
    response, mcp, code, cli = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": FIELDS, "strict_fields": True},
            "response_char_limit": 0,
        },
    )
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
def test_invalid_seconds_are_rejected_on_all_local_surfaces(second, surface_calls):
    payload = parameters(cases()[0]["after"])
    payload["analysis_second"] = second
    spec = SPECS["meihua_analysis"]
    response, mcp, code, cli = surface_calls(spec, payload)
    assert response.status_code == 422 and code != 0 and mcp.is_error
    for result in [response.json(), cli, mcp.structured_content]:
        assert (
            result["error_code"] == "validation_error" and result["retryable"] is False
        )
