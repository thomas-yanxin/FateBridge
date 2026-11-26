"""Western events tool declarations and domain binding helpers."""

from __future__ import annotations

from pydantic import BaseModel

from fatebridge.application.bindings import ServiceRef, bind_kwargs, service_ref
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.western_events import (
    AstroElectionRequest,
    AstroExtraReturnsRequest,
    AstroHoraryRequest,
    AstroMundaneRequest,
)

calculate_election = service_ref(
    "fatebridge.services.western_election", "calculate_election"
)


calculate_extrareturns = service_ref(
    "fatebridge.services.western_events", "calculate_extrareturns"
)


calculate_mundane = service_ref(
    "fatebridge.services.western_events", "calculate_mundane"
)


calculate_horary = service_ref(
    "fatebridge.services.western_horary", "calculate_horary"
)


def _western_event_spec(
    name: str, service: ServiceRef, model: type[BaseModel], label: str
) -> ToolSpec:
    """Register a western ephemeris-event technique (ingress chart / planetary return)."""
    return ToolSpec(
        name=name,
        bind=bind_kwargs(service),
        request_model=model,
        summary=(
            (
                "按明确提问时刻起盘，核算月亮出宫前黄经事件、当前相位候选与原典条件缺项。"
                if name == "horary_chart"
                else (
                    "按明确候选时刻起盘，核算原生月亮事件、太阳状态与约定评分因子，未核算项保留未知。"
                    if name == "evaluate_election_time"
                    else f"生成{label}（求解天文时刻后起盘）。"
                )
            )
            + (
                "评估给定的非医疗活动候选时刻；不是整段时间自动最优搜索，不提供手术或治疗择时。"
                if name == "evaluate_election_time"
                else (
                    "生死寿命、疾病及生育临床判断类别不开放。"
                    if name == "horary_chart"
                    else ""
                )
            )
        ),
        operation_label_zh=label,
        family="western_event",
        cpu_bound=True,
        rest_path="/api/astrology/events/" + name.replace("_", "-"),
        cli_request_file=name == "horary_chart",
    )


SPECS: list[ToolSpec] = [
    _western_event_spec(
        "mundane_ingress_chart",
        calculate_mundane,
        AstroMundaneRequest,
        "世俗入宫盘",
    ),
    _western_event_spec(
        "planetary_returns",
        calculate_extrareturns,
        AstroExtraReturnsRequest,
        "多重回归",
    ),
    _western_event_spec(
        "horary_chart",
        calculate_horary,
        AstroHoraryRequest,
        "卜卦证据",
    ),
    _western_event_spec(
        "evaluate_election_time",
        calculate_election,
        AstroElectionRequest,
        "择日",
    ),
]
