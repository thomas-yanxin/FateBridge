"""Western events tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import Any, List

from fatebridge.application.bindings import lazy_service, raw_invoke
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.western_events import (
    AstroElectionRequest,
    AstroExtraReturnsRequest,
    AstroHoraryRequest,
    AstroMundaneRequest,
)

calculate_election = lazy_service(
    "fatebridge.services.western_election", "calculate_election"
)


calculate_extrareturns = lazy_service(
    "fatebridge.services.western_events", "calculate_extrareturns"
)


calculate_mundane = lazy_service(
    "fatebridge.services.western_events", "calculate_mundane"
)


calculate_horary = lazy_service(
    "fatebridge.services.western_horary", "calculate_horary"
)


def _western_event_spec(name: str, service: Any, model: Any, label: str) -> ToolSpec:
    """Register a western ephemeris-event technique (ingress chart / planetary return)."""
    return ToolSpec(
        key=f"astro_{name}",
        bind=raw_invoke(service),
        request_model=model,
        summary=(
            f"生成{label}（求解天文时刻后起盘）。"
            + (
                "评估给定的非医疗活动候选时刻；不是整段时间自动最优搜索，不提供手术或治疗择时。"
                if name == "election"
                else (
                    "生死寿命、疾病及生育临床判断类别不开放。"
                    if name == "horary"
                    else ""
                )
            )
        ),
        operation_label_zh=label,
        family="western_event",
        rest_path=f"/api/astro/event/{name}",
        mcp_name=f"astro_{name}",
    )


SPECS: List[ToolSpec] = [
    _western_event_spec(
        "mundane",
        calculate_mundane,
        AstroMundaneRequest,
        "世俗入宫盘",
    ),
    _western_event_spec(
        "extrareturns",
        calculate_extrareturns,
        AstroExtraReturnsRequest,
        "多重回归",
    ),
    _western_event_spec(
        "horary",
        calculate_horary,
        AstroHoraryRequest,
        "卜卦判断",
    ),
    _western_event_spec(
        "election",
        calculate_election,
        AstroElectionRequest,
        "择日",
    ),
]
