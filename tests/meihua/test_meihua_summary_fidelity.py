"""Published default evidence and summaries carry their own computed qualifiers."""

import json

import pytest
from fastmcp import Client
from mcp import MCPError

from fatebridge.application.examples import suggested_fields
from tests.support.result_delivery import store
from tests.support.transports import AS_OF, SPECS, cached_mcp_app, call_calculation


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_analysis"])
def test_first_view_and_seasonal_evidence(tool: str) -> None:
    spec = SPECS[tool]
    first_fields = suggested_fields(spec)
    assert first_fields == suggested_fields(spec, view="general")
    assert first_fields is not None
    assert first_fields.count("summary") == 1
    assert not any(
        field.startswith("interpretation.seasonal_qualification")
        for field in first_fields
    )
    for view in ("reading", "strength"):
        fields = suggested_fields(spec, view=view)
        assert fields is not None
        assert fields.count("interpretation.seasonal_qualification") == 1


@pytest.mark.asyncio
async def test_verified_topic_page_preserves_an_empty_casting_array(store) -> None:
    spec = SPECS["meihua_analysis"]
    arguments = {
        "analysis_year": 2026,
        "analysis_month": 10,
        "analysis_day": 26,
        "analysis_hour": 12,
        "analysis_timezone": "Asia/Shanghai",
        "interpretation_topic": "traveler",
        "as_of": AS_OF,
        "fields": suggested_fields(spec, view="topic"),
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 4096,
    }
    async with Client(cached_mcp_app(families="divination")) as client:
        reply = await call_calculation(client, spec.tool_name, arguments)
        result = reply.structured_content
        assert result is not None
        result_id = result["result_delivery"]["result_id"]
        run_id = result["run_metadata"]["run_id"]
        uri = (
            f"fatebridge://results/{result_id}/verified/{run_id}"
            "/fields/interpretation.casting_readings"
        )
        page = json.loads((await client.read_resource(f"{uri}/0"))[0].text)
        assert json.loads(page["text"]) == []
        with pytest.raises(MCPError, match="结果字段路径不存在"):
            await client.read_resource(f"{uri}.0/0")
