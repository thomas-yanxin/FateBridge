"""Input-clock resolution facts; no astronomical or classical verdict."""

from typing import Literal

from pydantic import Field

from fatebridge.core.contracts.output_base import PartialOutput


class RenCivilClockResolution(PartialOutput):
    method: str | None = None
    timezone: str | None = None
    input_utc_offset: str | None = None
    resolved_utc_offset: str | None = None
    wall_datetime: str | None = None
    was_ambiguous: bool | None = None
    fold: int | None = Field(default=None, ge=0, le=1)
    instant_utc: str | None = None
    timezone_rules: dict[str, str] | None = None
    timezone_source: (
        Literal["birth_timezone", "birth_place", "default_timezone"] | None
    ) = None
    timezone_resolved_place: str | None = None
    timezone_assumed: bool | None = None
    timezone_resolution_advisory: str | None = None


class RenRunyearAgeCalendar(PartialOutput):
    policy: Literal["one_timezone_lunar_year_age_v1"] | None = None
    timezone: str | None = None
    analysis_civil_datetime: str | None = None
    birth_lunar_year: int | None = None
    analysis_lunar_year: int | None = None
    year_boundary: Literal["正月初一00:00"] | None = None
    scope: str | None = None
