"""Default MCP delivery must retain every replacement source difference."""

import asyncio

import pytest
from fastmcp import Client

from fatebridge.mcp_server import create_mcp_app
from tests.fengshui.test_fengshui_source_comparison import request
from tests.fengshui.test_fengshui_surfaces import same_run_projected_response


@pytest.mark.parametrize("period,angle", [(5, 174), (9, 39), (5, 175.5)])
@pytest.mark.parametrize("name", ["xuankong_natal", "assess"])
def test_default_budget_same_run_pages_preserve_source_conflicts(period, angle, name):
    inputs = request(period, angle)
    if name == "assess":
        inputs = {
            "methods": ["xuankong_natal"],
            "house": inputs["house"],
            "xuankong": {"period": inputs["period"]},
        }

    async def call():
        async with Client(create_mcp_app(scenarios="onda-fengshui")) as client:
            response = await client.call_tool(
                "fengshui_" + name,
                {
                    **inputs,
                    "fields": [
                        "coverage.natal_source_comparison",
                        "layers.xuankong_natal.source_comparison",
                    ],
                    "strict_fields": True,
                    "include_snapshot_text": False,
                },
            )
            assert not response.is_error
            assert len(response.content[0].text) <= 8192
            return await same_run_projected_response(client, response)

    output = asyncio.run(call())
    comparison = output["layers"]["xuankong_natal"]["source_comparison"]
    summary = output["coverage"]["natal_source_comparison"]
    assert summary == comparison["summary"]
    assert summary["status"] == "selected_source_difference"
    assert summary["replacement_candidates_compared"] == 1
    assert summary["candidate_count"] == (2 if angle == 175.5 else 1)
    assert summary["source_angle_applicability_verified"] is False
    replacement = next(
        r for r in comparison["candidates"] if r["chart_mode"] == "replacement"
    )
    assert "申听禅" in replacement["source_section"]["author"]
    assert (
        replacement["source_section"]["prose_comparison_status"]
        == "not_transcribed_or_compared"
    )
    assert replacement["diagram"]["pdf_page"] == (582 if period == 9 else 515)
    assert len(replacement["diagram"]["differences"]) == (2 if period == 9 else 1)
    assert replacement["source_angle_applicability_verified"] is False
