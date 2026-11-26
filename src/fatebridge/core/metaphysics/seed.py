"""Shared civil-input, nominal-clock and calendar assembly for technique seeds."""

from __future__ import annotations

from datetime import datetime, timedelta

from fatebridge.core.almanac import build_calendar_context, get_adjacent_solar_terms
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.utils.civil_clock import resolve_civil_clock
from fatebridge.utils.civil_time import NominalClockLabel
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_APPARENT,
    calculate_solar_time_adjustment,
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
