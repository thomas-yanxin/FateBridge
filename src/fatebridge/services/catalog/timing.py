"""Timing tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import bind_kwargs, bind_person, service_ref
from fatebridge.application.domain_validators import resolve_bazi_analysis_time_defaults
from fatebridge.application.tool_spec import ServiceResult, ToolSpec
from fatebridge.core.reproducibility import ReproducibilityPolicy
from fatebridge.core.requests.calendar import JieqiYearRequest, NongliTimeRequest
from fatebridge.core.requests.timing import (
    DayunAnalysisRequest,
    JieqiTimelineRequest,
    LiunianAnalysisRequest,
    LiuriAnalysisRequest,
    LiushiAnalysisRequest,
    LiuyueAnalysisRequest,
    TimingAnalysisRequest,
)

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


def _compact_jieqi_year(result: ServiceResult) -> ServiceResult:
    field = (
        "selected_jieqi"
        if result["query_context"]["requested_jieqis"]
        else "jieqi_year"
    )
    return {
        **{
            key: value
            for key, value in result.items()
            if key not in {"jieqi_year", "selected_jieqi"}
        },
        field: [
            {key: value for key, value in term.items() if key in TERM_VIEW}
            for term in result[field]
        ],
    }


def _compact_jieqi_timeline(result: ServiceResult) -> ServiceResult:
    return {
        **result,
        "jieqi_timeline": [
            {
                "order": node["order"],
                "jieqi": {
                    key: value
                    for key, value in node["jieqi"].items()
                    if key in TERM_VIEW
                },
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
            for node in result["jieqi_timeline"]
        ],
    }


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="bazi_timing",
        bind=bind_person(calculate_comprehensive_timing),
        request_model=TimingAnalysisRequest,
        summary="时运综合：整合大运/流年/流月/流日/流时；单项用对应时机或 bazi_luck_cycles。",
        operation_label_zh="时运综合分析",
        family="timing",
        rest_path="/api/bazi/timing",
        cpu_bound=True,
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
    ),
    ToolSpec(
        name="bazi_luck_cycles",
        bind=bind_person(calculate_dayun_analysis),
        request_model=DayunAnalysisRequest,
        summary="大运时间轴与当前运；省略日期按 as_of，多粒度整合用 bazi_timing。",
        operation_label_zh="大运分析",
        family="timing",
        rest_path="/api/bazi/timing/luck-cycles",
        cpu_bound=True,
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
    ),
    ToolSpec(
        name="bazi_yearly_timing",
        bind=bind_person(calculate_liunian_analysis),
        request_model=LiunianAnalysisRequest,
        summary="单看某一流年的运势影响；要多粒度整合用 bazi_timing。",
        operation_label_zh="流年分析",
        family="timing",
        rest_path="/api/bazi/timing/yearly",
        cpu_bound=True,
    ),
    ToolSpec(
        name="bazi_monthly_timing",
        bind=bind_person(calculate_liuyue_analysis),
        request_model=LiuyueAnalysisRequest,
        summary="十二节换月流月分析；省略日期按 as_of，多粒度用 bazi_timing。",
        operation_label_zh="流月分析",
        family="timing",
        rest_path="/api/bazi/timing/monthly",
        cpu_bound=True,
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
    ),
    ToolSpec(
        name="bazi_daily_timing",
        bind=bind_person(calculate_liuri_analysis),
        request_model=LiuriAnalysisRequest,
        summary="流日分析（含晚子时换日）；省略日期按 as_of，多粒度用 bazi_timing。",
        operation_label_zh="流日分析",
        family="timing",
        rest_path="/api/bazi/timing/daily",
        cpu_bound=True,
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
    ),
    ToolSpec(
        name="bazi_hourly_timing",
        bind=bind_person(calculate_liushi_analysis),
        request_model=LiushiAnalysisRequest,
        summary="流时（时辰）分析；省略日期按 as_of，多粒度用 bazi_timing。",
        operation_label_zh="流时分析",
        family="timing",
        rest_path="/api/bazi/timing/hourly",
        cpu_bound=True,
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
    ),
    ToolSpec(
        name="solar_term_timeline",
        bind=bind_person(calculate_jieqi_timeline_analysis),
        request_model=JieqiTimelineRequest,
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
        request_model=JieqiYearRequest,
        summary="指定年份节气时刻表。",
        operation_label_zh="节气年表",
        family="timing",
        rest_path="/api/calendar/solar-terms",
        compact_view=_compact_jieqi_year,
    ),
    ToolSpec(
        name="lunar_calendar_time",
        bind=bind_kwargs(calculate_nongli_time),
        request_model=NongliTimeRequest,
        summary="由公历日期与时刻换算农历、节气及干支上下文。",
        operation_label_zh="农历时间",
        family="timing",
        rest_path="/api/calendar/lunar-time",
    ),
]
