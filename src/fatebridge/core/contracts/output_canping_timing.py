"""Canping timing and interval series contracts."""

from typing import Any, Literal

from pydantic import model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_canping_rows import CanpingRow
from fatebridge.core.contracts.output_canping_schedule import CanpingScheduleBasis
from fatebridge.core.contracts.output_canping_solar import (
    CanpingSolarBoundary,
    CanpingSolarContext,
)
from fatebridge.core.contracts.output_chinese_calendar import Object


class CanpingSeries(PartialOutput):
    comparison_policy: Literal["retained_nominal_civil_point_v1"] | None = None
    year_boundaries: list[CanpingSolarBoundary] | None = None
    solar_context: CanpingSolarContext | None = None
    dayun: list[CanpingRow] | None = None
    element: str | None = None
    partName: str | None = None
    qiyunAge: int | None = None
    rows: list[CanpingRow] | None = None
    year_boundary: str | None = None
    birth_pillar_year: int | None = None
    age_policy: str | None = None

    @model_validator(mode="after")
    def coherent_annual_points(self) -> "CanpingSeries":
        previous_year = None
        for row in self.rows or []:
            if row.year is not None and previous_year is not None:
                if row.year != previous_year + 1:
                    raise ValueError("配运年序年份不连续。")
            previous_year = row.year
        context = self.solar_context
        if context is not None:
            if self.rows is not None and context.horizon_years is not None:
                if len(self.rows) != context.horizon_years:
                    raise ValueError("实际年序行数与声明的范围不一致。")
            if (
                self.birth_pillar_year is not None
                and context.origin_bazi_year is not None
            ):
                if self.birth_pillar_year != context.origin_bazi_year:
                    raise ValueError("年序起年与实际出生干支年不一致。")
        if (
            self.rows
            and self.rows[0].year is not None
            and self.birth_pillar_year is not None
        ):
            if self.rows[0].year != self.birth_pillar_year:
                raise ValueError("年序首行不是实际出生干支年。")
        return self


class CanpingTiming(PartialOutput):
    comparison_policy: Literal["retained_nominal_civil_point_v1"] | None = None
    solar_year_context: CanpingSolarContext | None = None
    profile_id: str | None = None
    method_id: str | None = None
    birth_at: str | None = None
    timezone: str | None = None
    start_at: str | None = None
    start_details: Object | None = None
    calendar_offset: Object | None = None
    calendar_policy: str | None = None
    reference_policy: str | None = None
    boundary_policy: str | None = None
    dst_policy: str | None = None
    ruleset_id: str | None = None
    ruleset_version: str | None = None
    source_title: str | None = None
    source_url: str | None = None
    source_pdf_pages: list[int] | None = None
    source_status: str | None = None
    calendar_scope: str | None = None
    heluo_period_distinction: str | None = None
    selected: CanpingRow | None = None
    schedule_basis: CanpingScheduleBasis | None = None
    first_row: CanpingRow | None = None
    first_period: CanpingRow | None = None

    @model_validator(mode="after")
    def coherent_schedule_source_map(self) -> "CanpingTiming":
        basis = self.schedule_basis
        known_profile = self.profile_id or (basis.profile_id if basis else None)
        known_start = self.start_at or (basis.actual_start_at if basis else None)
        if self.first_row is not None:
            if known_profile == "legacy_minggong_v1" or (
                basis is not None and basis.has_actual_date_mapping is False
            ):
                for key in (
                    "start_at",
                    "end_at",
                    "start_age",
                    "end_age",
                    "at",
                    "dayun_index",
                ):
                    if getattr(self.first_row, key) is not None:
                        raise ValueError(
                            "旧法首行仅为年龄标签，不能补实际日期或查询身份。"
                        )
            if self.first_period is not None:

                def agree(a: Any, b: Any) -> bool:
                    if a is None or b is None:
                        return True
                    if isinstance(a, dict) and isinstance(b, dict):
                        return all(agree(a[k], b[k]) for k in a.keys() & b.keys())
                    if isinstance(a, list) and isinstance(b, list):
                        return len(a) == len(b) and all(
                            agree(x, y) for x, y in zip(a, b)
                        )
                    return bool(a == b)

                if not agree(
                    self.first_row.model_dump(exclude_unset=True),
                    self.first_period.model_dump(exclude_unset=True),
                ):
                    raise ValueError("首行与首运的已返回事实不一致。")
        if basis is not None:
            if (
                self.start_at is not None
                and basis.actual_start_at is not None
                and self.start_at != basis.actual_start_at
            ):
                raise ValueError("配运来源回执与实际起运瞬间不一致。")
            if (
                self.profile_id is not None
                and basis.profile_id is not None
                and self.profile_id != basis.profile_id
            ):
                raise ValueError("配运来源回执与实际方法不一致。")
            if (
                self.calendar_offset is not None
                and basis.age_conversion_result is not None
            ):
                for key in (
                    self.calendar_offset.keys() & basis.age_conversion_result.keys()
                ):
                    actual = self.calendar_offset[key]
                    recorded = basis.age_conversion_result[key]
                    if type(actual) is not type(recorded) or actual != recorded:
                        raise ValueError("配运年龄折算回执与本次实际结果不一致。")
            if basis.calendar_mapping is not None:
                for key in (
                    "calendar_policy",
                    "reference_policy",
                    "boundary_policy",
                    "dst_policy",
                ):
                    actual = getattr(self, key)
                    recorded = basis.calendar_mapping.get(key)
                    if (
                        known_profile != "legacy_minggong_v1"
                        and actual is not None
                        and recorded is not None
                        and actual != recorded
                    ):
                        raise ValueError("配运日期映射回执与本次实际政策不一致。")
        if (
            self.first_period is not None
            and self.first_period.start_at is not None
            and known_start is not None
            and self.first_period.start_at != known_start
        ):
            raise ValueError("首运摘要与实际起运时刻不一致。")
        if self.first_period is not None and (
            known_profile == "legacy_minggong_v1"
            or basis is not None
            and basis.has_actual_date_mapping is False
        ):
            raise ValueError("旧命宫排法不能补成已核日期首运。")
        return self
