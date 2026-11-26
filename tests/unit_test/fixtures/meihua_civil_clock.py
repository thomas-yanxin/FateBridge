"""Shared frozen civil clock inputs for Meihua boundary tests."""

import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from typing_extensions import NotRequired

CIVIL_CLOCK_FIXTURE = Path(__file__).parents[2] / "fixtures/meihua_civil_clock_v1"
CIVIL_CLOCK_CASES = json.loads((CIVIL_CLOCK_FIXTURE / "cases.json").read_text())


class CivilClockInput(TypedDict):
    wall: str
    zone: str
    offset: str | None


class CivilClockParameters(TypedDict):
    analysis_year: int
    analysis_month: int
    analysis_day: int
    analysis_hour: int
    analysis_minute: int
    analysis_timezone: str
    analysis_utc_offset: NotRequired[str]


def civil_clock_parameters(case: CivilClockInput) -> CivilClockParameters:
    """Build a request and retain the difference between omitted and reported offset."""
    wall_clock = datetime.fromisoformat(case["wall"])
    parameters: CivilClockParameters = {
        "analysis_year": wall_clock.year,
        "analysis_month": wall_clock.month,
        "analysis_day": wall_clock.day,
        "analysis_hour": wall_clock.hour,
        "analysis_minute": wall_clock.minute,
        "analysis_timezone": case["zone"],
    }
    if case["offset"] is not None:
        parameters["analysis_utc_offset"] = case["offset"]
    else:
        pass
    return parameters
