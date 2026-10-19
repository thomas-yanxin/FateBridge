"""
FateBridge western predictive timing services.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fatebridge.core.predictive._common import (
    build_analysis_datetime,
    build_predictive_birth_info,
)
from fatebridge.core.predictive.firdaria import (
    normalize_calendar_firdaria_birth,
    validate_calendar_firdaria_inputs,
)
from fatebridge.core.predictive.western_timing import (
    build_western_timing_module_payload,
    build_western_timing_payload,
)
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.house_systems import normalize_house_system


@calculation_guard("西占推运与返照分析")
def calculate_western_timing_analysis(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_timezone: str,
    birth_longitude: float,
    birth_latitude: float,
    name: Optional[str] = None,
    birth_minute: int = 0,
    birth_place: Optional[str] = None,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    analysis_hour: Optional[int] = None,
    analysis_minute: Optional[int] = None,
    firdaria_night_order: str = "nodes_at_end",
    firdaria_year_basis: str = "fixed_365_2425",
    return_longitude: Optional[float] = None,
    return_latitude: Optional[float] = None,
    return_timezone: Optional[str] = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    pd_method: str = "astroapp_alchabitius",
    pd_time_key: str = "Ptolemy",
    pd_type: int = 0,
    pd_aspects: Optional[list[int]] = None,
    show_pd_bounds: bool = True,
) -> Dict[str, Any]:
    """
    Build a western astrology predictive package with returns, progressions,
    and time-lord systems around a target analysis date.
    """
    house_system = normalize_house_system(house_system)
    birth_info = build_predictive_birth_info(
        birth_year=birth_year,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_hour=birth_hour,
        birth_minute=birth_minute,
        birth_timezone=birth_timezone,
        birth_longitude=birth_longitude,
        birth_latitude=birth_latitude,
        name=name,
        birth_place=birth_place,
    )
    if firdaria_year_basis == "calendar_anniversary":
        birth_info = normalize_calendar_firdaria_birth(birth_info)
    analysis_datetime = build_analysis_datetime(
        birth_info,
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
    )
    if firdaria_year_basis == "calendar_anniversary":
        # Request analysis fields are civil clocks in birth_timezone. Preserve
        # that clock using IANA recurrence rules, including dates after 2038.
        analysis_datetime = analysis_datetime.replace(
            tzinfo=birth_info.local_datetime.tzinfo
        )
        validate_calendar_firdaria_inputs(birth_info, analysis_datetime)
    return build_western_timing_payload(
        birth_info,
        analysis_datetime=analysis_datetime,
        firdaria_night_order=firdaria_night_order,
        firdaria_year_basis=firdaria_year_basis,
        return_longitude=return_longitude,
        return_latitude=return_latitude,
        return_timezone=return_timezone,
        house_system=house_system,
        zodiac_type=zodiac_type,
        pd_method=pd_method,
        pd_time_key=pd_time_key,
        pd_type=pd_type,
        pd_aspects=pd_aspects,
        show_pd_bounds=show_pd_bounds,
    )


@calculation_guard("西占推运与返照分析")
def calculate_western_timing_module_analysis(
    *,
    technique: str,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_timezone: str,
    birth_longitude: float,
    birth_latitude: float,
    name: Optional[str] = None,
    birth_minute: int = 0,
    birth_place: Optional[str] = None,
    analysis_year: Optional[int] = None,
    analysis_month: Optional[int] = None,
    analysis_day: Optional[int] = None,
    analysis_hour: Optional[int] = None,
    analysis_minute: Optional[int] = None,
    firdaria_night_order: str = "nodes_at_end",
    firdaria_year_basis: str = "fixed_365_2425",
    return_longitude: Optional[float] = None,
    return_latitude: Optional[float] = None,
    return_timezone: Optional[str] = None,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    pd_method: str = "astroapp_alchabitius",
    pd_time_key: str = "Ptolemy",
    pd_type: int = 0,
    pd_aspects: Optional[list[int]] = None,
    show_pd_bounds: bool = True,
) -> Dict[str, Any]:
    """Build a single western timing technique payload for standalone tools."""
    house_system = normalize_house_system(house_system)
    birth_info = build_predictive_birth_info(
        birth_year=birth_year,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_hour=birth_hour,
        birth_minute=birth_minute,
        birth_timezone=birth_timezone,
        birth_longitude=birth_longitude,
        birth_latitude=birth_latitude,
        name=name,
        birth_place=birth_place,
    )
    if technique == "firdaria" and firdaria_year_basis == "calendar_anniversary":
        birth_info = normalize_calendar_firdaria_birth(birth_info)
    analysis_datetime = build_analysis_datetime(
        birth_info,
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
    )
    if technique == "firdaria" and firdaria_year_basis == "calendar_anniversary":
        analysis_datetime = analysis_datetime.replace(
            tzinfo=birth_info.local_datetime.tzinfo
        )
        validate_calendar_firdaria_inputs(birth_info, analysis_datetime)
    return build_western_timing_module_payload(
        birth_info,
        technique=technique,
        analysis_datetime=analysis_datetime,
        firdaria_night_order=firdaria_night_order,
        firdaria_year_basis=firdaria_year_basis,
        return_longitude=return_longitude,
        return_latitude=return_latitude,
        return_timezone=return_timezone,
        house_system=house_system,
        zodiac_type=zodiac_type,
        pd_method=pd_method,
        pd_time_key=pd_time_key,
        pd_type=pd_type,
        pd_aspects=pd_aspects,
        show_pd_bounds=show_pd_bounds,
    )
