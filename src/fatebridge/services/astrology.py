"""
FateBridge astrology services.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fatebridge.core.astro.birth import AstroBirthInfo, build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload, build_midpoint_payload
from fatebridge.core.astro.opaque_solar import opaque_solar_positions
from fatebridge.core.astro.relationship import build_relative_payload
from fatebridge.core.astro.sensitivity import enrich_specialty_sensitivity
from fatebridge.core.astro.solar_arc import enrich_solar_arc
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.house_systems import (
    normalize_offline_zodiac_code,
    resolve_offline_house_code,
)


def _chart_calculation_notes(payload: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for field in (
        "ephemeris_reference_points",
        "angle_definition",
        "house_axis_convention",
        "house_position_projection",
        "orbital_fallback",
        "fixed_stars",
    ):
        qualification = payload.get("chart_profile", {}).get(field) or {}
        note = qualification.get("note_zh")
        if field == "orbital_fallback" and not note:
            fb = qualification.get("approximate_planets") or qualification.get(
                "fallback_planets"
            )
            if fb:
                note = f"轨道近似天体：{'、'.join(fb)}。"
        if note and note not in notes:
            notes.append(note)
    return notes


__all__ = [
    "SUPPORTED_CHART_VARIANTS",
    "calculate_core_chart_analysis",
    "calculate_germany_chart_analysis",
    "calculate_relative_chart_analysis",
]

SUPPORTED_CHART_VARIANTS = {
    "chart",
    "chart13",
    "hellen_chart",
}


def _build_birth_info(payload: dict[str, Any]) -> AstroBirthInfo:
    return build_astro_birth_info(
        birth_year=payload["birth_year"],
        birth_month=payload["birth_month"],
        birth_day=payload["birth_day"],
        birth_hour=payload["birth_hour"],
        birth_minute=payload.get("birth_minute", 0),
        birth_second=payload.get("birth_second", 0),
        birth_microsecond=payload.get("birth_microsecond", 0),
        birth_clock_basis=payload.get("birth_clock_basis", "civil"),
        birth_timezone=payload.get("birth_timezone"),
        birth_longitude=payload.get("birth_longitude"),
        birth_latitude=payload.get("birth_latitude"),
        name=payload.get("name"),
        birth_place=payload.get("birth_place"),
        use_true_solar_time=payload.get("use_true_solar_time", False),
        preserve_instant=payload.get("preserve_instant", False),
        require_resolved_timezone=payload.get("require_resolved_timezone", True),
        solar_clock_ephemeris_policy=payload.get(
            "solar_clock_ephemeris_policy", "auto"
        ),
        allow_native_solar_epoch=payload.get("allow_native_solar_epoch", False),
    )


@calculation_guard("核心星盘分析")
def calculate_core_chart_analysis(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_longitude: float | None,
    birth_latitude: float | None,
    chart_variant: str = "chart",
    apparent_model: Literal["native", "opaque_solar"] = "native",
    birth_minute: int = 0,
    birth_second: int = 0,
    birth_clock_basis: str = "civil",
    birth_timezone: str | None = None,
    name: str | None = None,
    birth_place: str | None = None,
    gender: str | None = None,  # accepted for uniform args; unused in chart math
    house_system: int | str | None = None,
    zodiac_type: str | None = None,
    use_true_solar_time: bool = False,
    node_mode: str = "mean",
    high_latitude_fallback: str = "error",
    include_minor_aspects: bool = False,
    max_aspects: int | None = None,
    extra_bodies: list[str] | tuple[str, ...] = (),
    birth_time_uncertainty_minutes: float | None = None,
    analysis_datetime: datetime | None = None,
) -> dict[str, Any]:
    """
    Build an offline core astrology chart family payload.

    Core charts prefer a local Swiss Ephemeris runtime when available and fall
    back to the bundled approximate orbital model when it is not.
    """
    if birth_clock_basis != "civil" and chart_variant not in {
        "germany",
        "chart13",
    }:
        raise ValueError(
            "Noncivil birth_clock_basis requires chart_variant=germany or chart13"
        )
    if birth_second and chart_variant not in {
        "germany",
        "chart13",
    }:
        raise ValueError(
            "nonzero birth_second requires chart_variant=germany or chart13"
        )
    if chart_variant == "germany":
        return calculate_germany_chart_analysis(
            birth_year=birth_year,
            birth_month=birth_month,
            birth_day=birth_day,
            birth_hour=birth_hour,
            birth_minute=birth_minute,
            birth_second=birth_second,
            birth_clock_basis=birth_clock_basis,
            birth_longitude=birth_longitude,
            birth_latitude=birth_latitude,
            birth_timezone=birth_timezone,
            name=name,
            birth_place=birth_place,
            gender=gender,
            house_system=house_system,
            zodiac_type=zodiac_type,
            use_true_solar_time=use_true_solar_time,
            birth_time_uncertainty_minutes=birth_time_uncertainty_minutes,
            analysis_datetime=analysis_datetime,
        )
    raw_hsys = (
        None if house_system is None else resolve_offline_house_code(house_system)
    )
    hsys = "E" if raw_hsys == 9 else raw_hsys
    zodiacal = (
        None if zodiac_type is None else normalize_offline_zodiac_code(zodiac_type)
    )

    if analysis_datetime is not None:
        raise ValueError("analysis_datetime requires chart_variant=germany")
    if chart_variant not in SUPPORTED_CHART_VARIANTS:
        raise ValueError(
            f"不支持的 chart_variant: {chart_variant}。"
            f"可选值：{', '.join(sorted(SUPPORTED_CHART_VARIANTS))}"
        )

    birth_info = _build_birth_info(
        {
            "birth_year": birth_year,
            "birth_month": birth_month,
            "birth_day": birth_day,
            "birth_hour": birth_hour,
            "birth_minute": birth_minute,
            "birth_second": birth_second,
            "birth_clock_basis": birth_clock_basis,
            "birth_timezone": birth_timezone,
            "birth_longitude": birth_longitude,
            "birth_latitude": birth_latitude,
            "name": name,
            "birth_place": birth_place,
            "use_true_solar_time": use_true_solar_time,
            "preserve_instant": False,
            "require_resolved_timezone": True,
            "allow_native_solar_epoch": False,
            "birth_microsecond": 0,
            "solar_clock_ephemeris_policy": "auto",
        }
    )
    result = build_core_chart_payload(
        birth_info,
        chart_variant,
        hsys=hsys,
        zodiacal=zodiacal,
        node_mode=node_mode,
        high_latitude_fallback=high_latitude_fallback,
        include_minor_aspects=include_minor_aspects,
        max_aspects=max_aspects,
        extra_bodies=extra_bodies,
    )
    result["summary"] = [
        f"{chart_variant}：{len(result['planets'])} 个星体与虚点，"
        f"{len(result['houses'])} 个宫位，{len(result['aspects'])} 条相位。",
        *_chart_calculation_notes(result),
    ]
    if chart_variant == "chart13":
        enrich_specialty_sensitivity(
            result,
            birth_info,
            kind="chart13",
            uncertainty_minutes=birth_time_uncertainty_minutes,
        )
        if "time_sensitivity" in result:
            result["birth_time_sensitivity"] = result.pop("time_sensitivity")
    if apparent_model == "opaque_solar":
        result["apparent_model_positions"] = opaque_solar_positions(
            result["chart_profile"]["julian_day_tt"]
        )
    return result


@calculation_guard("量化盘分析")
def calculate_germany_chart_analysis(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_longitude: float | None,
    birth_latitude: float | None,
    birth_minute: int = 0,
    birth_second: int = 0,
    birth_clock_basis: str = "civil",
    birth_timezone: str | None = None,
    name: str | None = None,
    birth_place: str | None = None,
    gender: str | None = None,  # accepted for uniform args; unused in chart math
    house_system: int | str | None = None,
    zodiac_type: str | None = None,
    use_true_solar_time: bool = False,
    birth_time_uncertainty_minutes: float | None = None,
    analysis_datetime: datetime | None = None,
    high_latitude_fallback: str = "error",
    dial_degrees: str | None = None,
    sensitive_point_query: str | None = None,
    max_higher_factor_contacts: int | None = 12,
    max_mixed_pair_contacts: int | None = 2,
) -> dict[str, Any]:
    """
    Build the FateBridge midpoint/germany chart payload.
    """
    raw_hsys = (
        None if house_system is None else resolve_offline_house_code(house_system)
    )
    hsys = "E" if raw_hsys == 9 else raw_hsys
    zodiacal = (
        None if zodiac_type is None else normalize_offline_zodiac_code(zodiac_type)
    )
    birth_info = _build_birth_info(
        {
            "birth_year": birth_year,
            "birth_month": birth_month,
            "birth_day": birth_day,
            "birth_hour": birth_hour,
            "birth_minute": birth_minute,
            "birth_second": birth_second,
            "birth_clock_basis": birth_clock_basis,
            "birth_timezone": birth_timezone,
            "birth_longitude": birth_longitude,
            "birth_latitude": birth_latitude,
            "name": name,
            "birth_place": birth_place,
            "use_true_solar_time": use_true_solar_time,
        }
    )
    result = build_midpoint_payload(
        birth_info,
        hsys=hsys,
        zodiacal=zodiacal,
        high_latitude_fallback=high_latitude_fallback,
        dial_degrees=dial_degrees,
        sensitive_point_query=sensitive_point_query,
        max_higher_factor_contacts=max_higher_factor_contacts,
    )
    sample_times = enrich_specialty_sensitivity(
        result,
        birth_info,
        kind="germany",
        uncertainty_minutes=birth_time_uncertainty_minutes,
    )
    enrich_solar_arc(
        result,
        birth_info,
        analysis_datetime,
        sample_times=sample_times,
        max_higher_factor_contacts=max_higher_factor_contacts,
        max_mixed_pair_contacts=max_mixed_pair_contacts,
    )
    layer = result.get("midpoint_analysis")
    if isinstance(layer, dict) and "time_sensitivity" in layer:
        layer["birth_time_sensitivity"] = layer.pop("time_sensitivity")
    return result


@calculation_guard("关系星盘分析")
def calculate_relative_chart_analysis(
    *,
    inner_payload: dict[str, Any],
    outer_payload: dict[str, Any],
    relative_mode: Any = None,
    house_system: int | str = "P",
    zodiac_type: str = "Tropic",
    relationship_focus: Any = None,
    davison_variant: str = "uncorrected",
    composite_house_method: str = "midpoint",
    high_latitude_fallback: str = "error",
) -> dict[str, Any]:
    """
    Build synastry/composite payloads for two parties.

    house_system defaults to Placidus ('P', code 3), matching both published request forms.
    """
    hsys = resolve_offline_house_code(house_system)
    zodiacal = normalize_offline_zodiac_code(zodiac_type)
    inner_birth = _build_birth_info(inner_payload)
    outer_birth = _build_birth_info(outer_payload)
    return build_relative_payload(
        inner_birth=inner_birth,
        outer_birth=outer_birth,
        relative_mode=relative_mode,
        hsys=hsys,
        zodiacal=zodiacal,
        relationship_focus=relationship_focus,
        davison_variant=davison_variant,
        composite_house_method=composite_house_method,
        high_latitude_fallback=high_latitude_fallback,
    )
