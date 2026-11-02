"""Shared birth primitives independent of any analysis response renderer."""

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from fatebridge.core.almanac import build_calendar_context
from fatebridge.core.calendar import BaZiCalendar
from fatebridge.core.elements import ElementAnalysis
from fatebridge.utils.birth_clock import birth_clock_input_receipt
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.data import Element
from fatebridge.utils.solar_time import NormalizedBirthTime, normalize_birth_time


@dataclass(frozen=True)
class BirthComputationContext:
    """Shared deterministic birth-computation primitives for heavy services."""

    person: PersonInfo
    normalized_birth_time: NormalizedBirthTime
    birth_pillars: Dict[str, Tuple[str, str]]
    birth_calendar_context: Dict[str, Any]
    element_analysis: Dict[str, Any]
    original_element_counts: Dict[Element, float]


def build_birth_computation_context(person: PersonInfo) -> BirthComputationContext:
    """Build the shared birth context once so downstream services can reuse it."""
    normalized_birth_time = normalize_birth_time(person)
    corrected_birth_datetime = normalized_birth_time.corrected_datetime
    birth_pillars = BaZiCalendar.get_four_pillars(
        corrected_birth_datetime,
        timezone_name=normalized_birth_time.timezone,
        civil_datetime=normalized_birth_time.input_datetime,
    )
    birth_calendar_context = build_calendar_context(
        corrected_birth_datetime,
        timezone_name=normalized_birth_time.timezone,
        pillars=birth_pillars,
        civil_datetime=normalized_birth_time.input_datetime,
    )
    birth_calendar_context["birth_time_input"] = birth_clock_input_receipt(
        person, normalized_birth_time
    )
    element_analysis = ElementAnalysis.comprehensive_analysis(birth_pillars)
    # Raw distributions omit elements whose count is zero.
    raw_counts = element_analysis["day_master"]["element_distribution_raw"]

    return BirthComputationContext(
        person=person,
        normalized_birth_time=normalized_birth_time,
        birth_pillars=birth_pillars,
        birth_calendar_context=birth_calendar_context,
        element_analysis=element_analysis,
        original_element_counts={
            element: float(raw_counts.get(element.value, 0.0)) for element in Element
        },
    )
