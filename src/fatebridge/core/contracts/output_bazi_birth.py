"""Bazi birth and day master output contracts."""

from __future__ import annotations

from typing import Annotated

from pydantic import JsonValue

from fatebridge.core.contracts.output_base import (
    FULL_FACT,
    OpenJsonValue,
    PartialOutput,
)
from fatebridge.core.contracts.output_bazi_evidence import (
    ClassicalForceSummary,
    EvidenceStructureProfile,
)
from fatebridge.core.contracts.output_chinese_calendar import (
    CalendarContext,
    FourPillars,
    PersonInfo,
)
from fatebridge.core.receipt_models import Object


class DayMaster(PartialOutput):
    stem: str | None = None
    element: str | None = None
    polarity: str | None = None
    strength: str | None = None
    support_share: float | None = None
    life_stages: dict[str, str] | None = None
    changsheng_school: str | None = None
    classical_adjudication: Annotated[ClassicalForceSummary | None, FULL_FACT] = None
    engineering_index: dict[str, OpenJsonValue] | None = None


class BaziBirth(PartialOutput):
    engine: str | None = None
    time_algorithm: str | None = None
    analysis_date: str | None = None
    person_info: PersonInfo | None = None
    four_pillars: FourPillars | None = None
    three_origins: dict[str, OpenJsonValue] | None = None
    taixi: dict[str, OpenJsonValue] | None = None
    day_master: DayMaster | None = None
    element_distribution: Object | None = None
    element_seasonal_phase: dict[str, str] | None = None
    favorable_elements: list[JsonValue] | None = None
    favorable_elements_status: Annotated[str | None, FULL_FACT] = None
    avoid_elements: list[str] | None = None
    structure_profile: EvidenceStructureProfile | None = None
    intra_month_duty: dict[str, OpenJsonValue] | None = None
    ten_gods: Object | None = None
    patterns: Object | None = None
    kongwang: dict[str, OpenJsonValue] | None = None
    shensha: list[dict[str, OpenJsonValue]] | None = None
    shensha_triggered: list[dict[str, OpenJsonValue]] | None = None
    three_origins_shensha: list[dict[str, OpenJsonValue]] | None = None
    calendar_context: CalendarContext | None = None
    analysis_calendar_context: CalendarContext | None = None
    timing_overview: dict[str, OpenJsonValue] | None = None
