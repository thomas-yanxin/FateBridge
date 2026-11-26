"""Shared civil-input, nominal-clock and calendar assembly for technique seeds."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TypedDict

from fatebridge.core.almanac import (
    build_calendar_context,
    get_adjacent_solar_terms,
    localize_datetime,
)
from fatebridge.core.bazi.calendar import BaZiCalendar
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.ziwei.calendar import birth_clock_receipt
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.civil_clock import resolve_civil_clock
from fatebridge.utils.civil_time import NominalClockLabel
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_APPARENT,
    calculate_solar_time_adjustment,
    normalize_birth_time,
)
from fatebridge.utils.solar_time_provenance import solar_time_receipt


def assemble_metaphysics_seed(
    *,
    civil: datetime,
    clock: NominalClockLabel,
    timezone_name: str,
    input_offset_visible: bool,
    longitude: float | None,
    applied_true_solar: bool,
    total_correction_minutes: float,
    solar_time_adjustment: dict[str, object] | None = None,
    birth_time_normalization: dict[str, object] | None = None,
) -> MetaphysicsSeed:
    """Assemble the selected nominal label with its resolved civil instant."""
    pillars = BaZiCalendar.get_four_pillars(
        clock, timezone_name=timezone_name, civil_datetime=civil
    )
    adjacent_terms = get_adjacent_solar_terms(civil, timezone_name)
    calendar_context = build_calendar_context(
        clock,
        timezone_name=timezone_name,
        pillars=pillars,
        civil_datetime=civil,
        adjacent_terms=adjacent_terms,
    )
    return MetaphysicsSeed(
        input_datetime=civil,
        clock=clock,
        timezone=timezone_name,
        longitude=longitude,
        applied_true_solar=applied_true_solar,
        total_correction_minutes=total_correction_minutes,
        pillars=pillars,
        calendar_context=calendar_context,
        input_offset_visible=input_offset_visible,
        current_term_source_grid_year=adjacent_terms[0].source_grid_year,
        solar_time_adjustment=solar_time_adjustment,
        birth_time_normalization=birth_time_normalization,
    )


class AnalysisClockContext(TypedDict):
    input_datetime: str
    corrected_datetime: str
    timezone: str
    longitude: float | None
    time_algorithm: str
    total_correction_minutes: float
    current_jieqi: str
    next_jieqi: str
    lunar_display: str | None


def _build_person_seed(
    person: PersonInfo, *, birth_utc_offset: str | None = None
) -> MetaphysicsSeed:
    # note (birth clock): Zi Wei and BaZi both include the equation of time at hour boundaries.
    normalized_birth_time = normalize_birth_time(
        person,
        solar_time_strategy=SOLAR_TIME_STRATEGY_APPARENT,
        birth_utc_offset=birth_utc_offset,
    )
    civil = localize_datetime(
        normalized_birth_time.input_datetime, normalized_birth_time.timezone
    )
    return assemble_metaphysics_seed(
        civil=civil,
        clock=NominalClockLabel.from_local_datetime(
            normalized_birth_time.corrected_datetime
        ),
        timezone_name=normalized_birth_time.timezone,
        input_offset_visible=normalized_birth_time.input_datetime.utcoffset()
        is not None,
        longitude=normalized_birth_time.longitude,
        applied_true_solar=normalized_birth_time.applied,
        total_correction_minutes=normalized_birth_time.total_correction_minutes,
        birth_time_normalization=birth_clock_receipt(person, normalized_birth_time),
    )


def _analysis_context_payload(seed: MetaphysicsSeed) -> AnalysisClockContext:
    lunar_context = seed.calendar_context.get("lunar_calendar") or {}
    return {
        "input_datetime": seed.input_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "corrected_datetime": seed.clock.isoformat(sep=" ", timespec="seconds"),
        "timezone": seed.timezone,
        "longitude": seed.longitude,
        "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        "total_correction_minutes": round(seed.total_correction_minutes, 2),
        "current_jieqi": seed.calendar_context["current_solar_term"]["name"],
        "next_jieqi": seed.calendar_context["next_solar_term"]["name"],
        "lunar_display": lunar_context.get("display"),
    }


def build_metaphysics_seed(
    *,
    civil: datetime,
    timezone_name: str,
    input_offset_visible: bool,
    longitude: float | None,
    use_true_solar_time: bool,
    true_solar_explicit: bool = True,
) -> MetaphysicsSeed:
    """Correct a resolved civil clock once, without moving its physical epoch."""
    is_solar_time_applied = use_true_solar_time
    if is_solar_time_applied and longitude is None:
        if true_solar_explicit:
            raise ValueError("真太阳时修正需要 analysis_longitude")
        is_solar_time_applied = False
    clock = NominalClockLabel.from_local_datetime(civil)
    total_correction_minutes = 0.0
    receipt = None
    if is_solar_time_applied:
        assert longitude is not None
        adjustment = calculate_solar_time_adjustment(
            civil, timezone_name, longitude, strategy=SOLAR_TIME_STRATEGY_APPARENT
        )
        total_correction_minutes = adjustment["total_correction_minutes"]
        clock = clock.shifted(timedelta(minutes=total_correction_minutes))
        receipt = solar_time_receipt(
            civil_instant=civil,
            corrected_label=clock,
            timezone_name=timezone_name,
            longitude=longitude,
            adjustment=adjustment,
        )
    return assemble_metaphysics_seed(
        civil=civil,
        clock=clock,
        timezone_name=timezone_name,
        input_offset_visible=input_offset_visible,
        longitude=longitude,
        applied_true_solar=is_solar_time_applied,
        total_correction_minutes=total_correction_minutes,
        solar_time_adjustment=receipt,
    )


def build_analysis_seed(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_second: int = 0,
    analysis_timezone: str | None = None,
    analysis_utc_offset: str | None = None,
    timezone_field: str = "analysis_timezone",
    utc_offset_field: str = "analysis_utc_offset",
    analysis_longitude: float | None = None,
    use_true_solar_time: bool = False,
    true_solar_explicit: bool = True,
) -> MetaphysicsSeed:
    """Resolve numeric analysis input at its boundary, then use the domain owner."""
    timezone_name = analysis_timezone or DEFAULT_BIRTH_TIMEZONE
    civil = resolve_civil_clock(
        datetime(
            analysis_year,
            analysis_month,
            analysis_day,
            analysis_hour,
            analysis_minute,
            analysis_second,
        ),
        timezone_name,
        analysis_utc_offset,
        offset_field=utc_offset_field,
        timezone_field=timezone_field,
    )
    return build_metaphysics_seed(
        civil=civil,
        timezone_name=timezone_name,
        input_offset_visible=analysis_utc_offset is not None,
        longitude=analysis_longitude,
        use_true_solar_time=use_true_solar_time,
        true_solar_explicit=true_solar_explicit,
    )
