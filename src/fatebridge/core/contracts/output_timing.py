"""Projectable structural contracts for the shared BaZi timing engine."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, ValidationInfo, model_validator

from fatebridge.core.contracts.output_base import OpenJsonValue, PartialOutput
from fatebridge.core.contracts.output_civil_time import CivilPointEvidence
from fatebridge.utils.civil_time import ZonedCalendar, nominal_calendar_bracket


class AnalysisReference(PartialOutput):
    method_id: Literal["bazi_analysis_instant_v1"] | None = None
    basis: (
        Literal[
            "implicit_execution_clock",
            "explicit_components",
            "declared_partial_components",
            "explicit_age_reference",
        ]
        | None
    ) = None
    analysis_datetime: str | None = None
    utc_datetime: str | None = None
    timezone: str | None = None
    fold: int | None = Field(default=None, ge=0, le=1)
    precision: Literal["execution_clock", "minute"] | None = None
    provided_fields: list[str] | None = None
    defaulted_from_clock: list[str] | None = None
    fixed_defaults: dict[str, int] | None = None
    scope: str | None = None


class TimingNode(PartialOutput):
    id: str | None = None
    scope: str | None = None
    layer: str | None = None
    stem: str | None = None
    branch: str | None = None
    pillar: str | None = None


class TimingRelation(PartialOutput):
    id: str | None = None
    rule_id: str | None = None
    participants: list[str] | None = None
    scope: str | None = None
    source: str | None = None
    target: str | None = None
    group: str | None = None
    bureau: str | None = None
    detail: str | None = None
    complete: bool | None = None
    traditional_label: str | None = None


class TimingInteractions(PartialOutput):
    nodes: list[TimingNode] | None = None
    ten_god_context: list[dict[str, OpenJsonValue]] | None = None
    relations: list[TimingRelation] | None = None
    rule_trace: list[str] | None = None


class PillarsCandidate(PartialOutput):
    pillars: dict[str, str] | None = None
    first_sample_at: str | None = None
    last_sample_at: str | None = None
    sample_count: int | None = None
    event_probe_count: int | None = None
    first_event_probe_at: str | None = None
    last_event_probe_at: str | None = None
    evidence_sources: (
        list[Literal["minute_grid", "event_probe", "dayun_event_probe"]] | None
    ) = None


class BirthTimeEvent(PartialOutput):
    kind: (
        Literal[
            "jie",
            "civil_clock",
            "solar_clock",
            "dayun_nominal_month_carry",
            "dayun_civil_clock",
            "dayun_future_civil_gap_end",
            "dayun_future_civil_fold_end",
            "dayun_analysis_moment",
            "dayun_decade_leap_clip",
        ]
        | None
    ) = None
    name: str | None = None
    lower_utc: str | None = None
    upper_utc: str | None = None
    at_utc: str | None = None
    bracket_width_seconds: float | None = None
    civil_point: CivilPointEvidence | None = None
    reference_point: CivilPointEvidence | None = None
    bracket_basis: Literal["nominal_gregorian_microsecond_enclosure_v1"] | None = None
    source: dict[str, str] | None = None

    @model_validator(mode="after")
    def preserve_nominal_point_bracket(self, info: ValidationInfo) -> "BirthTimeEvent":
        if self.bracket_basis != "nominal_gregorian_microsecond_enclosure_v1":
            return self
        if info.context and info.context.get("full_result"):
            if (
                self.civil_point is None
                or self.lower_utc is None
                or self.upper_utc is None
            ):
                raise ValueError("完整名义事件括区间须保留主点及两端标签")
            if (
                self.kind == "dayun_nominal_month_carry"
                and self.reference_point is None
            ):
                raise ValueError("完整名义月进位须保留同次实际参考节令主点")
        day = self.civil_point.known_day() if self.civil_point is not None else None
        if day is None:
            return self
        expected_lower, expected_upper = nominal_calendar_bracket(day)
        if self.lower_utc is not None:
            lower = ZonedCalendar.from_isoformat(self.lower_utc).utc
            if lower != expected_lower:
                raise ValueError("名义事件下端须为保留坐标的微秒格点下包")
        if self.upper_utc is not None:
            upper = ZonedCalendar.from_isoformat(self.upper_utc).utc
            if upper != expected_upper:
                raise ValueError("名义事件上端须为保留坐标的微秒格点上包")
        if self.at_utc is not None:
            if ZonedCalendar.from_isoformat(self.at_utc).utc != expected_upper:
                raise ValueError("名义事件代表标签须为括区间上端，不冒充未舍入主点")
        if self.bracket_width_seconds is not None:
            width = float(
                (expected_upper.julian_day_exact() - expected_lower.julian_day_exact())
                * 86400
            )
            if self.bracket_width_seconds != width:
                raise ValueError("名义事件括区间宽度须与所声明坐标外包一致")
        return self


class BirthTimeSensitivity(PartialOutput):
    method_id: str | None = None
    status: str | None = None
    status_scope: str | None = None
    dayun_assessment_status: str | None = None
    unavailable_fields: list[str] | None = None
    boundary_ranges_vary: bool | None = None
    uncertainty_minutes: int | None = None
    sample_count: int | None = None
    event_probe_count: int | None = None
    natal_event_probe_count: int | None = None
    dayun_event_probe_count: int | None = None
    additional_event_probe_count: int | None = None
    total_assessed_instants: int | None = None
    birth_at_range: dict[str, str] | None = None
    sampling_policy: str | None = None
    boundary_range_scope: str | None = None
    event_analysis: dict[str, OpenJsonValue] | None = None
    dayun_event_analysis: dict[str, OpenJsonValue] | None = None
    pillars_candidates: list[PillarsCandidate] | None = None
    current_dayun_candidates: list[dict[str, OpenJsonValue]] | None = None
    dayun_boundary_ranges: list[dict[str, OpenJsonValue]] | None = None
    affected_fields: list[str] | None = None
    interpretation_scope: str | None = None
