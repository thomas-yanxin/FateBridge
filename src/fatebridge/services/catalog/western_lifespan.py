"""Western lifespan tool declarations and domain binding helpers."""

from __future__ import annotations

from pydantic import BaseModel

from fatebridge.application.bindings import LazyService, lazy_service, raw_invoke
from fatebridge.application.tool_spec import ToolSpec
from fatebridge.core.requests.western_lifespan import (
    AstroAgePointRequest,
    AstroBalbillusRequest,
    AstroDistributionsRequest,
    AstroHarmonicRequest,
    AstroJaynesProgRequest,
    AstroKeypointsRequest,
    AstroLunationPhaseRequest,
    AstroPersianDirectedRequest,
    AstroPlanetaryAgesRequest,
    AstroPlanetaryArcRequest,
    AstroTriplicityRulersRequest,
    AstroVedicProgRequest,
    AstroYearSystem129Request,
)

calculate_age_point = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_age_point"
)


calculate_balbillus = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_balbillus"
)


calculate_distributions = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_distributions"
)


calculate_harmonic_chart = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_harmonic_chart"
)


calculate_jaynesprog = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_jaynesprog"
)


calculate_keypoints = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_keypoints"
)


calculate_lunation_phase = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_lunation_phase"
)


calculate_persian_directed = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_persian_directed"
)


calculate_planetary_ages = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_planetary_ages"
)


calculate_planetary_arc = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_planetary_arc"
)


calculate_triplicity_rulers = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_triplicity_rulers"
)


calculate_vedicprog = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_vedicprog"
)


calculate_yearsystem129 = lazy_service(
    "fatebridge.services.western_lifespan", "calculate_yearsystem129"
)


def _western_lifespan_spec(
    name: str,
    tool_name: str,
    service: LazyService,
    model: type[BaseModel],
    label: str,
    *,
    summary: str | None = None,
    rest_path: str | None = None,
) -> ToolSpec:
    """Register a single-natal-chart western lifespan technique tool."""
    return ToolSpec(
        key=f"astro_{name}",
        bind=raw_invoke(service),
        request_model=model,
        summary=summary
        or (
            f"{label}：只读单张本命盘的古典「全生命周期」技法（不需目标时刻），"
            f"输出按年龄/时段划分的人生阶段。"
        ),
        operation_label_zh=label,
        family="western_lifespan",
        cpu_bound=True,
        rest_path=rest_path or "/api/astrology/timing/" + tool_name.replace("_", "-"),
        mcp_name=tool_name,
    )


SPECS: list[ToolSpec] = [
    # --- Western lifespan techniques (single natal chart, whole-life) ------
    _western_lifespan_spec(
        "harmonic",
        "harmonic_chart",
        calculate_harmonic_chart,
        AstroHarmonicRequest,
        "调波盘",
        rest_path="/api/astrology/harmonic-chart",
    ),
    _western_lifespan_spec(
        "planetary_ages",
        "planetary_ages",
        calculate_planetary_ages,
        AstroPlanetaryAgesRequest,
        "行星年龄",
    ),
    _western_lifespan_spec(
        "triplicity_rulers",
        "triplicity_ruler_periods",
        calculate_triplicity_rulers,
        AstroTriplicityRulersRequest,
        "三分主星推运",
    ),
    _western_lifespan_spec(
        "lunation_phase",
        "lunar_phase_progressions",
        calculate_lunation_phase,
        AstroLunationPhaseRequest,
        "月相推运",
        summary=(
            "月相推运：按出生后实际日月星历搜索八相交点，"
            "以一名义UTC日对应一象征年龄年，返回出生后至年龄上限内的转换。"
            "星历与时间钥随结果交付；年龄范围不是寿命估计。"
        ),
    ),
    _western_lifespan_spec(
        "distributions",
        "bounds_directions",
        calculate_distributions,
        AstroDistributionsRequest,
        "界推运",
    ),
    _western_lifespan_spec(
        "balbillus",
        "balbillus_periods",
        calculate_balbillus,
        AstroBalbillusRequest,
        "Balbillus 129年系统",
    ),
    _western_lifespan_spec(
        "keypoints",
        "numeric_aspect_periods",
        calculate_keypoints,
        AstroKeypointsRequest,
        "数字相位推运",
    ),
    _western_lifespan_spec(
        "yearsystem129",
        "planetary_periods_129_years",
        calculate_yearsystem129,
        AstroYearSystem129Request,
        "129年系统",
    ),
    _western_lifespan_spec(
        "planetaryarc",
        "planetary_arc_directions",
        calculate_planetary_arc,
        AstroPlanetaryArcRequest,
        "行星弧方向",
    ),
    _western_lifespan_spec(
        "persiandirected",
        "persian_directions",
        calculate_persian_directed,
        AstroPersianDirectedRequest,
        "波斯向运",
    ),
    _western_lifespan_spec(
        "agepoint",
        "age_point",
        calculate_age_point,
        AstroAgePointRequest,
        "年龄推进点",
    ),
    _western_lifespan_spec(
        "vedicprog",
        "sidereal_progressions",
        calculate_vedicprog,
        AstroVedicProgRequest,
        "恒星推运",
    ),
    _western_lifespan_spec(
        "jaynesprog",
        "declination_progressions",
        calculate_jaynesprog,
        AstroJaynesProgRequest,
        "赤纬推运",
    ),
]
