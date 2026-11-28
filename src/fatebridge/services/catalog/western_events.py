"""Western events tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import (
    ServiceRef,
    bind_kwargs,
    request_model_ref,
    service_ref,
)
from fatebridge.application.tool_spec import ToolSpec

_REQ_MODULE = "fatebridge.core.requests.western_events"


calculate_election = service_ref(
    "fatebridge.services.western_election", "calculate_election"
)


calculate_extrareturns = service_ref(
    "fatebridge.services.western_events", "calculate_extrareturns"
)


calculate_mundane = service_ref(
    "fatebridge.services.western_events", "calculate_mundane"
)


calculate_horary = service_ref("fatebridge.services.western_horary", "calculate_horary")


def _western_event_spec(
    name: str,
    service: ServiceRef,
    model_name: str,
    label: str,
    *,
    default_omit: tuple[str, ...] = (),
) -> ToolSpec:
    """Register a western ephemeris-event technique (ingress chart / planetary return)."""
    return ToolSpec(
        name=name,
        bind=bind_kwargs(service),
        request_model_loader=request_model_ref(_REQ_MODULE, model_name),
        summary=(
            "按明确提问时刻起盘，核算月亮出宫前黄经事件与原典条件；禁生死/疾病/生育判断。"
            if name == "horary_chart"
            else (
                "按明确候选时刻起盘评估非医疗活动条件（支持窗口搜索）。"
                if name == "evaluate_election_time"
                else f"生成{label}（求解天文时刻后起盘）。"
            )
        ),
        operation_label_zh=label,
        family="western_event",
        cpu_bound=True,
        rest_path="/api/astrology/events/" + name.replace("_", "-"),
        cli_request_file=name == "horary_chart",
        default_omit=default_omit,
    )


SPECS: list[ToolSpec] = [
    _western_event_spec(
        "mundane_ingress_chart",
        calculate_mundane,
        "AstroMundaneRequest",
        "世俗入宫盘",
        default_omit=(
            "mundane_ingress_chart.calculation_basis.physical_ephemeris_source",
        ),
    ),
    _western_event_spec(
        "planetary_returns",
        calculate_extrareturns,
        "AstroExtraReturnsRequest",
        "多重回归",
        default_omit=(),
    ),
    _western_event_spec(
        "horary_chart",
        calculate_horary,
        "AstroHoraryRequest",
        "卜卦证据",
        default_omit=(
            "calendar_conversion",
            "clock_conversion",
            "analysis_context.radicality_context",
            "horary_chart.calculation_basis",
            "horary_chart.ephemeris_source_identity",
            "horary_chart.rule_profile",
            "horary_chart.planets",
            "horary_chart.significators.querent.house_assignment",
            "horary_chart.significators.querent.house_condition",
            "horary_chart.significators.querent.essential_condition",
            "horary_chart.significators.quesited.house_assignment",
            "horary_chart.significators.quesited.house_condition",
            "horary_chart.significators.quesited.essential_condition",
            "horary_chart.significators.moon_co_significator",
            "horary_chart.fortitudes",
            "horary_chart.fortune",
            "horary_chart.chart_almuten",
            "horary_chart.radicality.clauses",
            "horary_chart.radicality.hour_inputs",
            "horary_chart.radicality.reported_context",
            "horary_chart.moon.motion_basis",
            "horary_chart.perfection.event_history",
            "horary_chart.perfection.lilly_conditions",
        ),
    ),
    _western_event_spec(
        "evaluate_election_time",
        calculate_election,
        "AstroElectionRequest",
        "择日",
        default_omit=(
            "calendar_conversion",
            "clock_conversion",
            "election.calculation_basis.physical_ephemeris_source",
            "election.planets",
            "election.moon.motion_basis",
            "election.marriage_significators",
        ),
    ),
]
