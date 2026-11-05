"""Western lifespan tool declarations and domain binding helpers."""

from __future__ import annotations

from typing import Any, List

from fatebridge.application.bindings import lazy_service, raw_invoke
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


def _western_lifespan_spec(name: str, service: Any, model: Any, label: str) -> ToolSpec:
    """Register a single-natal-chart western lifespan technique tool."""
    return ToolSpec(
        key=f"astro_{name}",
        bind=raw_invoke(service),
        request_model=model,
        summary=(
            f"{label}：只读单张本命盘的古典「全生命周期」技法（不需目标时刻），"
            f"输出按年龄/时段划分的人生阶段。"
        ),
        operation_label_zh=label,
        family="western_lifespan",
        cpu_bound=True,
        rest_path=f"/api/astro/lifespan/{name}",
        mcp_name=f"astro_{name}",
    )


SPECS: List[ToolSpec] = [
    # --- Western lifespan techniques (single natal chart, whole-life) ------
    _western_lifespan_spec(
        "harmonic", calculate_harmonic_chart, AstroHarmonicRequest, "调波盘"
    ),
    _western_lifespan_spec(
        "planetary_ages",
        calculate_planetary_ages,
        AstroPlanetaryAgesRequest,
        "行星年龄",
    ),
    _western_lifespan_spec(
        "triplicity_rulers",
        calculate_triplicity_rulers,
        AstroTriplicityRulersRequest,
        "三分主星推运",
    ),
    _western_lifespan_spec(
        "lunation_phase",
        calculate_lunation_phase,
        AstroLunationPhaseRequest,
        "月相推运",
    ),
    _western_lifespan_spec(
        "distributions",
        calculate_distributions,
        AstroDistributionsRequest,
        "界推运",
    ),
    _western_lifespan_spec(
        "balbillus",
        calculate_balbillus,
        AstroBalbillusRequest,
        "Balbillus 129年系统",
    ),
    _western_lifespan_spec(
        "keypoints",
        calculate_keypoints,
        AstroKeypointsRequest,
        "数字相位推运",
    ),
    _western_lifespan_spec(
        "yearsystem129",
        calculate_yearsystem129,
        AstroYearSystem129Request,
        "129年系统",
    ),
    _western_lifespan_spec(
        "planetaryarc",
        calculate_planetary_arc,
        AstroPlanetaryArcRequest,
        "行星弧方向",
    ),
    _western_lifespan_spec(
        "persiandirected",
        calculate_persian_directed,
        AstroPersianDirectedRequest,
        "波斯向运",
    ),
    _western_lifespan_spec(
        "agepoint",
        calculate_age_point,
        AstroAgePointRequest,
        "年龄推进点",
    ),
    _western_lifespan_spec(
        "vedicprog",
        calculate_vedicprog,
        AstroVedicProgRequest,
        "恒星推运",
    ),
    _western_lifespan_spec(
        "jaynesprog",
        calculate_jaynesprog,
        AstroJaynesProgRequest,
        "赤纬推运",
    ),
]
