"""Timing tool declarations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fatebridge.application.bindings import (
    bind_kwargs,
    bind_person,
    request_model_ref,
    service_ref,
)
from fatebridge.application.domain_validators import resolve_bazi_analysis_time_defaults
from fatebridge.application.tool_spec import (
    OutputContractError,
    ServiceResult,
    ToolSpec,
)
from fatebridge.core.reproducibility import ReproducibilityPolicy

if TYPE_CHECKING:
    from pydantic import BaseModel

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


def _validate_jieqi_year_output(
    _spec: ToolSpec,
    result: ServiceResult,
    request: BaseModel | None,
) -> None:
    analysis_context = result.get("analysis_context")
    requested_jieqis = (
        getattr(request, "jieqis", None)
        if request is not None
        else (
            analysis_context.get("requested_jieqis")
            if isinstance(analysis_context, dict)
            else None
        )
    )
    if requested_jieqis:
        if "jieqi_year" in result:
            raise OutputContractError("筛选节气请求不得重复输出全量 jieqi_year")
        if not isinstance(result.get("selected_jieqi"), list):
            raise OutputContractError("筛选节气输出缺少 selected_jieqi 列表")
        return
    if "selected_jieqi" in result:
        raise OutputContractError("未筛选节气请求不得重复输出 selected_jieqi")
    jieqi_year = result.get("jieqi_year")
    if not isinstance(jieqi_year, list) or not jieqi_year:
        raise OutputContractError("全年节气输出缺少 jieqi_year 列表")


_ANALYSIS_DATE_CONTEXT_OMIT: tuple[str, ...] = (
    "analysis_calendar.analysis_date_context.current_solar_term.civil_point",
    "analysis_calendar.analysis_date_context.current_solar_term.comparison_policy",
    "analysis_calendar.analysis_date_context.next_solar_term.civil_point",
    "analysis_calendar.analysis_date_context.next_solar_term.comparison_policy",
    "analysis_calendar.analysis_date_context.bazi_month_boundary.start_term.civil_point",
    "analysis_calendar.analysis_date_context.bazi_month_boundary.start_term.comparison_policy",
    "analysis_calendar.analysis_date_context.bazi_month_boundary.next_term.civil_point",
    "analysis_calendar.analysis_date_context.bazi_month_boundary.next_term.comparison_policy",
    "analysis_calendar.analysis_date_context.lunar_calendar.previous_jieqi",
    "analysis_calendar.analysis_date_context.lunar_calendar.next_jieqi",
)

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
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
        default_omit=(
            "calendar_context",
            "interaction_analysis",
            "combined_effects",
            "dayun.timing_context",
            "dayun.element_effects",
            "dayun.natal_relations",
            "dayun.shensha",
            "liunian.element_effects",
            "liuyue.detailed_analysis",
            "liuri.detailed_analysis",
            "liushi.detailed_analysis",
            *_ANALYSIS_DATE_CONTEXT_OMIT,
            "analysis_calendar.analysis_year_jieqi.*.civil_point",
            "analysis_calendar.analysis_year_jieqi.*.comparison_policy",
            "analysis_calendar.liuyue_timeline.*.start_term.civil_point",
            "analysis_calendar.liuyue_timeline.*.start_term.comparison_policy",
            "analysis_calendar.liuyue_timeline.*.next_term.civil_point",
            "analysis_calendar.liuyue_timeline.*.next_term.comparison_policy",
            "analysis_calendar.jieqi_timeline.*.jieqi.civil_point",
            "analysis_calendar.jieqi_timeline.*.jieqi.comparison_policy",
        ),
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
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
        default_omit=("calendar_context", "timing_context"),
    ),
    ToolSpec(
        name="bazi_yearly_timing",
        bind=bind_person(calculate_liunian_analysis),
        request_model_loader=request_model_ref(_TIMING_REQ, "LiunianAnalysisRequest"),
        summary="流年分析（含十神、刑冲合害破暗合及流年神煞）；多粒度整合用 bazi_timing。",
        operation_label_zh="流年分析",
        family="timing",
        rest_path="/api/bazi/timing/yearly",
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
        cpu_bound=True,
        default_omit=("calendar_context",),
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
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
        default_omit=(
            "calendar_context",
            *_ANALYSIS_DATE_CONTEXT_OMIT,
            "liuyue.solar_term_window.start_term.civil_point",
            "liuyue.solar_term_window.start_term.comparison_policy",
            "liuyue.solar_term_window.next_term.civil_point",
            "liuyue.solar_term_window.next_term.comparison_policy",
            "monthly_timeline.*.solar_term_window.start_term.civil_point",
            "monthly_timeline.*.solar_term_window.start_term.comparison_policy",
            "monthly_timeline.*.solar_term_window.next_term.civil_point",
            "monthly_timeline.*.solar_term_window.next_term.comparison_policy",
        ),
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
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
        default_omit=(
            "calendar_context",
            *_ANALYSIS_DATE_CONTEXT_OMIT,
        ),
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
        resolve_time_defaults=resolve_bazi_analysis_time_defaults,
        default_omit=(
            "calendar_context",
            *_ANALYSIS_DATE_CONTEXT_OMIT,
        ),
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
        cpu_bound=True,
        default_omit=(
            "calendar_context",
            "target_year_jieqi",
            "person_info.time_adjustment",
            "analysis_context.scope",
            "jieqi_timeline.*.jieqi.civil_point",
            "jieqi_timeline.*.jieqi.comparison_policy",
            "jieqi_timeline.*.jieqi.resolution_provider",
            "jieqi_timeline.*.jieqi.timezone",
            "jieqi_timeline.*.jieqi.datetime",
            "jieqi_timeline.*.jieqi.date_key",
            "jieqi_timeline.*.jieqi.utc_offset_seconds",
            "jieqi_timeline.*.jieqi.fold",
            "jieqi_timeline.*.liuyue.stem",
            "jieqi_timeline.*.liuri.stem",
            "jieqi_timeline.*.liuri.branch",
        ),
    ),
    ToolSpec(
        name="solar_terms_for_year",
        bind=bind_kwargs(calculate_jieqi_year),
        request_model_loader=request_model_ref(_CAL_REQ, "JieqiYearRequest"),
        required_output_fields=("analysis_context", "year"),
        required_output_validator=_validate_jieqi_year_output,
        summary="指定年份节气时刻表。",
        operation_label_zh="节气年表",
        family="timing",
        rest_path="/api/calendar/solar-terms",
        default_omit=(
            "jieqi_year.*.civil_point",
            "jieqi_year.*.comparison_policy",
            "selected_jieqi.*.civil_point",
            "selected_jieqi.*.comparison_policy",
        ),
    ),
    ToolSpec(
        name="lunar_calendar_time",
        bind=bind_kwargs(calculate_nongli_time),
        request_model_loader=request_model_ref(_CAL_REQ, "NongliTimeRequest"),
        summary="由公历日期与时刻换算农历、节气及干支上下文。",
        operation_label_zh="农历时间",
        family="timing",
        rest_path="/api/calendar/lunar-time",
        default_omit=("calendar_context", "lunar_calendar.meihua"),
    ),
]
