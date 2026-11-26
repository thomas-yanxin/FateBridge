"""
FateBridge astrology services.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any, Literal

from fatebridge.core.astro.birth import AstroBirthInfo, build_astro_birth_info
from fatebridge.core.astro.chart import build_core_chart_payload, build_midpoint_payload
from fatebridge.core.astro.opaque_solar import opaque_solar_positions
from fatebridge.core.astro.relationship import build_relative_payload
from fatebridge.core.astro.sensitivity import enrich_specialty_sensitivity
from fatebridge.core.astro.solar_arc import enrich_solar_arc
from fatebridge.core.guolao.guolao_anchor_days import POLICIES
from fatebridge.core.guolao.guolao_birth_clock import coherent_guolao_solar_call
from fatebridge.core.guolao.guolao_timing import enrich_guolao_timing
from fatebridge.core.jyotish.jyotish_display import normalize_solar_display
from fatebridge.core.jyotish.jyotish_sources import coherent_india_call
from fatebridge.services.jyotish import enrich_india_chart
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
    "guolao_chart",
    "india_chart",
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
@coherent_india_call
@coherent_guolao_solar_call
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
    birth_microsecond: int = 0,
    birth_clock_basis: str = "civil",
    birth_timezone: str | None = None,
    name: str | None = None,
    birth_place: str | None = None,
    gender: str | None = None,  # accepted for uniform args; unused in chart math
    house_system: int | str | None = None,
    zodiac_type: str | None = None,
    use_true_solar_time: bool = False,
    node_mode: str = "mean",
    ephemeris_policy: str = "auto",
    saptavargaja_profile: str = "santhanam_27",
    drekkana_profile: str = "santhanam_27_6",
    cheshta_model: str = "unadjudicated",
    divisions: list[int] | None = None,
    birth_time_uncertainty_minutes: float | None = None,
    analysis_datetime: datetime | None = None,
    guolao_month_basis: str | None = None,
    guolao_seasonal_anchor_policy: str | None = None,
) -> dict[str, Any]:
    """
    Build an offline core astrology chart family payload.

    Core charts prefer a local Swiss Ephemeris runtime when available and fall
    back to the bundled approximate orbital model when it is not.
    """
    if guolao_seasonal_anchor_policy is not None:
        if chart_variant != "guolao_chart":
            raise ValueError(
                "guolao_seasonal_anchor_policy requires chart_variant=guolao_chart"
            )
        if guolao_seasonal_anchor_policy not in POLICIES:
            raise ValueError("Unknown guolao_seasonal_anchor_policy")
        if guolao_seasonal_anchor_policy in POLICIES[1:] and not (
            use_true_solar_time or birth_clock_basis == "local_apparent_solar"
        ):
            raise ValueError(
                "Solar-day anchors require an apparent clock: use_true_solar_time=true or explicit LAT input"
            )
    if guolao_month_basis is not None and (
        chart_variant != "guolao_chart" or analysis_datetime is None
    ):
        raise ValueError(
            "guolao_month_basis requires chart_variant=guolao_chart and analysis_datetime"
        )
    if guolao_month_basis is not None and guolao_month_basis not in {
        "jie_month",
        "chinese_lunar_utc8",
    }:
        raise ValueError("guolao_month_basis must be jie_month or chinese_lunar_utc8")
    if chart_variant != "india_chart" and drekkana_profile != "santhanam_27_6":
        raise ValueError("drekkana_profile requires chart_variant=india_chart")
    if birth_clock_basis != "civil" and chart_variant not in {
        "germany",
        "chart13",
        "india_chart",
        "guolao_chart",
    }:
        raise ValueError(
            "Noncivil birth_clock_basis requires chart_variant=germany, chart13, india_chart or guolao_chart"
        )
    if birth_second and chart_variant not in {
        "germany",
        "chart13",
        "india_chart",
        "guolao_chart",
    }:
        raise ValueError(
            "nonzero birth_second requires chart_variant=germany, chart13, india_chart or guolao_chart"
        )
    if birth_microsecond and chart_variant not in {"india_chart", "guolao_chart"}:
        raise ValueError(
            "nonzero birth_microsecond requires chart_variant=india_chart or guolao_chart"
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
    hsys = None if house_system is None else resolve_offline_house_code(house_system)
    zodiacal = (
        None if zodiac_type is None else normalize_offline_zodiac_code(zodiac_type)
    )

    if analysis_datetime is not None and chart_variant != "guolao_chart":
        raise ValueError(
            "analysis_datetime requires chart_variant=germany or guolao_chart"
        )
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
            "use_true_solar_time": (
                False
                if chart_variant == "guolao_chart"
                or (chart_variant == "india_chart" and birth_clock_basis == "civil")
                else use_true_solar_time
            ),
            "preserve_instant": chart_variant in {"guolao_chart", "india_chart"},
            "require_resolved_timezone": True,
            "allow_native_solar_epoch": chart_variant == "guolao_chart",
            "birth_microsecond": birth_microsecond,
            "solar_clock_ephemeris_policy": (
                ephemeris_policy if chart_variant == "india_chart" else "auto"
            ),
        }
    )
    if chart_variant == "guolao_chart":
        # Guolao derives its solar clock from its actual Sun/UT1 later. The
        # legacy constructor's independent display is unused and can fail
        # before that valid calculation. Keep only the requested clock policy.
        birth_info = replace(birth_info, applied_true_solar=use_true_solar_time)
    if chart_variant == "india_chart":
        birth_info, _ = normalize_solar_display(
            birth_info, ephemeris_policy, requested=use_true_solar_time
        )
    anchor_options: dict[str, Any] = (
        {"guolao_seasonal_anchor_policy": guolao_seasonal_anchor_policy}
        if guolao_seasonal_anchor_policy is not None
        else {}
    )
    result = build_core_chart_payload(
        birth_info,
        chart_variant,
        hsys=hsys,
        zodiacal=zodiacal,
        **anchor_options,
    )
    if chart_variant == "guolao_chart":
        enrich_guolao_timing(
            result,
            birth_info,
            analysis_datetime,
            zodiacal=zodiacal,
            month_basis=guolao_month_basis,
        )
        result["summary"] = [
            f"果老研究盘：{len(result['guolao']['bodies'])} 个星曜与虚点，"
            f"{len(result['guolao']['palaces'])} 个功能宫。"
        ]
    else:
        result["summary"] = [
            f"{chart_variant}：{len(result['planets'])} 个星体与虚点，"
            f"{len(result['houses'])} 个宫位，{len(result['aspects'])} 条相位。",
            *_chart_calculation_notes(result),
        ]
    if chart_variant == "india_chart":
        enrich_india_chart(
            result,
            birth_info,
            node_mode=node_mode,
            ephemeris_policy=ephemeris_policy,
            saptavargaja_profile=saptavargaja_profile,
            drekkana_profile=drekkana_profile,
            cheshta_model=cheshta_model,
            divisions=divisions,
            birth_time_uncertainty_minutes=birth_time_uncertainty_minutes,
        )
    if chart_variant == "chart13":
        enrich_specialty_sensitivity(
            result,
            birth_info,
            kind="chart13",
            uncertainty_minutes=birth_time_uncertainty_minutes,
        )
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
) -> dict[str, Any]:
    """
    Build the FateBridge midpoint/germany chart payload.
    """
    hsys = None if house_system is None else resolve_offline_house_code(house_system)
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
    )
    sample_times = enrich_specialty_sensitivity(
        result,
        birth_info,
        kind="germany",
        uncertainty_minutes=birth_time_uncertainty_minutes,
    )
    enrich_solar_arc(result, birth_info, analysis_datetime, sample_times=sample_times)
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
    )
