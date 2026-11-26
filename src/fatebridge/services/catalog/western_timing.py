"""Western timing tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import bind_kwargs, service_ref
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.western_timing import (
    WesternFirdariaRequest,
    WesternPrimaryDirectionsChartRequest,
    WesternPrimaryDirectionsRequest,
    WesternReturnTimingRequest,
    WesternTimingBaseRequest,
    WesternTimingRequest,
)

calculate_western_timing_analysis = service_ref(
    "fatebridge.services.western_timing", "calculate_western_timing_analysis"
)


calculate_timing_tool = service_ref(
    "fatebridge.services.western_timing_tools", "calculate_timing_tool"
)


def _western_module_spec(
    name: str,
    label: str,
    *,
    request_model: type[WesternTimingBaseRequest] = WesternTimingBaseRequest,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        bind=bind_kwargs(calculate_timing_tool, fixed={"tool_name": name}),
        request_model=request_model,
        summary=(
            f"{label}：西占行运的单项技法，读取本命盘+目标时刻只算这一种。"
            "想一次拿到多项行运的整合结果，改用聚合工具 western_timing。"
        ),
        operation_label_zh=label,
        family="western_timing",
        cpu_bound=True,
        rest_path="/api/astrology/timing/" + name.replace("_", "-"),
    )


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="western_timing",
        bind=bind_kwargs(calculate_western_timing_analysis),
        request_model=WesternTimingRequest,
        summary=(
            "西占预测时运的聚合分析：一次整合多种行运技法（返照/行运/太阳弧/小限/法达等）；"
            "只要单一技法请用对应的 solar_return、transit_chart 等工具。"
        ),
        operation_label_zh="西占时运",
        family="western_timing",
        cpu_bound=True,
        rest_path="/api/astrology/timing",
    ),
    _western_module_spec(
        "solar_return", "西占太阳返照", request_model=WesternReturnTimingRequest
    ),
    _western_module_spec(
        "lunar_return", "西占月亮返照", request_model=WesternReturnTimingRequest
    ),
    _western_module_spec("transit_chart", "西占行运盘"),
    _western_module_spec("solar_arc", "西占太阳弧"),
    _western_module_spec("chart_for_year", "西占指定年盘"),
    _western_module_spec("profection", "西占年小限"),
    _western_module_spec(
        "primary_directions",
        "西占主限",
        request_model=WesternPrimaryDirectionsRequest,
    ),
    _western_module_spec(
        "primary_directions_chart",
        "西占主限法盘",
        request_model=WesternPrimaryDirectionsChartRequest,
    ),
    _western_module_spec("zodiacal_releasing", "西占黄道释放"),
    _western_module_spec(
        "firdaria", "西占法达星限", request_model=WesternFirdariaRequest
    ),
    _western_module_spec("decennials", "西占十年星限"),
]
