"""Bazi birth and day master output contracts."""

from typing import Annotated

from pydantic import Field, JsonValue

from fatebridge.core.contracts.output_base import FULL_FACT, PartialOutput
from fatebridge.core.contracts.output_bazi_evidence import EvidenceStructureProfile
from fatebridge.core.contracts.output_chinese_calendar import (
    CalendarContext,
    FourPillars,
    PersonInfo,
)
from fatebridge.core.contracts.output_classical_force import (
    ClassicalForceAdjudication,
    EngineeringStrengthIndex,
)
from fatebridge.core.contracts.output_classical_roots import ClassicalOverview
from fatebridge.core.receipt_models import Object


class DayMaster(PartialOutput):
    stem: str | None = None
    element: str | None = None
    polarity: str | None = None
    strength: str | None = Field(
        default=None,
        description="既有工程旺衰政策档；完整依据见engineering_index，不是classical_adjudication的原典力量结论",
    )
    engineering_index: Annotated[EngineeringStrengthIndex | None, FULL_FACT] = None
    classical_adjudication: Annotated[ClassicalForceAdjudication | None, FULL_FACT] = (
        None
    )
    assessment: Object | None = None


class BaziBirth(PartialOutput):
    classical: ClassicalOverview | None = None
    structure_profile: EvidenceStructureProfile | None = None
    day_master: DayMaster | None = None
    four_pillars: FourPillars | None = None
    favorable_elements: list[JsonValue] | None = None
    favorable_elements_status: Annotated[str | None, FULL_FACT] = None
    engineering_favorable_elements: Annotated[list[str] | None, FULL_FACT] = None
    element_distribution: Object | None = None
    person_info: PersonInfo | None = None
    calendar_context: CalendarContext | None = None
    patterns: Object | None = None
    ten_gods: Object | None = None
    analysis_date: str | None = None
