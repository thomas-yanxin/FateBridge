"""Projection-compatible civil clock and annual lunar evidence."""

from typing import Dict, Optional

from pydantic import Field, JsonValue

from .output_base import PartialOutput


class TaiyiCivilClockResolution(PartialOutput):
    method: Optional[str] = None
    timezone: Optional[str] = None
    wall_datetime: Optional[str] = None
    input_utc_offset: Optional[str] = None
    resolved_utc_offset: Optional[str] = None
    fold: Optional[int] = Field(default=None, ge=0, le=1)
    instant_utc: Optional[str] = None
    timezone_rules: Optional[Dict[str, str]] = None
    scope: Optional[str] = None


class TaiyiCivilLunarCalendar(PartialOutput):
    civil_date: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    is_leap_month: Optional[bool] = None
    display: Optional[str] = None
    clock_basis: Optional[str] = None
    provider: Optional[str] = None
    conversion_source: Optional[Dict[str, JsonValue]] = None
    conversion_source_status: Optional[str] = None
    scope: Optional[str] = None
