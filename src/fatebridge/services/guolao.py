"""Standalone Guolao Xingzong service orchestration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.guolao.ephemeris import MansionFrame
from fatebridge.core.guolao.guolao import LifeDegreeMethod, build_chart
from fatebridge.core.guolao.guolao_timing import enrich_guolao_timing
from fatebridge.utils.errors import calculation_guard


@calculation_guard("果老星宗计算")
def calculate_guolao_chart(
    *,
    birth_year: int,
    birth_month: int,
    birth_day: int,
    birth_hour: int,
    birth_minute: int = 0,
    birth_second: int = 0,
    name: str | None = None,
    birth_place: str | None = None,
    birth_timezone: str | None = None,
    birth_longitude: float | None = 116.4074,
    birth_latitude: float | None = 39.9042,
    use_true_solar_time: bool = True,
    house_system: int | str | None = None,
    zodiac_type: str | None = None,
    zodiacal: int | str | None = None,
    mansion_frame: MansionFrame = "modern_equatorial",
    life_degree_method: LifeDegreeMethod = "sun_degree_in_palace",
    analysis_datetime: datetime | None = None,
    month_basis: str | None = None,
    seasonal_anchor_policy: str | None = None,
) -> dict[str, Any]:
    """Compute a complete Guolao Xingzong chart with optional timing."""
    birth = build_astro_birth_info(
        birth_year=birth_year,
        birth_month=birth_month,
        birth_day=birth_day,
        birth_hour=birth_hour,
        birth_minute=birth_minute,
        birth_second=birth_second,
        name=name,
        birth_place=birth_place,
        birth_timezone=birth_timezone,
        birth_longitude=birth_longitude,
        birth_latitude=birth_latitude,
        use_true_solar_time=use_true_solar_time,
        preserve_instant=True,
        require_resolved_timezone=True,
    )
    if zodiacal is not None:
        selected_zodiacal: int | str | None = zodiacal
    elif isinstance(zodiac_type, str):
        selected_zodiacal = {
            "tropic": 0,
            "tropical": 0,
            "sidereal": 1,
        }.get(zodiac_type.strip().lower(), zodiac_type)
    else:
        selected_zodiacal = None
    payload = build_chart(
        birth,
        hsys=house_system,
        zodiacal=selected_zodiacal,
        seasonal_anchor_policy=seasonal_anchor_policy,
        mansion_frame=mansion_frame,
        life_degree_method=life_degree_method,
    )
    if analysis_datetime is not None or month_basis is not None:
        enrich_guolao_timing(
            payload,
            birth,
            analysis_datetime,
            zodiacal=selected_zodiacal,
            month_basis=month_basis,
        )
    return payload
