"""Western events tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import (
    ServiceRef,
    bind_kwargs,
    request_model_ref,
    service_ref,
)
from fatebridge.application.tool_spec import CompactView, ServiceResult, ToolSpec

_REQ_MODULE = "fatebridge.core.requests.western_events"


def _compact_horary(result: ServiceResult) -> ServiceResult:
    horary = result.get("horary_chart")
    if not isinstance(horary, dict):
        return result
    moon = horary.get("moon") or {}
    rad = horary.get("radicality") or {}
    fort = horary.get("fortitudes") or {}
    perf = horary.get("perfection") or {}
    fort_planets = fort.get("planets") or {}
    fort_summary = {
        p: {
            k: v
            for k, v in data.items()
            if k
            in {
                "net_score",
                "essential_score",
                "accidental_score",
                "total_fortitude",
                "total_debility",
            }
        }
        for p, data in fort_planets.items()
        if isinstance(data, dict)
    }
    compact_horary = {
        "system": horary.get("system"),
        "category": horary.get("category"),
        "quesited_house": horary.get("quesited_house"),
        "turned_from_house": horary.get("turned_from_house"),
        "turned_house": horary.get("turned_house"),
        "ascendant": horary.get("ascendant"),
        "significators": horary.get("significators"),
        "moon": {
            "sign": moon.get("sign"),
            "speed": moon.get("speed"),
            "void_of_course": moon.get("void_of_course"),
            "degrees_left_in_sign": moon.get("degrees_left_in_sign"),
            "next_aspect": moon.get("next_aspect"),
        },
        "radicality": {
            "safe_to_judge": rad.get("safe_to_judge"),
            "status": rad.get("status"),
            "hour_affinity": rad.get("hour_affinity"),
            "strictures": rad.get("strictures"),
            "ascendant_degree_gate": rad.get("ascendant_degree_gate"),
        },
        "fortitudes": {
            "summary": fort_summary,
            "balance": fort.get("balance"),
        },
        "fortune": horary.get("fortune"),
        "chart_almuten": horary.get("chart_almuten"),
        "antiscia_contacts": horary.get("antiscia_contacts"),
        "perfection": {
            "perfected": perf.get("perfected"),
            "status": perf.get("status"),
            "perfection_routes": perf.get("perfection_routes"),
            "obstructions": perf.get("obstructions"),
        },
    }
    return {
        "analysis_type": result.get("analysis_type"),
        "analysis_context": result.get("analysis_context"),
        "horary_chart": compact_horary,
        "summary": result.get("summary"),
        **(
            {"run_metadata": result["run_metadata"]} if "run_metadata" in result else {}
        ),
    }


def _compact_election(result: ServiceResult) -> ServiceResult:
    el = result.get("election")
    if not isinstance(el, dict):
        return result
    moon = el.get("moon") or {}
    compact_el = {
        "topic_id": el.get("topic_id"),
        "topic_house": el.get("topic_house"),
        "significator": el.get("significator"),
        "ascendant": el.get("ascendant"),
        "moon": {
            "sign": moon.get("sign"),
            "void_of_course": moon.get("void_of_course"),
            "next_applying_aspect": moon.get("next_applying_aspect"),
            "phase": moon.get("phase"),
            "solar_condition": moon.get("solar_condition"),
        },
        "planetary_hour_match": el.get("planetary_hour_match"),
        "planetary_hour": el.get("planetary_hour"),
        "factors": el.get("factors"),
        "unresolved_factors": el.get("unresolved_factors"),
        **(
            {"candidate_windows": el["candidate_windows"]}
            if "candidate_windows" in el
            else {}
        ),
    }
    return {
        "analysis_type": result.get("analysis_type"),
        "analysis_context": result.get("analysis_context"),
        "election": compact_el,
        "summary": result.get("summary"),
        **(
            {"run_metadata": result["run_metadata"]} if "run_metadata" in result else {}
        ),
    }


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
    compact_view: CompactView | None = None,
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
        compact_view=compact_view,
    )


SPECS: list[ToolSpec] = [
    _western_event_spec(
        "mundane_ingress_chart",
        calculate_mundane,
        "AstroMundaneRequest",
        "世俗入宫盘",
    ),
    _western_event_spec(
        "planetary_returns",
        calculate_extrareturns,
        "AstroExtraReturnsRequest",
        "多重回归",
    ),
    _western_event_spec(
        "horary_chart",
        calculate_horary,
        "AstroHoraryRequest",
        "卜卦证据",
        compact_view=_compact_horary,
    ),
    _western_event_spec(
        "evaluate_election_time",
        calculate_election,
        "AstroElectionRequest",
        "择日",
        compact_view=_compact_election,
    ),
]
