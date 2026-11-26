"""Western timing tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import bind_kwargs, request_model_ref, service_ref
from fatebridge.application.tool_spec import CompactView, ServiceResult, ToolSpec

_REQ_MODULE = "fatebridge.core.requests.western_timing"

calculate_western_timing_analysis = service_ref(
    "fatebridge.services.western_timing", "calculate_western_timing_analysis"
)


calculate_timing_tool = service_ref(
    "fatebridge.services.western_timing_tools", "calculate_timing_tool"
)


_DECENNIAL_PERIOD_FIELDS = frozenset(
    {
        "key",
        "level",
        "planet",
        "planet_label",
        "date",
        "nominal",
        "start",
        "end",
        "active",
    }
)


def _compact_decennial_period(period: ServiceResult | None) -> ServiceResult | None:
    if period is None:
        return None
    return {
        key: value for key, value in period.items() if key in _DECENNIAL_PERIOD_FIELDS
    }


def _compact_decennials(result: ServiceResult) -> ServiceResult:
    decennials = result["decennials"]
    return {
        **result,
        "decennials": {
            **decennials,
            "current_level_1": _compact_decennial_period(decennials["current_level_1"]),
            "current_level_2": _compact_decennial_period(decennials["current_level_2"]),
            "current_level_3": _compact_decennial_period(decennials["current_level_3"]),
        },
    }


def _western_module_spec(
    name: str,
    label: str,
    *,
    request_model_name: str = "WesternTimingBaseRequest",
    compact_view: CompactView | None = None,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        bind=bind_kwargs(calculate_timing_tool, fixed={"tool_name": name}),
        request_model_loader=request_model_ref(_REQ_MODULE, request_model_name),
        summary=f"{label}：单项西占行运（整合用 western_timing）。",
        operation_label_zh=label,
        family="western_timing",
        cpu_bound=True,
        rest_path="/api/astrology/timing/" + name.replace("_", "-"),
        compact_view=compact_view,
    )


SPECS: list[ToolSpec] = [
    ToolSpec(
        name="western_timing",
        bind=bind_kwargs(calculate_western_timing_analysis),
        request_model_loader=request_model_ref(_REQ_MODULE, "WesternTimingRequest"),
        summary="西占时运聚合分析：整合返照/行运/太阳弧/小限/法达；单项用对应工具。",
        operation_label_zh="西占时运",
        family="western_timing",
        cpu_bound=True,
        rest_path="/api/astrology/timing",
    ),
    _western_module_spec(
        "solar_return", "西占太阳返照", request_model_name="WesternReturnTimingRequest"
    ),
    _western_module_spec(
        "lunar_return", "西占月亮返照", request_model_name="WesternReturnTimingRequest"
    ),
    _western_module_spec("transit_chart", "西占行运盘"),
    _western_module_spec("solar_arc", "西占太阳弧"),
    _western_module_spec("chart_for_year", "西占指定年盘"),
    _western_module_spec("profection", "西占年小限"),
    _western_module_spec(
        "primary_directions",
        "西占主限",
        request_model_name="WesternPrimaryDirectionsRequest",
    ),
    _western_module_spec(
        "primary_directions_chart",
        "西占主限法盘",
        request_model_name="WesternPrimaryDirectionsChartRequest",
    ),
    _western_module_spec("zodiacal_releasing", "西占黄道释放"),
    _western_module_spec(
        "firdaria", "西占法达星限", request_model_name="WesternFirdariaRequest"
    ),
    _western_module_spec(
        "decennials", "西占十年星限", compact_view=_compact_decennials
    ),
]
