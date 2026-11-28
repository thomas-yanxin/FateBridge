"""次限法（二次推运）。"""

from __future__ import annotations

from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any, TypedDict

from fatebridge.core.astro.birth import AstroBirthInfo
from fatebridge.core.predictive._common import (
    build_subject,
    collect_aspect_hits,
    extract_reference_longitudes,
    point_to_dict,
)
from fatebridge.core.predictive.native_chart import NativeSubject
from fatebridge.utils.civil_time import UTCCalendar, ZonedCalendar, utc_calendar
from fatebridge.utils.timezones import format_local_time_or_utc, parse_timezone_name

SECONDARY_PROGRESSION_YEAR_KEY = Fraction(36524219, 100000)


class ProgressionClockOptions(TypedDict):
    method: str
    year_basis: str
    year_key_numerator: int
    year_key_denominator: int
    time_basis: str
    timestamp_rounding: str


class ProgressionCalculationOptions(ProgressionClockOptions):
    house_method: str


def secondary_progression_clock_options() -> ProgressionClockOptions:
    return {
        "method": "direct_secondary_progression",
        "year_basis": "fixed_365_24219_nominal_days",
        "year_key_numerator": SECONDARY_PROGRESSION_YEAR_KEY.numerator,
        "year_key_denominator": SECONDARY_PROGRESSION_YEAR_KEY.denominator,
        "time_basis": "UTC_nominal_elapsed_days",
        "timestamp_rounding": "nearest_microsecond_ties_to_even_from_birth",
    }


def calculate_secondary_progression_clock(
    birth_info: AstroBirthInfo,
    *,
    analysis_datetime: datetime,
) -> tuple[UTCCalendar, ProgressionClockOptions]:
    birth_utc = birth_info.utc_calendar
    delta = utc_calendar(analysis_datetime).elapsed_since(birth_utc)
    elapsed_microseconds = (
        delta.days * 86400 + delta.seconds
    ) * 1_000_000 + delta.microseconds
    # Astrolog's documented fixed mean-tropical key, not a measured solar year.
    # The day/year unit cancels: divide elapsed microseconds by the exact key.
    progressed_utc = birth_utc.shifted(
        timedelta(
            microseconds=round(
                Fraction(elapsed_microseconds) / SECONDARY_PROGRESSION_YEAR_KEY
            )
        )
    )
    return progressed_utc, secondary_progression_clock_options()


def build_secondary_progression_payload(
    birth_info: AstroBirthInfo,
    natal_subject: NativeSubject,
    *,
    analysis_datetime: datetime,
    house_system: str = "P",
    zodiac_type: str = "Tropic",
    orb_limit: float = 1.5,
    max_hits: int | None = None,
) -> dict[str, Any]:
    progressed_utc, clock_options = calculate_secondary_progression_clock(
        birth_info, analysis_datetime=analysis_datetime
    )
    progressed_local = ZonedCalendar(
        progressed_utc, parse_timezone_name(birth_info.timezone)
    ).require_datetime()
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
        orb_limit=orb_limit,
    )
    hits_total_count = len(hits)
    selected_hits = hits[:max_hits] if max_hits is not None else hits
    calculation_options: ProgressionCalculationOptions = {
        **clock_options,
        "house_method": "quotidian_at_progressed_UTC",
    }
    return {
        "calculation_options": calculation_options,
        "calculation_basis": progressed_subject.calculation_basis,
        "progressed_datetime": format_local_time_or_utc(progressed_local),
        "sun": point_to_dict("Sun", progressed_subject.sun),
        "moon": point_to_dict("Moon", progressed_subject.moon),
        "ascendant": point_to_dict("Ascendant", progressed_subject.ascendant),
        "medium_coeli": point_to_dict(
            "Medium_Coeli",
            progressed_subject.medium_coeli,
        ),
        "hits": selected_hits,
        "hits_total_count": hits_total_count,
        "subject": progressed_subject,
    }
