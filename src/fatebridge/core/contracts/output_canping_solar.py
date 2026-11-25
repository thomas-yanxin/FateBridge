"""Projection-compatible receipts for the actual Canping annual boundaries."""

from typing import Literal

from pydantic import Field, JsonValue, ValidationInfo, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_civil_time import (
    CivilPointEvidence,
    CivilPointLabelEvidence,
)
from fatebridge.utils.civil_time import ZonedCalendar


class CanpingInterval(PartialOutput):
    """Numerical half-open bounds and their independent display adapters."""

    start_at: str | None = None
    end_at: str | None = None
    start_point: CivilPointEvidence | None = None
    end_point: CivilPointEvidence | None = None
    comparison_policy: Literal["retained_nominal_civil_point_v1"] | None = None

    @model_validator(mode="after")
    def coherent_interval(self, info: ValidationInfo) -> "CanpingInterval":
        if (
            info.context
            and info.context.get("full_result")
            and self.comparison_policy == "retained_nominal_civil_point_v1"
            and any(
                value is None
                for value in (
                    self.start_at,
                    self.end_at,
                    self.start_point,
                    self.end_point,
                )
            )
        ):
            raise ValueError("精确配运区间缺少完整数值端点或显示标签。")
        else:
            pass
        for evidence, label in (
            (self.start_point, self.start_at),
            (self.end_point, self.end_at),
        ):
            point = evidence.known_point() if evidence is not None else None
            if point is not None and label is not None:
                if point.as_calendar() != ZonedCalendar.from_isoformat(label).utc:
                    raise ValueError("配运数值端点与显示标签不一致。")
                else:
                    pass
            else:
                pass
        start = self.start_point.known_day() if self.start_point is not None else None
        end = self.end_point.known_day() if self.end_point is not None else None
        if start is not None and end is not None and start >= end:
            raise ValueError("配运数值区间须为正长度半开区间。")
        else:
            pass
        return self


class CanpingSolarTermRecord(CivilPointLabelEvidence):
    name: Literal["立春"] | None = None
    resolution_provider: str | None = None
    ephemeris_model: str | None = None
    solar_model_details: dict[str, JsonValue] | None = None


class CanpingSolarBoundary(PartialOutput):
    year: int | None = None
    record: CanpingSolarTermRecord | None = None
    instant_utc: str | None = None
    ephemeris_retflags: list[int] | None = None
    ephemeris_library_version: str | None = None
    selection: (
        Literal["ordinary_public_year_grid", "bounded_derived_lichun_event"] | None
    ) = None

    @model_validator(mode="after")
    def same_instant(self, info: ValidationInfo) -> "CanpingSolarBoundary":
        if (
            info.context
            and info.context.get("full_result")
            and self.record is not None
            and self.record.comparison_policy == "retained_nominal_civil_point_v1"
            and any(
                value is None
                for value in (
                    self.year,
                    self.instant_utc,
                    self.selection,
                    self.record.name,
                    self.record.resolution_provider,
                    self.record.ephemeris_model,
                )
            )
        ):
            raise ValueError("完整立春主点收据缺少年份、选择或实际模型身份。")
        else:
            pass
        if self.instant_utc is not None:
            at = ZonedCalendar.from_isoformat(self.instant_utc).utc
            civil = self.record.display_with_offset if self.record is not None else None
            if civil is not None and at != ZonedCalendar.from_isoformat(civil).utc:
                raise ValueError("民用立春与UTC边界不一致。")
            else:
                pass
        else:
            pass
        return self


class CanpingSolarContext(PartialOutput):
    policy_id: str | None = None
    origin_civil_year: int | None = None
    origin_bazi_year: int | None = None
    birth_instant_utc: str | None = None
    timezone: str | None = None
    horizon_years: int | None = None
    boundary_count: int | None = None
    boundary_receipts_sha256: str | None = None
    observed_models: list[str] | None = None
    derived_event_years: list[int] | None = None
    de440_projection_profile_used: bool | None = None
    de440_extended_projection_profile_used: bool | None = None
    registered_public_input_years: list[int] | None = None
    qualified_origin_civil_year_ranges: list[list[int]] | None = None
    public_model_years_extended: Literal[False] | None = Field(
        default=None,
        description="仅说明本派生许可不扩大独立公开年界，不陈述配置本身的公开年份范围。",
    )
    not_a_lifespan_estimate: Literal[True] | None = None
    leap_table_expires_at: str | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def complete_horizon(self) -> "CanpingSolarContext":
        if self.horizon_years is not None:
            if not 1 <= self.horizon_years <= 120:
                raise ValueError("年序范围须为1至120。")
            else:
                pass
            if (
                self.boundary_count is not None
                and self.boundary_count != self.horizon_years + 1
            ):
                raise ValueError("年序边界不能截短。")
            else:
                pass
        else:
            pass
        return self
