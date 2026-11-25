"""Ziwei civil-time and calendar evidence."""

from typing import Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_chinese_calendar import LunarDate


class ZiweiMinuteSensitivity(PartialOutput):
    method_id: str | None = None
    assumption: str | None = None
    birth_seconds_supplied: bool | None = None
    base_second: int | None = None
    endpoint_seconds: list[float] | None = None
    endpoint_placement_datetimes: list[str] | None = None
    endpoint_hour_branches: list[str] | None = None
    crosses_hour_branch: bool | None = None
    crosses_placement_date: bool | None = None
    endpoints_are_alternative_birth_facts: bool | None = None
    observed_birth_precision_certified: bool | None = None
    scope: str | None = None


class ZiweiTimeInput(PartialOutput):
    method_id: str | None = None
    status: str | None = None
    requested: bool | None = None
    explicitly_requested: bool | None = None
    applied: bool | None = None
    components_computed: bool | None = None
    timezone: str | None = None
    timezone_source: str | None = None
    timezone_resolved_place: str | None = None
    timezone_assumed: bool | None = None
    timezone_rules: dict[str, str] | None = None
    longitude: float | None = None
    longitude_source: str | None = None
    resolved_place: str | None = None
    resolution_level: str | None = None
    resolution_advisory: str | None = None
    longitude_correction_minutes: float | None = None
    equation_of_time_minutes: float | None = None
    daylight_saving_minutes: float | None = None
    total_correction_minutes: float | None = None
    applied_delta_seconds: float | None = None
    solar_time_strategy: str | None = None
    equation_of_time_method: str | None = None
    equation_of_time_time_scale: str | None = None
    seconds_are_derived_not_birth_accuracy: bool | None = None
    minute_sensitivity: ZiweiMinuteSensitivity | None = None
    advisories: list[str] | None = None
    precision_scope: str | None = None
    source_basis: dict[str, str] | None = None


class ZiweiCivilClock(PartialOutput):
    method_id: str | None = None
    selection: str | None = None
    timezone: str | None = None
    resolved_utc_offset: str | None = None
    wall_datetime: str | None = None
    was_ambiguous: bool | None = None
    fold: int | None = Field(default=None, ge=0, le=1)
    instant_utc: str | None = None
    timezone_rules: dict[str, str] | None = None


class ZiweiDateReference(PartialOutput):
    publisher: str | None = None
    title: str | None = None
    url: str | None = None
    raw_sha256: str | None = None
    date_scope: list[str] | None = None
    role: str | None = None


class ZiweiDateLookupProvenance(PartialOutput):
    solar_date: str | None = None
    status: Literal["available", "unavailable"] | None = None
    implementation_provider: str | None = None
    printed_date_reference: str | None = None
    applied_year_info_correction: str | None = None


class ZiweiDateConversionProvenance(PartialOutput):
    method_id: str | None = None
    lookups: dict[str, ZiweiDateLookupProvenance] | None = None
    implementation_sources: dict[str, dict[str, str]] | None = None
    printed_date_references: dict[str, ZiweiDateReference] | None = None
    implementation_data_is_independent_validation: Literal[False] | None = None
    historical_clock_policy_verified: Literal[False] | None = None


class ZiweiCalendarBasis(PartialOutput):
    method_id: str | None = None
    placement_clock: str | None = None
    placement_datetime: str | None = None
    civil_datetime: str | None = None
    timezone: str | None = None
    date_shift_days: int | None = None
    placement_lunar_date: LunarDate | None = None
    civil_date_lunar_date: LunarDate | None = None
    reference_datetime_utc_plus_08: str | None = None
    reference_lunar_date: LunarDate | None = None
    date_lookup_convention: str | None = None
    day_boundary: str | None = None
    solar_terms_basis: str | None = None
    classical_clock_rule_verified: bool | None = None
    source_scope: str | None = None
    reference_source: str | None = None
    date_conversion_provenance: ZiweiDateConversionProvenance | None = None
    time_input: ZiweiTimeInput | None = None
    civil_clock: ZiweiCivilClock | None = None


class ZiweiHoroscopeCalendarBasis(PartialOutput):
    birth: ZiweiCalendarBasis | None = None
    target: ZiweiCalendarBasis | None = None
    nominal_age_rule: str | None = None
    age_boundary_classically_verified: bool | None = None
