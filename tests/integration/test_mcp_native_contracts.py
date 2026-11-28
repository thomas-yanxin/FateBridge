"""Regressions through FastMCP validation, default injection and app loading."""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from fatebridge.core.requests.birth import FateBridgeRequest
from fatebridge.core.schema_cache import model_schema
from fatebridge.mcp_server import create_mcp_app
from tests.support.transports import call_calculation, describe_capability

BIRTH: dict[str, int | str] = {
    "birth_year": 1990,
    "birth_month": 6,
    "birth_day": 15,
    "birth_hour": 10,
    "gender": "男",
}
ANALYSIS: dict[str, int] = {
    "analysis_year": 2024,
    "analysis_month": 6,
    "analysis_day": 15,
    "analysis_hour": 10,
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,payload", [("bazi_birth_chart", BIRTH), ("qimen", ANALYSIS)]
)
async def test_real_mcp_omission_and_explicit_solar_flags(
    name: str, payload: dict[str, int | str]
) -> None:
    """Distinguish omitted correction from explicit values without coordinates."""
    async with Client(create_mcp_app()) as client:
        schema = (await describe_capability(client, name))["input_schema"]
        solar_flag = schema["properties"]["use_true_solar_time"]
        assert solar_flag["type"] == "boolean"
        assert solar_flag["default"] is True
        assert "use_true_solar_time" not in schema["required"]
        assert not (await call_calculation(client, name, payload)).is_error
        with pytest.raises(ToolError):
            await call_calculation(
                client, name, {**payload, "use_true_solar_time": True}
            )
        assert not (
            await call_calculation(
                client, name, {**payload, "use_true_solar_time": False}
            )
        ).is_error
        with pytest.raises(ToolError):
            await call_calculation(
                client, name, {**payload, "use_true_solar_time": None}
            )
        assert not (await call_calculation(client, name, payload)).is_error


@pytest.mark.asyncio
async def test_real_mcp_pair_keeps_each_person_explicitness_separate() -> None:
    """Require longitude only from the person who explicitly asks for correction."""
    tool_name = "bazi_compatibility"
    payload: dict[str, int | str] = {
        **{
            f"person{person_number}_{field}": value
            for person_number in (1, 2)
            for field, value in BIRTH.items()
        },
        "person1_name": "A",
        "person2_name": "B",
    }
    async with Client(create_mcp_app(families="compatibility")) as client:
        assert not (await call_calculation(client, tool_name, payload)).is_error
        for person_number in (1, 2):
            result = await call_calculation(
                client,
                tool_name,
                {**payload, f"person{person_number}_use_true_solar_time": True},
                raise_on_error=False,
            )
            assert result.is_error
            assert result.structured_content is not None
            assert result.structured_content["issues"] == [
                {
                    "path": f"person{person_number}_birth_longitude",
                    "code": "longitude_required_for_solar_time",
                }
            ]
        for second_person_options in ({}, {"person2_use_true_solar_time": True}):
            result = await call_calculation(
                client,
                tool_name,
                {
                    **payload,
                    **second_person_options,
                    "person1_use_true_solar_time": False,
                    "person1_birth_longitude": 100.0,
                    "person2_birth_longitude": 100.0,
                    "fields": [
                        f"natal_contexts.person{person_number}.calendar_context.birth_time_input"
                        for person_number in (1, 2)
                    ],
                },
            )
            assert result.structured_content is not None
            natal_contexts = result.structured_content["natal_contexts"]
            first_clock = natal_contexts["person1"]["calendar_context"][
                "birth_time_input"
            ]
            second_clock = natal_contexts["person2"]["calendar_context"][
                "birth_time_input"
            ]
            nominal_time = datetime.fromisoformat(first_clock["nominal_civil_datetime"])
            assert datetime.fromisoformat(first_clock["corrected_clock_datetime"]) == (
                nominal_time.replace(tzinfo=None)
            )
            assert (
                second_clock["nominal_civil_datetime"]
                == first_clock["nominal_civil_datetime"]
            )
            assert (
                second_clock["corrected_clock_datetime"]
                != first_clock["corrected_clock_datetime"]
            )
        with pytest.raises(ToolError):
            await call_calculation(
                client, tool_name, {**payload, "person1_use_true_solar_time": None}
            )


@pytest.mark.asyncio
async def test_real_mcp_exposes_constraints_descriptions_and_keeps_canonical_names() -> (
    None
):
    """Publish the same birth-month constraints that the calculation enforces."""
    tool_name = "bazi_birth_chart"
    async with Client(create_mcp_app(families="bazi")) as client:
        schema = (await describe_capability(client, tool_name))["input_schema"]
        month = schema["properties"]["birth_month"]
        reference = model_schema(FateBridgeRequest)["properties"]["birth_month"]
        assert month == reference
        assert "useTrueSolarTime" not in schema["properties"]
        with pytest.raises(ToolError):
            await call_calculation(client, tool_name, {**BIRTH, "birth_month": 13})


def test_app_entrypoint_reads_runtime_configuration_only_when_loaded(
    tmp_path: Path,
) -> None:
    """A host can configure the default server after importing the factory."""
    dotenv = tmp_path / ".env"
    dotenv.write_text("FATEBRIDGE_MCP_FAMILIES=bazi\n", encoding="utf-8")
    script = """
import asyncio
import json
import sys
from pathlib import Path

from fastmcp import Client

import fatebridge.mcp_server as server
from fatebridge.utils import runtime

runtime.DEFAULT_ENV_PATH = Path(sys.argv[1])

async def verify_default_app():
    from fatebridge.mcp_server import app

    assert app is server.app
    async with Client(app) as client:
        result = await client.call_tool('discover_tools', {})
    catalog = result.structured_content
    assert {tool['family'] for tool in catalog['tools']} == {'bazi'}

asyncio.run(verify_default_app())
"""
    environment = os.environ.copy()
    environment.pop("FATEBRIDGE_MCP_FAMILIES", None)
    child = subprocess.run(
        [sys.executable, "-c", script, str(dotenv)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert child.returncode == 0, child.stderr
