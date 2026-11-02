"""Input-clock resolution facts; no astronomical or classical verdict."""

from typing import Dict, Literal, Optional

from pydantic import Field

from .output_base import PartialOutput


class RenCivilClockResolution(PartialOutput):
    method: Optional[str] = None
    timezone: Optional[str] = None
    input_utc_offset: Optional[str] = None
    resolved_utc_offset: Optional[str] = None
    wall_datetime: Optional[str] = None
    was_ambiguous: Optional[bool] = None
    fold: Optional[int] = Field(default=None, ge=0, le=1)
    instant_utc: Optional[str] = None
    timezone_rules: Optional[Dict[str, str]] = None
    timezone_source: Optional[
        Literal["birth_timezone", "birth_place", "default_timezone"]
    ] = None
    timezone_resolved_place: Optional[str] = None
    timezone_assumed: Optional[bool] = None
    timezone_resolution_advisory: Optional[str] = None


class RenRunyearAgeCalendar(PartialOutput):
    policy: Optional[Literal["one_timezone_lunar_year_age_v1"]] = None
    timezone: Optional[str] = None
    analysis_civil_datetime: Optional[str] = None
    birth_lunar_year: Optional[int] = None
    analysis_lunar_year: Optional[int] = None
    year_boundary: Optional[Literal["正月初一00:00"]] = None
    scope: Optional[str] = None
