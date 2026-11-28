"""Western timing tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import bind_kwargs, request_model_ref, service_ref
from fatebridge.application.tool_spec import ToolSpec

_REQ_MODULE = "fatebridge.core.requests.western_timing"

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
    request_model_name: str = "WesternTimingBaseRequest",
    default_omit: tuple[str, ...] = (),
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
        default_omit=default_omit,
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
        default_omit=(
            "natal_reference",
            "returns.solar_return.calculation_basis",
            "returns.lunar_return",
            "transits.current_transit.calculation_basis",
            "transits.current_transit.transit_reference",
            "transits.current_transit.location",
            "directions.given_year",
            "directions.secondary_progression",
            "directions.solar_arc",
            "directions.primary_directions",
            "directions.primary_direction_chart",
            "time_lords.zodiacal_releasing",
            "time_lords.decennials",
        ),
    ),
    _western_module_spec(
        "solar_return",
        "西占太阳返照",
        request_model_name="WesternReturnTimingRequest",
        default_omit=(
            "natal_reference",
            "solar_return.calculation_basis.physical_ephemeris_source",
        ),
    ),
    _western_module_spec(
        "lunar_return",
        "西占月亮返照",
        request_model_name="WesternReturnTimingRequest",
        default_omit=(
            "natal_reference",
            "lunar_return.calculation_basis.physical_ephemeris_source",
        ),
    ),
    _western_module_spec(
        "transit_chart",
        "西占行运盘",
        request_model_name="WesternTransitRequest",
        default_omit=(
            "natal_reference",
            "transit_chart.natal_reference",
            "transit_chart.transit_reference",
            "transit_chart.calculation_basis.physical_ephemeris_source",
        ),
    ),
    _western_module_spec(
        "solar_arc",
        "西占太阳弧",
        request_model_name="WesternAspectTimingRequest",
        default_omit=("natal_reference",),
    ),
    _western_module_spec(
        "chart_for_year",
        "西占指定年盘",
        request_model_name="WesternAspectTimingRequest",
        default_omit=("natal_reference",),
    ),
    _western_module_spec(
        "profection",
        "西占年小限",
        default_omit=("natal_reference",),
    ),
    _western_module_spec(
        "primary_directions",
        "西占主限",
        request_model_name="WesternPrimaryDirectionsRequest",
        default_omit=(
            "natal_reference",
            "primary_directions.timeline",
            "primary_directions.past_window",
            "primary_directions.future_window",
            "primary_directions.coordinate_diagnostics",
            "primary_directions.coordinate_points",
            "primary_directions.coordinate_lots",
            "primary_directions.current_coordinate_points",
            "primary_directions.current_coordinate_lots",
            "primary_directions.promissors",
            "primary_directions.significators",
        ),
    ),
    _western_module_spec(
        "primary_directions_chart",
        "西占主限法盘",
        request_model_name="WesternPrimaryDirectionsChartRequest",
        default_omit=(
            "natal_reference",
            "primary_directions_chart.coordinate_hits",
            "primary_directions_chart.coordinate_diagnostics",
            "primary_directions_chart.natal_coordinate_points",
            "primary_directions_chart.natal_coordinate_lots",
            "primary_directions_chart.directed_coordinate_points",
            "primary_directions_chart.directed_coordinate_lots",
            "primary_directions_chart.bounds_overlay",
            "primary_directions_chart.directed_lots",
            "primary_directions_chart.sign_changes",
        ),
    ),
    _western_module_spec(
        "zodiacal_releasing",
        "西占黄道释放",
        default_omit=(
            "natal_reference",
            "zodiacal_releasing.*.peak_signs",
            "zodiacal_releasing.*.level_1_timeline",
            "zodiacal_releasing.*.level_2_timeline",
            "zodiacal_releasing.*.level_3_timeline",
            "zodiacal_releasing.*.level_4_timeline",
        ),
    ),
    _western_module_spec(
        "firdaria",
        "西占法达星限",
        request_model_name="WesternFirdariaRequest",
        default_omit=("natal_reference", "firdaria.timeline"),
    ),
    _western_module_spec(
        "decennials",
        "西占十年星限",
        default_omit=(
            "natal_reference",
            "decennials.timeline",
            "decennials.current_level_1.sublevel",
            "decennials.current_level_2.sublevel",
            "decennials.current_level_3.sublevel",
        ),
    ),
]
