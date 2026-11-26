"""Stable nested facts, with projection-compatible optional fields.

Validate existing payloads without reserialization; dynamic map keys and
extension fields remain open. Definitions follow the service builders.
"""

from typing import Literal

from pydantic import ConfigDict

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_bazi_evidence import BaziEvidenceChain
from fatebridge.core.contracts.output_chinese_calendar import CalendarContext, SolarTerm


class TimingOverrides(PartialOutput):
    dayun_pillar: bool | None = None
    liunian_pillar: bool | None = None


class DimensionTimingContext(PartialOutput):
    analysis_date: str | None = None
    analysis_datetime: str | None = None
    timezone: str | None = None
    input_granularity: Literal["date"] | None = None
    anchor_policy: Literal["local_midnight"] | None = None
    year_boundary_policy: Literal["lichun_exact_moment"] | None = None
    boundary_status: Literal["year_boundary_day", "not_year_boundary_day"] | None = None
    boundaries_on_date: list[SolarTerm] | None = None
    boundary_scope: str | None = None
    hourly_evidence: dict[str, OpenJsonValue] | None = None
    dayun_pillar: str | None = None
    liunian_pillar: str | None = None
    source: str | None = None
    dayun_status: str | None = None
    limitations: list[str] | None = None
    # The timing engine reports fractional years (for example 28.7).
    dayun_age: float | None = None
    dayun_age_basis: str | None = None
    dayun_selection_basis: str | None = None
    dayun_start_at: str | None = None
    dayun_end_at: str | None = None
    overridden: TimingOverrides | None = None


class DimensionOutput(PartialOutput):
    model_config = ConfigDict(extra="forbid")

    calendar_context: CalendarContext | None = None
    timing_context: DimensionTimingContext | None = None
    evidence_chain: BaziEvidenceChain | None = None
