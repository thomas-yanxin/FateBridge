"""Canping interval rows and text witnesses."""

from pydantic import ValidationInfo, model_validator

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.contracts.output_canping_reading import (
    CanpingPairResolution,
    CanpingTextSelection,
)
from fatebridge.core.contracts.output_canping_solar import (
    CanpingInterval,
    CanpingSolarBoundary,
)
from fatebridge.utils.civil_time import ZonedCalendar


class CanpingVerses(PartialOutput):
    statusShun: str | None = None
    statusNi: str | None = None
    numNi: int | None = None
    numShun: int | None = None
    textNi: str | None = None
    textShun: str | None = None
    selectionShun: CanpingTextSelection | None = None
    selectionNi: CanpingTextSelection | None = None
    pair_resolution: CanpingPairResolution | None = None


class CanpingRow(CanpingInterval):
    year_start_boundary: CanpingSolarBoundary | None = None
    year_end_boundary: CanpingSolarBoundary | None = None
    age: int | None = None
    ageEnd: int | None = None
    ageStart: int | None = None
    branch: str | None = None
    index: int | None = None
    ni: int | None = None
    numNi: int | None = None
    numShun: int | None = None
    shun: int | None = None
    ziRound: int | None = None
    verses: CanpingVerses | None = None
    dayunBranch: str | None = None
    dayunRange: str | None = None
    ganzhi: str | None = None
    taisuiBranch: str | None = None
    year: int | None = None
    at: str | None = None
    start_age: float | None = None
    end_age: float | None = None
    status: str | None = None
    pillar: str | None = None
    dayun_index: int | None = None
    dayun_pillar: str | None = None
    segments: list["CanpingRow"] | None = None

    @model_validator(mode="after")
    def coherent_dated_row(self, info: ValidationInfo) -> "CanpingRow":
        full = bool(info.context and info.context.get("full_result"))
        exact = self.comparison_policy == "retained_nominal_civil_point_v1"
        if (
            full
            and (self.start_at is not None or self.end_at is not None)
            and not exact
        ):
            raise ValueError("实际日期配运行缺少主点比较政策。")
        if (
            full
            and exact
            and self.at is not None
            and any(
                value is None
                for value in (
                    self.year,
                    self.ganzhi,
                    self.status,
                    self.year_start_boundary,
                    self.year_end_boundary,
                )
            )
        ):
            raise ValueError("精确查询缺少实际年份或立春边界。")
        if self.status == "not_started" and any(
            value is not None
            for value in (
                self.dayun_index,
                self.dayunBranch,
                self.dayun_pillar,
                self.numNi,
                self.numShun,
                self.verses,
            )
        ):
            raise ValueError("未起运区间不能附活动大运或条文。")
        start = self.start_point.known_day() if self.start_point is not None else None
        end = self.end_point.known_day() if self.end_point is not None else None
        at = (
            ZonedCalendar.from_isoformat(self.at).utc.julian_day_exact()
            if self.at is not None
            else None
        )
        if at is not None and (
            (start is not None and at < start) or (end is not None and at >= end)
        ):
            raise ValueError("查询时刻不在所选数值半开区间。")
        for boundary, ending in (
            (self.year_start_boundary, False),
            (self.year_end_boundary, True),
        ):
            if boundary is None:
                continue
            if (
                full
                and exact
                and self.at is not None
                and (
                    boundary.year is None
                    or boundary.record is None
                    or boundary.record.comparison_policy != self.comparison_policy
                    or boundary.record.civil_point is None
                )
            ):
                raise ValueError("精确查询缺少实际立春主点。")
            if self.year is not None and boundary.year is not None:
                if boundary.year != self.year + int(ending):
                    raise ValueError("所选年与实际立春边界年份不一致。")
            point = boundary.record.civil_point if boundary.record is not None else None
            day = point.known_day() if point is not None else None
            if day is not None and at is not None:
                if (ending and at >= day) or (not ending and at < day):
                    raise ValueError("查询时刻不在所选立春年内。")
        if self.segments is not None:
            previous_end = start
            for segment in self.segments:
                if (
                    full
                    and self.comparison_policy == "retained_nominal_civil_point_v1"
                    and segment.comparison_policy != self.comparison_policy
                ):
                    raise ValueError("精确年序的分段缺少同一比较政策。")
                if (
                    full
                    and exact
                    and (
                        segment.status not in {"active", "not_started"}
                        or segment.status == "active"
                        and any(
                            value is None
                            for value in (
                                segment.dayun_index,
                                segment.dayunBranch,
                                segment.dayun_pillar,
                                segment.numNi,
                                segment.numShun,
                                segment.verses,
                            )
                        )
                    )
                ):
                    raise ValueError("精确年序分段缺少活动状态或实际配运事实。")
                lower = (
                    segment.start_point.known_day()
                    if segment.start_point is not None
                    else None
                )
                upper = (
                    segment.end_point.known_day()
                    if segment.end_point is not None
                    else None
                )
                if (
                    lower is not None
                    and previous_end is not None
                    and lower != previous_end
                ):
                    raise ValueError("配运年内分段没有连续覆盖父区间。")
                if (lower is not None and start is not None and lower < start) or (
                    upper is not None and end is not None and upper > end
                ):
                    raise ValueError("配运分段超出父年区间。")
                if (
                    self.year is not None
                    and segment.year is not None
                    and segment.year != self.year
                ):
                    raise ValueError("配运分段的年份与父年不一致。")
                previous_end = upper
            if (
                self.segments
                and previous_end is not None
                and end is not None
                and previous_end != end
            ):
                raise ValueError("配运分段末端没有到达父年终点。")
            if full and self.comparison_policy is not None and not self.segments:
                raise ValueError("精确年序不能缺少分段。")
            expected_status = None
            if self.segments:
                expected_status = (
                    "split" if len(self.segments) > 1 else self.segments[0].status
                )
            if self.status is not None and expected_status is not None:
                if self.status != expected_status:
                    raise ValueError("配运年状态与实际分段不一致。")
        return self
