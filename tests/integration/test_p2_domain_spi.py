"""Verify P2 DomainPlugin SPI supports non-metaphysics pan-psychology domains cleanly."""

from __future__ import annotations

import asyncio
from typing import Dict

from fastmcp import Client, FastMCP
from pydantic import BaseModel, Field

from fatebridge.application.bindings import raw_invoke
from fatebridge.application.domain_plugin import DomainPlugin, assemble_catalog
from fatebridge.application.execution import execute_tool
from fatebridge.application.response_delivery import deliver_response
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.reproducibility import ReproducibilityPolicy
from fatebridge.mcp_server import _register_mcp_tools
from tests.support.transports import call_calculation, describe_capability


class _BigFiveRequest(BaseModel):
    openness: int = Field(ge=1, le=5)
    conscientiousness: int = Field(ge=1, le=5)
    extraversion: int = Field(ge=1, le=5)
    agreeableness: int = Field(ge=1, le=5)
    neuroticism: int = Field(ge=1, le=5)


def _score_big_five(
    *,
    openness: int,
    conscientiousness: int,
    extraversion: int,
    agreeableness: int,
    neuroticism: int,
) -> Dict[str, object]:
    traits = {
        "openness": openness,
        "conscientiousness": conscientiousness,
        "extraversion": extraversion,
        "agreeableness": agreeableness,
        "neuroticism": neuroticism,
    }
    normalized = {k: round((v - 1) / 4 * 100, 1) for k, v in traits.items()}
    return {
        "traits": normalized,
        "dominant_trait": max(normalized, key=normalized.__getitem__),
        "assessment": {"sources": ["self_report"]},
    }


def test_non_metaphysics_psychometric_plugin_runs_end_to_end() -> None:
    spec = ToolSpec(
        key="psych_big_five",
        bind=raw_invoke(_score_big_five),
        request_model=_BigFiveRequest,
        summary="Big Five 性格五因素确定性计分器",
        operation_label_zh="大五人格计分",
        family="psychometrics",
        rest_path="/api/psych/big-five",
        mcp_name="psych_big_five",
        required_output_fields=("traits", "dominant_trait"),
    )
    plugin = DomainPlugin(
        name="psychometrics",
        specs=(spec,),
    )
    assembled = assemble_catalog([plugin])
    assert [item.key for item in assembled] == ["psych_big_five"]

    req = _BigFiveRequest(
        openness=5,
        conscientiousness=4,
        extraversion=3,
        agreeableness=4,
        neuroticism=2,
    )
    raw = execute_tool(spec, req)
    delivered = deliver_response(raw, spec=spec, detail="compact")
    assert delivered["traits"]["openness"] == 100.0
    assert delivered["dominant_trait"] == "openness"
    assert delivered["assessment"] == raw["assessment"]
    assert delivered["run_metadata"]["tool_name"] == "psych_big_five"
    assert "calculation_evidence" not in delivered["run_metadata"]

    for tier in ("standard", "audit"):
        tiered = execute_tool(spec, req, options=ExecutionOptions(detail=tier))
        assert "ephemeris" not in tiered["run_metadata"]["runtime"]
        assert "solar_term_policy" not in tiered["run_metadata"]["runtime"]

    custom_policy = ReproducibilityPolicy(
        random_seed_field="seed", seed_condition="bootstrap_resampling"
    )
    assert custom_policy.as_manifest()["seed_condition"] == "bootstrap_resampling"

    server = FastMCP("psych-test")
    _register_mcp_tools(server, assembled)

    async def call_mcp():
        async with Client(server) as client:
            contract = await describe_capability(client, "psych_big_five")
            assert contract["tool"] == "psych_big_five"
            res = await call_calculation(
                client,
                "psych_big_five",
                {
                    "openness": 5,
                    "conscientiousness": 4,
                    "extraversion": 3,
                    "agreeableness": 4,
                    "neuroticism": 2,
                    "detail": "compact",
                },
            )
            assert not res.is_error
            assert res.structured_content["dominant_trait"] == "openness"

    asyncio.run(call_mcp())
