"""次限法（二次推运）。"""

from __future__ import annotations

from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any, Dict, TypedDict

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.utils.timezones import parse_timezone_name

from ._common import (
    build_subject,
    collect_aspect_hits,
    extract_reference_longitudes,
    point_to_dict,
)


class ProgressionClockOptions(TypedDict):
    method: str
    year_basis: str
    year_key_numerator: int
    year_key_denominator: int
    time_basis: str
    timestamp_rounding: str


class ProgressionCalculationOptions(ProgressionClockOptions):
    house_method: str


def calculate_secondary_progression_clock(
    birth_info: AstroBirthInfo,
    *,
    analysis_datetime: datetime,
) -> tuple[datetime, ProgressionClockOptions]:
    birth_utc = birth_info.require_utc_datetime
    delta = analysis_datetime.astimezone(parse_timezone_name("UTC")) - birth_utc
    elapsed_microseconds = (
        delta.days * 86400 + delta.seconds
    ) * 1_000_000 + delta.microseconds
    # Astrolog's documented fixed mean-tropical key, not a measured solar year.
    # The day/year unit cancels: divide elapsed microseconds by the exact key.
    progressed_utc = birth_utc + timedelta(
        microseconds=round(Fraction(elapsed_microseconds * 100000, 36524219))
    )
    return progressed_utc, {
        "method": "direct_secondary_progression",
        "year_basis": "fixed_365_24219_nominal_days",
        "year_key_numerator": 36524219,
        "year_key_denominator": 100000,
        "time_basis": "UTC_nominal_elapsed_days",
        "timestamp_rounding": "nearest_microsecond_ties_to_even_from_birth",
    }


def build_secondary_progression_payload(
    birth_info: AstroBirthInfo,
    natal_subject: Any,
    *,
    analysis_datetime: datetime,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
) -> Dict[str, Any]:
    progressed_utc, clock_options = calculate_secondary_progression_clock(
        birth_info, analysis_datetime=analysis_datetime
    )
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
    calculation_options: ProgressionCalculationOptions = {
        **clock_options,
        "house_method": "quotidian_at_progressed_UTC",
    }
    return {
        "calculation_options": calculation_options,
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
