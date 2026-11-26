"""Published default evidence and summaries carry their own computed qualifiers."""

import pytest
from fastmcp import Client

from fatebridge.application.examples import suggested_fields
from tests.support.transports import AS_OF, SPECS, cached_mcp_app, call_calculation


@pytest.mark.parametrize("tool", ["meihua_cast", "meihua_time_cast"])
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
async def test_topic_projection_preserves_an_empty_casting_array() -> None:
    spec = SPECS["meihua_time_cast"]
    arguments = {
        "analysis_year": 2026,
        "analysis_month": 10,
        "analysis_day": 26,
        "analysis_hour": 12,
        "analysis_timezone": "Asia/Shanghai",
        "interpretation_topic": "traveler",
        "as_of": AS_OF,
        "fields": suggested_fields(spec, view="topic"),
    }
    async with Client(cached_mcp_app(families="divination")) as client:
        reply = await call_calculation(client, spec.name, arguments)
        result = reply.structured_content
        assert result is not None
        assert result["interpretation"]["casting_readings"] == []
        bad = await call_calculation(
            client,
            spec.name,
            {**arguments, "fields": ["interpretation.casting_readings.0"]},
            raise_on_error=False,
        )
        assert bad.is_error
        assert (
            bad.structured_content["issues"][0]["code"] == "non_object_projection_path"
        )
