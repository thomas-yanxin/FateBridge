"""次限法（二次推运）。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.utils.timezones import parse_timezone_name

from ._common import (
    build_subject,
    calculate_age_years,
    collect_aspect_hits,
    extract_reference_longitudes,
    point_to_dict,
)


def build_secondary_progression_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
) -> Dict[str, Any]:
    age_years = calculate_age_years(birth_info, analysis_datetime)
    progressed_utc = birth_info.require_utc_datetime + timedelta(days=age_years)
    progressed_local = progressed_utc.astimezone(
        parse_timezone_name(birth_info.timezone)
    )
    progressed_subject = build_subject(
        name=f"{birth_info.name}-progressed",
        local_datetime=progressed_local,
        longitude=birth_info.longitude,
        latitude=birth_info.latitude,
        timezone_name=birth_info.timezone,
        house_system=house_system,
        zodiac_type=zodiac_type,
    )
    hits = collect_aspect_hits(
        source_longitudes=extract_reference_longitudes(progressed_subject),
        target_longitudes=extract_reference_longitudes(natal_subject),
        orb_limit=1.5,
    )
    return {
        "calculation_basis": progressed_subject.calculation_basis,
        "progressed_datetime": progressed_local.isoformat(),
        "sun": point_to_dict("Sun", progressed_subject.sun),
        "moon": point_to_dict("Moon", progressed_subject.moon),
        "ascendant": point_to_dict("Ascendant", progressed_subject.ascendant),
        "medium_coeli": point_to_dict(
            "Medium_Coeli",
            progressed_subject.medium_coeli,
        ),
        "hits": hits[:8],
        "subject": progressed_subject,
    }
