"""Western lifespan tool declarations and domain binding helpers."""

from __future__ import annotations

from fatebridge.application.bindings import (
    ServiceRef,
    bind_kwargs,
    request_model_ref,
    service_ref,
)
from fatebridge.application.tool_spec import BatchInputPolicy, ToolSpec

_REQ_MODULE = "fatebridge.core.requests.western_lifespan"

calculate_age_point = service_ref(
    "fatebridge.services.western_lifespan", "calculate_age_point"
)


calculate_balbillus = service_ref(
    "fatebridge.services.western_lifespan", "calculate_balbillus"
)


calculate_distributions = service_ref(
    "fatebridge.services.western_lifespan", "calculate_distributions"
)


calculate_harmonic_chart = service_ref(
    "fatebridge.services.western_lifespan", "calculate_harmonic_chart"
)


calculate_jaynesprog = service_ref(
    "fatebridge.services.western_lifespan", "calculate_jaynesprog"
)


calculate_keypoints = service_ref(
    "fatebridge.services.western_lifespan", "calculate_keypoints"
)


calculate_lunation_phase = service_ref(
    "fatebridge.services.western_lifespan", "calculate_lunation_phase"
)


calculate_persian_directed = service_ref(
    "fatebridge.services.western_lifespan", "calculate_persian_directed"
)


calculate_planetary_ages = service_ref(
    "fatebridge.services.western_lifespan", "calculate_planetary_ages"
)


calculate_planetary_arc = service_ref(
    "fatebridge.services.western_lifespan", "calculate_planetary_arc"
)


calculate_triplicity_rulers = service_ref(
    "fatebridge.services.western_lifespan", "calculate_triplicity_rulers"
)


calculate_vedicprog = service_ref(
    "fatebridge.services.western_lifespan", "calculate_vedicprog"
)


calculate_yearsystem129 = service_ref(
    "fatebridge.services.western_lifespan", "calculate_yearsystem129"
)


def _western_lifespan_spec(
    name: str,
    service: ServiceRef,
    model_name: str,
    label: str,
    *,
    required_output_fields: tuple[str, ...] | None = None,
    summary: str | None = None,
    rest_path: str | None = None,
    default_omit: tuple[str, ...] = (),
) -> ToolSpec:
    """Register a single-natal-chart western lifespan technique tool."""
    return ToolSpec(
        name=name,
        bind=bind_kwargs(service),
        request_model_loader=request_model_ref(_REQ_MODULE, model_name),
        required_output_fields=required_output_fields or (name,),
        summary=summary or f"{label}：古典全生命周期技法（不需目标时刻）。",
        operation_label_zh=label,
        family="western_lifespan",
        cpu_bound=True,
        rest_path=rest_path or "/api/astrology/timing/" + name.replace("_", "-"),
        default_omit=default_omit,
        batch_policy=BatchInputPolicy(subject_mode="birth_fields"),
    )


SPECS: list[ToolSpec] = [
    # --- Western lifespan techniques (single natal chart, whole-life) ------
    _western_lifespan_spec(
        "harmonic_chart",
        calculate_harmonic_chart,
        "AstroHarmonicRequest",
        "调波盘",
        rest_path="/api/astrology/harmonic-chart",
        default_omit=("natal_reference",),
    ),
    _western_lifespan_spec(
        "planetary_ages",
        calculate_planetary_ages,
        "AstroPlanetaryAgesRequest",
        "行星年龄",
        default_omit=("natal_reference",),
    ),
    _western_lifespan_spec(
        "triplicity_ruler_periods",
        calculate_triplicity_rulers,
        "AstroTriplicityRulersRequest",
        "三分主星推运",
        default_omit=("natal_reference",),
    ),
    _western_lifespan_spec(
        "lunar_phase_progressions",
        calculate_lunation_phase,
        "AstroLunationPhaseRequest",
        "月相推运",
        summary="月相推运：按出生后实际日月八相交点推演象征年龄阶段。",
        default_omit=(
            "natal_reference",
            "lunar_phase_progressions.physical_ephemeris_source",
            "lunar_phase_progressions.phase_ingresses",
        ),
    ),
    _western_lifespan_spec(
        "bounds_directions",
        calculate_distributions,
        "AstroDistributionsRequest",
        "界推运",
        default_omit=("natal_reference",),
    ),
    _western_lifespan_spec(
        "balbillus_periods",
        calculate_balbillus,
        "AstroBalbillusRequest",
        "Balbillus 129年系统",
        required_output_fields=("balbillus",),
        default_omit=(
            "natal_reference",
            "balbillus.reduction_model",
            "balbillus.periods.*.subperiods",
        ),
    ),
    _western_lifespan_spec(
        "numeric_aspect_periods",
        calculate_keypoints,
        "AstroKeypointsRequest",
        "数字相位推运",
        default_omit=("natal_reference", "numeric_aspect_periods.activations"),
    ),
    _western_lifespan_spec(
        "planetary_periods_129_years",
        calculate_yearsystem129,
        "AstroYearSystem129Request",
        "129年系统",
        default_omit=("natal_reference",),
    ),
    _western_lifespan_spec(
        "planetary_arc_directions",
        calculate_planetary_arc,
        "AstroPlanetaryArcRequest",
        "行星弧方向",
        required_output_fields=("planetary_arc",),
        default_omit=("natal_reference",),
    ),
    _western_lifespan_spec(
        "persian_directions",
        calculate_persian_directed,
        "AstroPersianDirectedRequest",
        "波斯向运",
        default_omit=("natal_reference", "persian_directions.hits"),
    ),
    _western_lifespan_spec(
        "age_point",
        calculate_age_point,
        "AstroAgePointRequest",
        "年龄推进点",
        default_omit=("natal_reference", "age_point.points"),
    ),
    _western_lifespan_spec(
        "sidereal_progressions",
        calculate_vedicprog,
        "AstroVedicProgRequest",
        "恒星推运",
        default_omit=("natal_reference",),
    ),
    _western_lifespan_spec(
        "declination_progressions",
        calculate_jaynesprog,
        "AstroJaynesProgRequest",
        "赤纬推运",
        default_omit=("natal_reference",),
    ),
]
