"""Projection-compatible civil clock and annual lunar evidence."""

from pydantic import Field, JsonValue

from fatebridge.core.contracts.output_base import PartialOutput


class TaiyiCivilClockResolution(PartialOutput):
    method: str | None = None
    timezone: str | None = None
    wall_datetime: str | None = None
    input_utc_offset: str | None = None
    resolved_utc_offset: str | None = None
    fold: int | None = Field(default=None, ge=0, le=1)
    instant_utc: str | None = None
    timezone_rules: dict[str, str] | None = None
    scope: str | None = None


class TaiyiCivilLunarCalendar(PartialOutput):
    civil_date: str | None = None
    year: int | None = None
    month: int | None = None
    day: int | None = None
    is_leap_month: bool | None = None
    display: str | None = None
    clock_basis: str | None = None
    provider: str | None = None
    conversion_source: dict[str, JsonValue] | None = None
    conversion_source_status: str | None = None
    scope: str | None = None
