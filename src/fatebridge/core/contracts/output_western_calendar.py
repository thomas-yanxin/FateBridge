"""Western civil and event clock outputs."""

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_chart_relationships import BirthClockConversion
from fatebridge.core.contracts.output_clock_labels import (
    WesternUTCRepresentation as WesternUTCRepresentation,
)
from fatebridge.core.contracts.output_midpoint_geometry import PhysicalEphemerisSource
from fatebridge.core.contracts.output_ut1 import C04UT1Evidence


class CivilDateParts(PartialOutput):
    year: int | None = None
    month: int | None = None
    day: int | None = None


class CivilClockParts(PartialOutput):
    hour: int | None = None
    minute: int | None = None
    second: int | None = None


class WesternCivilCalendarConversion(PartialOutput):
    method_id: str | None = None
    input_calendar: str | None = None
    input_date: CivilDateParts | None = None
    input_clock: CivilClockParts | None = None
    normalized_calendar: str | None = None
    normalized_local_datetime: str | None = None
    normalized_date_representable: bool | None = None
    normalized_local_datetime_scope: str | None = None
    date_label_jdn: int | None = None
    date_label_jdn_scope: str | None = None
    same_label_gregorian_date_valid: bool | None = None
    same_label_gregorian_offset_days: int | None = None
    calendar_conversion_performed: bool | None = None
    clock_preserved: bool | None = None
    automatic_regional_reform_applied: bool | None = None
    year_numbering: str | None = None
    calendar_selection_source: str | None = None
    timezone_order: str | None = None
    historical_clock_reconstruction_performed: bool | None = None
    scope: str | None = None


class WesternHourOriginConversion(PartialOutput):
    method_id: str | None = None
    input_hour_origin: str | None = None
    input_calendar: str | None = None
    input_date: CivilDateParts | None = None
    input_clock: CivilClockParts | None = None
    source_date_label_jdn: int | None = None
    source_date_gregorian_representable: bool | None = None
    calendar_normalized_label: str | None = None
    normalized_wall_calendar: str | None = None
    normalized_wall_datetime: str | None = None
    normalized_date_label_jdn: int | None = None
    day_carry: int | None = None
    nominal_label_shift_minutes: int | None = None
    normalization_performed: bool | None = None
    physical_duration_applied: bool | None = None
    timezone_applied: bool | None = None
    source_clock_identification_performed: bool | None = None
    selection_source: str | None = None
    rule_source: str | None = None
    rule_source_url: str | None = None
    source_pages: list[int] | None = None
    scope: str | None = None


class EventSolarObservation(PartialOutput):
    phase: str | None = None
    julian_day_ut1: float | None = None
    julian_day_tt: float | None = None
    source_index: int | None = None


class EventSolarSources(PartialOutput):
    status: str | None = None
    physical_ephemeris_sources: list[PhysicalEphemerisSource] | None = None
    has_unidentified_sources: bool | None = None
    observations: list[EventSolarObservation] | None = None
    scope: str | None = None


class EventSolarConversion(BirthClockConversion):
    solar_source_comparison: EventSolarSources | None = None


class EventClockChartComparison(PartialOutput):
    status: str | None = None
    chart_sun_source: PhysicalEphemerisSource | None = None
    has_unidentified_sources: bool | None = None
    scope: str | None = None


class WesternEventClockConversion(PartialOutput):
    ut1_reference: C04UT1Evidence | None = None
    method_id: str | None = None
    input_hour_origin: str | None = None
    hour_origin_conversion: WesternHourOriginConversion | None = None
    input_clock_basis: str | None = None
    input_wall_datetime: str | None = None
    input_granularity: str | None = None
    input_timezone: str | None = None
    effective_civil_timezone: str | None = None
    timezone_selection_source: str | None = None
    chart_timezone: str | None = None
    converted_utc: str | None = None
    utc_representation: WesternUTCRepresentation | None = None
    julian_day_tt: float | None = None
    julian_day_ut1: float | None = None
    time_scale_method: str | None = None
    modeled_solar_conversion_performed: bool | None = None
    source_clock_identification_performed: bool | None = None
    input_clock_accuracy_certified: bool | None = None
    solar_conversion: EventSolarConversion | None = None
    clock_chart_source_comparison: EventClockChartComparison | None = None
    scope: str | None = None
