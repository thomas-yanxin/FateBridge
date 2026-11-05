"""Timing tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import List

from fatebridge.application.bindings import lazy_service, person_invoke, raw_invoke
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.method_contracts import LIFE_DIMENSION_INDEX
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

calculate_comprehensive_timing = lazy_service(
    "fatebridge.services.timing", "calculate_comprehensive_timing"
)


calculate_dayun_analysis = lazy_service(
    "fatebridge.services.timing", "calculate_dayun_analysis"
)


calculate_jieqi_timeline_analysis = lazy_service(
    "fatebridge.services.timing", "calculate_jieqi_timeline_analysis"
)


calculate_jieqi_year = lazy_service(
    "fatebridge.services.calendar_tools", "calculate_jieqi_year"
)


calculate_liunian_analysis = lazy_service(
    "fatebridge.services.timing", "calculate_liunian_analysis"
)


calculate_liuri_analysis = lazy_service(
    "fatebridge.services.timing", "calculate_liuri_analysis"
)


calculate_liushi_analysis = lazy_service(
    "fatebridge.services.timing", "calculate_liushi_analysis"
)


calculate_liuyue_analysis = lazy_service(
    "fatebridge.services.timing", "calculate_liuyue_analysis"
)


calculate_nongli_time = lazy_service(
    "fatebridge.services.calendar_tools", "calculate_nongli_time"
)

SPECS: List[ToolSpec] = [
    # --- Timing ------------------------------------------------------------
    ToolSpec(
        key="timing_analysis",
        bind=person_invoke(calculate_comprehensive_timing),
        request_model=TimingAnalysisRequest,
        summary=(
            "时运综合分析：一次性给出大运/流年/流月等多粒度的整合影响，想要全景时用它；"
            "只需单一粒度请用对应的 dayun/liunian/liuyue/liuri/liushi_analysis。"
            "分析日期全省略时用as_of/执行开始的完整当地瞬间，实际时刻与补齐来源见analysis_reference。"
        ),
        operation_label_zh="时运综合分析",
        family="timing",
        rest_path="/api/timing/comprehensive",
        mcp_name="timing_analysis",
        cpu_bound=True,
    ),
    ToolSpec(
        key="dayun_analysis",
        bind=person_invoke(calculate_dayun_analysis),
        request_model=DayunAnalysisRequest,
        summary="大运交运时间轴与当前运：日期全省略时按as_of/执行开始的完整当地瞬间选运；analysis_age仅作显式年龄参考。analysis_reference记录实际时刻与补齐来源。要多粒度整合用 timing_analysis。",
        operation_label_zh="大运分析",
        family="timing",
        rest_path="/api/timing/dayun",
        mcp_name="dayun_analysis",
        cpu_bound=True,
    ),
    ToolSpec(
        key="liunian_analysis",
        bind=person_invoke(calculate_liunian_analysis),
        request_model=LiunianAnalysisRequest,
        summary="单看某一流年的运势影响；要多粒度整合用 timing_analysis。",
        operation_label_zh="流年分析",
        family="timing",
        rest_path="/api/timing/liunian",
        mcp_name="liunian_analysis",
        cpu_bound=True,
    ),
    ToolSpec(
        key="liuyue_analysis",
        bind=person_invoke(calculate_liuyue_analysis),
        request_model=LiuyueAnalysisRequest,
        summary="单看流月影响；日期全省略时用as_of/当前完整当地瞬间，显式部分日期仍缺日取15，见analysis_reference。solar_term_window是十二节换月窗口；二十四节气见analysis_calendar.analysis_date_context。要多粒度整合用 timing_analysis。",
        operation_label_zh="流月分析",
        family="timing",
        rest_path="/api/timing/liuyue",
        mcp_name="liuyue_analysis",
        cpu_bound=True,
    ),
    ToolSpec(
        key="liuri_analysis",
        bind=person_invoke(calculate_liuri_analysis),
        request_model=LiuriAnalysisRequest,
        summary="单看流日影响；日期全省略时用as_of/当前完整当地瞬间，保留晚子时换日；实际时刻与补齐见analysis_reference。底层solar_term_window是十二节换月窗口；二十四节气见analysis_calendar.analysis_date_context。要多粒度整合用 timing_analysis。",
        operation_label_zh="流日分析",
        family="timing",
        rest_path="/api/timing/liuri",
        mcp_name="liuri_analysis",
        cpu_bound=True,
    ),
    ToolSpec(
        key="liushi_analysis",
        bind=person_invoke(calculate_liushi_analysis),
        request_model=LiushiAnalysisRequest,
        methods=(LIFE_DIMENSION_INDEX,),
        summary="单看流时（时辰）影响；日期全省略时用as_of/当前完整当地瞬间，实际时刻与补齐见analysis_reference。时柱整点缓存不代替交气比较时刻。要多粒度整合用 timing_analysis。",
        operation_label_zh="流时分析",
        family="timing",
        rest_path="/api/timing/liushi",
        mcp_name="liushi_analysis",
        cpu_bound=True,
    ),
    ToolSpec(
        key="jieqi_timeline_analysis",
        bind=person_invoke(calculate_jieqi_timeline_analysis),
        request_model=JieqiTimelineRequest,
        summary="节气时间轴分析。",
        operation_label_zh="节气时间轴分析",
        family="timing",
        rest_path="/api/timing/jieqi",
        mcp_name="jieqi_timeline_analysis",
        cpu_bound=True,
    ),
    ToolSpec(
        key="jieqi_year",
        bind=raw_invoke(calculate_jieqi_year),
        request_model=JieqiYearRequest,
        summary="指定年份节气时刻表。",
        operation_label_zh="节气年表",
        family="timing",
        rest_path="/api/cn/jieqi/year",
        mcp_name="jieqi_year",
    ),
    ToolSpec(
        key="nongli_time",
        bind=raw_invoke(calculate_nongli_time),
        request_model=NongliTimeRequest,
        summary="公历↔农历时间换算与干支。",
        operation_label_zh="农历时间",
        family="timing",
        rest_path="/api/cn/nongli/time",
        mcp_name="nongli_time",
    ),
]
