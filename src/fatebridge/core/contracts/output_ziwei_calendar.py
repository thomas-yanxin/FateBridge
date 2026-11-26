"""Ziwei civil-time and calendar output contracts."""

from typing import Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_chinese_calendar import LunarDate


class ZiweiMinuteSensitivity(PartialOutput):
    method_id: str | None = None
    clock_stage: Literal["after_normalization_before_day_divide"] | None = None
    birth_seconds_supplied: bool | None = None
    base_second: int | None = None
    endpoint_seconds: list[float] | None = None
    endpoint_placement_datetimes: list[str] | None = None
    endpoint_hour_branches: list[str] | None = None
    crosses_hour_branch: bool | None = None
    crosses_placement_date: bool | None = None


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
    minute_sensitivity: ZiweiMinuteSensitivity | None = None


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


class ZiweiCalendarBasis(PartialOutput):
    method_id: str | None = None
    placement_clock: str | None = None
    placement_datetime: str | None = None
    civil_datetime: str | None = None
    civil_instant_utc: str | None = None
    apparent_solar_datetime: str | None = None
    timezone: str | None = None
    day_divide: Literal["current", "forward"] | None = None
    late_zi_rollover_applied: bool | None = None
    date_shift_days: int | None = None
    placement_lunar_date: LunarDate | None = None
    civil_date_lunar_date: LunarDate | None = None
    reference_datetime_utc_plus_08: str | None = None
    reference_lunar_date: LunarDate | None = None
    day_boundary: str | None = None
    time_input: ZiweiTimeInput | None = None
    civil_clock: ZiweiCivilClock | None = None


class ZiweiHoroscopeCalendarBasis(PartialOutput):
    birth: ZiweiCalendarBasis | None = None
    target: ZiweiCalendarBasis | None = None
    nominal_age_rule: str | None = None
