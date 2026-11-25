"""Western timing tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import lazy_service, raw_invoke
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.western_timing import (
    WesternTimingModuleRequest,
    WesternTimingRequest,
)

calculate_western_timing_analysis = lazy_service(
    "fatebridge.services.western_timing", "calculate_western_timing_analysis"
)


calculate_timing_tool = lazy_service(
    "fatebridge.services.western_timing_tools", "calculate_timing_tool"
)


def _western_module_spec(
    tool_name: str, label: str, *, key: str | None = None
) -> ToolSpec:
    key = key or tool_name
    return ToolSpec(
        key=key,
        bind=raw_invoke(calculate_timing_tool, fixed={"tool_name": key}),
        request_model=WesternTimingModuleRequest,
        summary=(
            f"{label}：西占行运的单项技法，读取本命盘+目标时刻只算这一种。"
            f"想一次拿到多项行运的整合结果，改用聚合工具 western_timing。"
            "（本族 11 个西占时运工具共用 WesternTimingModuleRequest，"
            "schema 中部分参数仅对特定技法生效，与本工具无关的可忽略。）"
        ),
        operation_label_zh=label,
        family="western_timing_tool",
        cpu_bound=True,
        include_snapshot_text=False,
        optional_snapshot=True,
        rest_path="/api/astrology/timing/" + tool_name.replace("_", "-"),
        mcp_name=tool_name,
    )


SPECS: list[ToolSpec] = [
    ToolSpec(
        key="western_timing_analysis",
        bind=raw_invoke(calculate_western_timing_analysis),
        request_model=WesternTimingRequest,
        summary=(
            "西占预测时运的聚合分析：一次整合多种行运技法（返照/行运/太阳弧/小限/法达等）；"
            "只要单一技法请用对应的 solar_return、transit_chart 等工具。"
        ),
        operation_label_zh="西占时运",
        family="western_timing",
        cpu_bound=True,
        rest_path="/api/astrology/timing",
        mcp_name="western_timing",
    ),
    _western_module_spec("solar_return", "西占太阳返照", key="solarreturn"),
    _western_module_spec("lunar_return", "西占月亮返照", key="lunarreturn"),
    _western_module_spec("transit_chart", "西占行运盘", key="transit"),
    _western_module_spec("solar_arc", "西占太阳弧", key="solararc"),
    _western_module_spec("chart_for_year", "西占指定年盘", key="givenyear"),
    _western_module_spec("profection", "西占年小限"),
    _western_module_spec("primary_directions", "西占主限", key="pd"),
    _western_module_spec("primary_directions_chart", "西占主限法盘", key="pdchart"),
    _western_module_spec("zodiacal_releasing", "西占黄道释放", key="zr"),
    _western_module_spec("firdaria", "西占法达星限"),
    _western_module_spec("decennials", "西占十年星限"),
]
