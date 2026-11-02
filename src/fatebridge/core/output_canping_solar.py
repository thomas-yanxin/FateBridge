"""Projection-compatible receipts for the actual Canping annual boundaries."""

from typing import Dict, List, Literal, Optional

from pydantic import Field, JsonValue, model_validator

from fatebridge.core.output_base import PartialOutput
from fatebridge.utils.civil_clock import parse_iso_datetime


class CanpingSolarBoundary(PartialOutput):
    year: Optional[int] = None
    record: Optional[Dict[str, JsonValue]] = None
    instant_utc: Optional[str] = None
    ephemeris_retflags: Optional[List[int]] = None
    ephemeris_library_version: Optional[str] = None
    selection: Optional[
        Literal["ordinary_public_year_grid", "bounded_derived_lichun_event"]
    ] = None

    @model_validator(mode="after")
    def same_instant(self) -> "CanpingSolarBoundary":
        if self.instant_utc is not None:
            at = parse_iso_datetime(self.instant_utc)
            if at.utcoffset() is None:
                raise ValueError("立春边界须为绝对时刻。")
            civil = (self.record or {}).get("datetime_with_offset")
            if isinstance(civil, str) and at != parse_iso_datetime(civil):
                raise ValueError("民用立春与UTC边界不一致。")
        if self.record is not None and self.record.get("name", "立春") != "立春":
            raise ValueError("参平年界须为立春。")
        return self


class CanpingSolarContext(PartialOutput):
    policy_id: Optional[str] = None
    origin_civil_year: Optional[int] = None
    origin_bazi_year: Optional[int] = None
    birth_instant_utc: Optional[str] = None
    timezone: Optional[str] = None
    horizon_years: Optional[int] = None
    boundary_count: Optional[int] = None
    boundary_receipts_sha256: Optional[str] = None
    observed_models: Optional[List[str]] = None
    derived_event_years: Optional[List[int]] = None
    de440_projection_profile_used: Optional[bool] = None
    de440_extended_projection_profile_used: Optional[bool] = None
    registered_public_input_years: Optional[List[int]] = None
    qualified_origin_civil_year_ranges: Optional[List[List[int]]] = None
    public_model_years_extended: Optional[Literal[False]] = Field(
        default=None,
        description="仅说明本派生许可不扩大独立公开年界，不陈述配置本身的公开年份范围。",
    )
    not_a_lifespan_estimate: Optional[Literal[True]] = None
    leap_table_expires_at: Optional[str] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def complete_horizon(self) -> "CanpingSolarContext":
        if self.horizon_years is not None:
            if not 1 <= self.horizon_years <= 120:
                raise ValueError("年序范围须为1至120。")
            if (
                self.boundary_count is not None
                and self.boundary_count != self.horizon_years + 1
            ):
                raise ValueError("年序边界不能截短。")
        return self
