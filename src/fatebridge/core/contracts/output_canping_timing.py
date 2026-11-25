"""Canping timing and interval series contracts."""

from typing import Any, Literal

from pydantic import ValidationInfo, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_canping_rows import CanpingRow
from fatebridge.core.contracts.output_canping_schedule import CanpingScheduleBasis
from fatebridge.core.contracts.output_canping_solar import (
    CanpingSolarBoundary,
    CanpingSolarContext,
)
from fatebridge.core.contracts.output_chinese_calendar import Object
from fatebridge.utils.civil_time import ZonedCalendar


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
    def coherent_annual_points(self, info: ValidationInfo) -> "CanpingSeries":
        exact = self.comparison_policy == "retained_nominal_civil_point_v1"
        full = bool(info.context and info.context.get("full_result"))
        if (
            full
            and (
                self.year_boundary == "lichun"
                or self.solar_context is not None
                or self.year_boundaries is not None
            )
            and not exact
        ):
            raise ValueError("实际立春年序缺少主点比较政策。")
        else:
            pass
        if (
            full
            and exact
            and (
                not self.rows
                or not self.year_boundaries
                or self.birth_pillar_year is None
                or self.solar_context is None
                or any(
                    value is None
                    for value in (
                        self.solar_context.birth_instant_utc,
                        self.solar_context.timezone,
                        self.solar_context.origin_civil_year,
                        self.solar_context.origin_bazi_year,
                        self.solar_context.horizon_years,
                        self.solar_context.boundary_count,
                    )
                )
            )
        ):
            raise ValueError("完整精确年序缺少出生、范围或实际年界。")
        else:
            pass
        boundaries: dict[int, CanpingSolarBoundary] = {}
        for boundary in self.year_boundaries or []:
            if boundary.year is not None:
                if boundary.year in boundaries:
                    raise ValueError("立春年界年份重复。")
                else:
                    pass
                boundaries[boundary.year] = boundary
            else:
                pass
            if (
                full
                and exact
                and (
                    boundary.year is None
                    or boundary.record is None
                    or boundary.record.comparison_policy != self.comparison_policy
                    or boundary.record.civil_point is None
                )
            ):
                raise ValueError("精确年序缺少实际立春主点。")
            else:
                pass
        context = self.solar_context
        birth = (
            ZonedCalendar.from_isoformat(
                context.birth_instant_utc
            ).utc.julian_day_exact()
            if context is not None and context.birth_instant_utc is not None
            else None
        )
        previous_end = None
        previous_year = None
        for row in self.rows or []:
            if (
                full
                and exact
                and (
                    row.comparison_policy != self.comparison_policy
                    or row.year is None
                    or row.segments is None
                )
            ):
                raise ValueError("完整精确年序缺少年份、主点政策或分段。")
            else:
                pass
            start = row.start_point.known_day() if row.start_point is not None else None
            end = row.end_point.known_day() if row.end_point is not None else None
            if start is not None and previous_end is not None and start != previous_end:
                raise ValueError("配运年序数值区间不连续。")
            else:
                pass
            if row.year is not None and previous_year is not None:
                if row.year != previous_year + 1:
                    raise ValueError("配运年序年份不连续。")
                else:
                    pass
            else:
                pass
            if row.year is not None:
                for year, actual, beginning in (
                    (row.year, start, True),
                    (row.year + 1, end, False),
                ):
                    year_boundary = boundaries.get(year)
                    if full and exact and year_boundary is None:
                        raise ValueError("配运年序没有绑定实际年度立春。")
                    else:
                        pass
                    point = (
                        year_boundary.record.civil_point
                        if year_boundary is not None
                        and year_boundary.record is not None
                        else None
                    )
                    expected = point.known_day() if point is not None else None
                    if expected is not None and beginning and birth is not None:
                        expected = max(expected, birth)
                    else:
                        pass
                    if (
                        expected is not None
                        and actual is not None
                        and expected != actual
                    ):
                        raise ValueError("配运年界或出生裁剪与实际主点不一致。")
                    else:
                        pass
            else:
                pass
            previous_end, previous_year = end, row.year
        if context is not None:
            if self.year_boundaries is not None and context.boundary_count is not None:
                if len(self.year_boundaries) != context.boundary_count:
                    raise ValueError("实际立春回执数与年序上下文不一致。")
                else:
                    pass
            else:
                pass
            if self.rows is not None and context.horizon_years is not None:
                if len(self.rows) != context.horizon_years:
                    raise ValueError("实际年序行数与声明的范围不一致。")
                else:
                    pass
            else:
                pass
            if (
                self.birth_pillar_year is not None
                and context.origin_bazi_year is not None
            ):
                if self.birth_pillar_year != context.origin_bazi_year:
                    raise ValueError("年序起年与实际出生干支年不一致。")
                else:
                    pass
            else:
                pass
        else:
            pass
        if (
            self.rows
            and self.rows[0].year is not None
            and self.birth_pillar_year is not None
        ):
            if self.rows[0].year != self.birth_pillar_year:
                raise ValueError("年序首行不是实际出生干支年。")
            else:
                pass
        else:
            pass
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
    source_pdf_sha256: str | None = None
    source_pdf_pages: list[int] | None = None
    source_status: str | None = None
    calendar_scope: str | None = None
    heluo_period_distinction: str | None = None
    selected: CanpingRow | None = None
    schedule_basis: CanpingScheduleBasis | None = None
    first_row: CanpingRow | None = None
    first_period: CanpingRow | None = None

    @model_validator(mode="after")
    def coherent_schedule_source_map(self, info: ValidationInfo) -> "CanpingTiming":
        basis = self.schedule_basis
        known_profile = self.profile_id or (basis.profile_id if basis else None)
        known_start = self.start_at or (basis.actual_start_at if basis else None)
        full = bool(info.context and info.context.get("full_result"))
        mapped = known_profile in {"bazi_appendix_v1", "bazi_continuous_v1"} and (
            known_start is not None
            or basis is not None
            and basis.has_actual_date_mapping is True
        )
        if full and mapped and self.comparison_policy is None:
            raise ValueError("实际日期配运缺少主点比较政策。")
        else:
            pass
        if known_profile == "legacy_minggong_v1" and self.comparison_policy is not None:
            raise ValueError("无实际日期的旧命宫方法不能声明精确民用区间。")
        else:
            pass
        if full and self.comparison_policy == "retained_nominal_civil_point_v1":
            if any(
                value is None
                for value in (
                    self.first_row,
                    self.first_period,
                    self.solar_year_context,
                    self.birth_at,
                    self.timezone,
                )
            ):
                raise ValueError("完整日期配运缺少实际首运或出生年序上下文。")
            else:
                pass
            for row in (self.first_row, self.first_period, self.selected):
                if row is not None and row.comparison_policy != self.comparison_policy:
                    raise ValueError("日期配运摘要缺少同一主点比较政策。")
                else:
                    pass
            if self.selected is not None and self.selected.at is None:
                raise ValueError("完整查询摘要缺少实际查询时刻。")
            else:
                pass
        else:
            pass
        if self.first_row is not None:
            if known_profile == "legacy_minggong_v1" or (
                basis is not None and basis.has_actual_date_mapping is False
            ):
                for key in (
                    "start_at",
                    "end_at",
                    "start_point",
                    "end_point",
                    "comparison_policy",
                    "start_age",
                    "end_age",
                    "at",
                    "dayun_index",
                    "year_start_boundary",
                    "year_end_boundary",
                ):
                    if getattr(self.first_row, key) is not None:
                        raise ValueError(
                            "旧法首行仅为年龄标签，不能补实际日期或查询身份。"
                        )
                    else:
                        pass
            else:
                pass
            if self.first_period is not None:

                def agree(a: Any, b: Any) -> bool:
                    if a is None or b is None:
                        return True
                    else:
                        pass
                    if isinstance(a, dict) and isinstance(b, dict):
                        return all(agree(a[k], b[k]) for k in a.keys() & b.keys())
                    else:
                        pass
                    if isinstance(a, list) and isinstance(b, list):
                        return len(a) == len(b) and all(
                            agree(x, y) for x, y in zip(a, b)
                        )
                    else:
                        pass
                    return bool(a == b)

                if not agree(
                    self.first_row.model_dump(exclude_unset=True),
                    self.first_period.model_dump(exclude_unset=True),
                ):
                    raise ValueError("首行与首运的已返回事实不一致。")
                else:
                    pass
            else:
                pass
        else:
            pass
        if basis is not None:
            if (
                self.start_at is not None
                and basis.actual_start_at is not None
                and self.start_at != basis.actual_start_at
            ):
                raise ValueError("配运来源回执与实际起运瞬间不一致。")
            else:
                pass
            if (
                self.profile_id is not None
                and basis.profile_id is not None
                and self.profile_id != basis.profile_id
            ):
                raise ValueError("配运来源回执与实际方法不一致。")
            else:
                pass
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
                    else:
                        pass
            else:
                pass
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
                    else:
                        pass
            else:
                pass
        else:
            pass
        if (
            self.first_period is not None
            and self.first_period.start_at is not None
            and known_start is not None
            and self.first_period.start_at != known_start
        ):
            raise ValueError("首运摘要与实际起运时刻不一致。")
        else:
            pass
        if self.first_period is not None and (
            known_profile == "legacy_minggong_v1"
            or basis is not None
            and basis.has_actual_date_mapping is False
        ):
            raise ValueError("旧命宫排法不能补成已核日期首运。")
        else:
            pass
        return self
