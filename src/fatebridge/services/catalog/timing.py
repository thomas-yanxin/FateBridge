"""Timing tool declarations and domain compact views."""

from __future__ import annotations

from typing import Any

from fatebridge.application.bindings import (
    bind_kwargs,
    bind_person,
    request_model_ref,
    service_ref,
)
from fatebridge.application.domain_validators import resolve_bazi_analysis_time_defaults
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.reproducibility import ReproducibilityPolicy

_TIMING_REQ = "fatebridge.core.requests.timing"
_CAL_REQ = "fatebridge.core.requests.calendar"

calculate_comprehensive_timing = service_ref(
    "fatebridge.services.timing", "calculate_comprehensive_timing"
)
calculate_dayun_analysis = service_ref(
    "fatebridge.services.timing", "calculate_dayun_analysis"
)
calculate_jieqi_timeline_analysis = service_ref(
    "fatebridge.services.timing", "calculate_jieqi_timeline_analysis"
)
calculate_jieqi_year = service_ref(
    "fatebridge.services.calendar_tools", "calculate_jieqi_year"
)
calculate_liunian_analysis = service_ref(
    "fatebridge.services.timing", "calculate_liunian_analysis"
)
calculate_liuri_analysis = service_ref(
    "fatebridge.services.timing", "calculate_liuri_analysis"
)
calculate_liushi_analysis = service_ref(
    "fatebridge.services.timing", "calculate_liushi_analysis"
)
calculate_liuyue_analysis = service_ref(
    "fatebridge.services.timing", "calculate_liuyue_analysis"
)
calculate_nongli_time = service_ref(
    "fatebridge.services.calendar_tools", "calculate_nongli_time"
)

TERM_VIEW = {
    "name",
    "datetime_with_offset",
    "datetime_utc",
    "day_ganzhi",
    "ephemeris_model",
}


def _compact_term(term: dict) -> dict:
    return {key: value for key, value in term.items() if key in TERM_VIEW}


def _compact_solar_term_window(window: dict) -> dict:
    return {
        **window,
        **(
            {"start_term": _compact_term(window["start_term"])}
            if isinstance(window.get("start_term"), dict)
            else {}
        ),
        **(
            {"next_term": _compact_term(window["next_term"])}
            if isinstance(window.get("next_term"), dict)
            else {}
        ),
    }


def _compact_jieqi_nodes(nodes: list[dict]) -> list[dict]:
    return [
        {
            "order": node["order"],
            "jieqi": _compact_term(node["jieqi"]),
            **(
                {
                    "analysis_anchor": node["analysis_anchor"],
                    "liuyue": {"pillar": node["liuyue"]["pillar"]},
                    "liuri": {"pillar": node["liuri"]["pillar"]},
                    "overall_effect": node["overall_effect"],
                }
                if "analysis_anchor" in node
                else {"analysis_anchor_status": node["analysis_anchor_status"]}
            ),
        }
        for node in nodes
    ]


def _compact_liuyue_timeline_nodes(nodes: list[dict]) -> list[dict]:
    compact_nodes: list[dict] = []
    for node in nodes:
        entry = {
            "order": node["order"],
            "gregorian_window": node["gregorian_window"],
            "start_term": _compact_term(node["start_term"]),
            "next_term": _compact_term(node["next_term"]),
        }
        if "analysis_anchor" in node:
            entry["analysis_anchor"] = node["analysis_anchor"]
            entry["liuyue"] = {"pillar": node["liuyue"]["pillar"]}
            if "overall_effect" in node:
                entry["overall_effect"] = node["overall_effect"]
        elif "analysis_anchor_status" in node:
            entry["analysis_anchor_status"] = node["analysis_anchor_status"]
        compact_nodes.append(entry)
    return compact_nodes


def _compact_jieqi_year(result: ServiceResult) -> ServiceResult:
    field = (
        "selected_jieqi"
        if result["analysis_context"]["requested_jieqis"]
        else "jieqi_year"
    )
    return {
        **{
            key: value
            for key, value in result.items()
            if key not in {"jieqi_year", "selected_jieqi"}
        },
        field: [_compact_term(term) for term in result[field]],
    }


def _compact_jieqi_timeline(result: ServiceResult) -> ServiceResult:
    return {
        **result,
        "jieqi_timeline": _compact_jieqi_nodes(result["jieqi_timeline"]),
    }


def _compact_bazi_timing(result: ServiceResult) -> ServiceResult:
    dayun = result.get("dayun")
    compact_dayun = (
        {k: v for k, v in dayun.items() if k != "timing_context"}
        if isinstance(dayun, dict)
        else dayun
    )
    analysis_calendar = result.get("analysis_calendar")
    compact_calendar: Any
    if isinstance(analysis_calendar, dict) and any(
        k in analysis_calendar
        for k in ("analysis_year_jieqi", "liuyue_timeline", "jieqi_timeline")
    ):
        trimmed_calendar = dict(analysis_calendar)
        if isinstance(trimmed_calendar.get("analysis_year_jieqi"), list):
            trimmed_calendar["analysis_year_jieqi"] = [
                _compact_term(term) for term in trimmed_calendar["analysis_year_jieqi"]
            ]
        if isinstance(trimmed_calendar.get("liuyue_timeline"), list):
            trimmed_calendar["liuyue_timeline"] = _compact_liuyue_timeline_nodes(
                trimmed_calendar["liuyue_timeline"]
            )
        if isinstance(trimmed_calendar.get("jieqi_timeline"), list):
            trimmed_calendar["jieqi_timeline"] = _compact_jieqi_nodes(
                trimmed_calendar["jieqi_timeline"]
            )
        compact_calendar = trimmed_calendar
    else:
        compact_calendar = analysis_calendar
    return {
        k: (
            compact_dayun
            if k == "dayun"
            else compact_calendar if k == "analysis_calendar" else v
        )
        for k, v in result.items()
        if k not in {"calendar_context"}
    }


def _compact_timing_period(result: ServiceResult) -> ServiceResult:
    return {
        k: v
        for k, v in result.items()
        if k not in {"calendar_context", "timing_context"}
    }


def _compact_liuyue(result: ServiceResult) -> ServiceResult:
    base = _compact_timing_period(result)
    liuyue = base.get("liuyue")
    if isinstance(liuyue, dict) and isinstance(liuyue.get("solar_term_window"), dict):
        base = {
            **base,
            "liuyue": {
                **liuyue,
                "solar_term_window": _compact_solar_term_window(
                    liuyue["solar_term_window"]
                ),
            },
        }
    timeline = base.get("monthly_timeline")
    if isinstance(timeline, list):
        base = {
            **base,
            "monthly_timeline": [
                (
                    {
                        **entry,
                        "solar_term_window": _compact_solar_term_window(
                            entry["solar_term_window"]
                        ),
                    }
                    if isinstance(entry, dict)
                    and isinstance(entry.get("solar_term_window"), dict)
                    else entry
                )
                for entry in timeline
            ],
        }
    return base


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="bazi_timing",
        bind=bind_person(calculate_comprehensive_timing),
        request_model_loader=request_model_ref(_TIMING_REQ, "TimingAnalysisRequest"),
        summary="时运综合：整合大运（含起运前小运/童限）/流年/流月/流日/流时及全量干支交互。",
        operation_label_zh="时运综合分析",
        family="timing",
        rest_path="/api/bazi/timing",
        cpu_bound=True,
        compact_view=_compact_bazi_timing,
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
    ),
    ToolSpec(
        name="bazi_luck_cycles",
        bind=bind_person(calculate_dayun_analysis),
        request_model_loader=request_model_ref(_TIMING_REQ, "DayunAnalysisRequest"),
        summary="大运时间轴、童限倒计时(X年Y月Z日)与起运前小运；省略日期按 as_of。",
        operation_label_zh="大运分析",
        family="timing",
        rest_path="/api/bazi/timing/luck-cycles",
        cpu_bound=True,
        compact_view=_compact_timing_period,
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
    ),
    ToolSpec(
        name="bazi_yearly_timing",
        bind=bind_person(calculate_liunian_analysis),
        request_model_loader=request_model_ref(_TIMING_REQ, "LiunianAnalysisRequest"),
        summary="流年分析（含十神、刑冲合害破暗合及流年神煞）；多粒度整合用 bazi_timing。",
        operation_label_zh="流年分析",
        family="timing",
        rest_path="/api/bazi/timing/yearly",
        compact_view=_compact_timing_period,
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
        cpu_bound=True,
    ),
    ToolSpec(
        name="bazi_monthly_timing",
        bind=bind_person(calculate_liuyue_analysis),
        request_model_loader=request_model_ref(_TIMING_REQ, "LiuyueAnalysisRequest"),
        summary="十二节换月流月分析（含完整干支交互与神煞）；省略日期按 as_of。",
        operation_label_zh="流月分析",
        family="timing",
        rest_path="/api/bazi/timing/monthly",
        cpu_bound=True,
        compact_view=_compact_liuyue,
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
    ),
    ToolSpec(
        name="bazi_daily_timing",
        bind=bind_person(calculate_liuri_analysis),
        request_model_loader=request_model_ref(_TIMING_REQ, "LiuriAnalysisRequest"),
        summary="流日分析（含早晚子时政策、完整干支交互与神煞）；省略日期按 as_of。",
        operation_label_zh="流日分析",
        family="timing",
        rest_path="/api/bazi/timing/daily",
        cpu_bound=True,
        compact_view=_compact_timing_period,
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
    ),
    ToolSpec(
        name="bazi_hourly_timing",
        bind=bind_person(calculate_liushi_analysis),
        request_model_loader=request_model_ref(_TIMING_REQ, "LiushiAnalysisRequest"),
        summary="流时（时辰）分析（含早晚子时政策与完整干支交互）；省略日期按 as_of。",
        operation_label_zh="流时分析",
        family="timing",
        rest_path="/api/bazi/timing/hourly",
        cpu_bound=True,
        compact_view=_compact_timing_period,
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
    ),
    ToolSpec(
        name="solar_term_timeline",
        bind=bind_person(calculate_jieqi_timeline_analysis),
        request_model_loader=request_model_ref(_TIMING_REQ, "JieqiTimelineRequest"),
        summary="节气时间轴分析。",
        operation_label_zh="节气时间轴分析",
        family="timing",
        rest_path="/api/calendar/solar-term-timeline",
        reproducibility=ReproducibilityPolicy(current_time_fields=("analysis_year",)),
        compact_view=_compact_jieqi_timeline,
        cpu_bound=True,
    ),
    ToolSpec(
        name="solar_terms_for_year",
        bind=bind_kwargs(calculate_jieqi_year),
        request_model_loader=request_model_ref(_CAL_REQ, "JieqiYearRequest"),
        summary="指定年份节气时刻表。",
        operation_label_zh="节气年表",
        family="timing",
        rest_path="/api/calendar/solar-terms",
        compact_view=_compact_jieqi_year,
    ),
    ToolSpec(
        name="lunar_calendar_time",
        bind=bind_kwargs(calculate_nongli_time),
        request_model_loader=request_model_ref(_CAL_REQ, "NongliTimeRequest"),
        summary="由公历日期与时刻换算农历、节气及干支上下文。",
        operation_label_zh="农历时间",
        family="timing",
        rest_path="/api/calendar/lunar-time",
    ),
]
