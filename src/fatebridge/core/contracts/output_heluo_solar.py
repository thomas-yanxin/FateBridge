"""Projection-compatible contracts for the actual Heluo solar dependencies."""

from typing import Annotated, Literal

from pydantic import model_validator

from fatebridge.core.contracts.output_base import FULL_FACT, PartialOutput
from fatebridge.core.contracts.output_civil_time import (
    CivilPointEvidence,
    CivilPointLabelEvidence,
)
from fatebridge.utils.civil_time import UTCCalendar, ZonedCalendar
from fatebridge.utils.timezones import parse_timezone_name


class HeluoSolarTermRecord(CivilPointLabelEvidence):
    """The source facts consumed here; other receipt fields remain intact."""

    name: str | None = None


class HeluoSolarBoundary(PartialOutput):
    role: Literal["current_term", "preceding_solstice", "next_four_li"] | None = None
    record: HeluoSolarTermRecord | None = None
    instant_utc: str | None = None
    ephemeris_retflags: list[int] | None = None
    ephemeris_library_version: str | None = None

    @model_validator(mode="after")
    def same_instant(self) -> "HeluoSolarBoundary":
        if self.instant_utc is not None:
            at = ZonedCalendar.from_isoformat(self.instant_utc).utc
            civil = self.record.display_with_offset if self.record is not None else None
            if civil is not None and ZonedCalendar.from_isoformat(civil).utc != at:
                raise ValueError("实际交节记录与所列UTC瞬间不是同一时刻。")
        return self


class HeluoSolarContext(PartialOutput):
    policy_id: str | None = None
    comparison_policy: Literal["retained_nominal_civil_point_v1"] | None = None
    context_local_year: int | None = None
    context_timezone: str | None = None
    birth_instant_utc: str | None = None
    dependencies: list[HeluoSolarBoundary] | None = None
    environment_unchanged_at_observation_points: Literal[True] | None = None
    calendar_context_match: Literal[True] | None = None
    scope: str | None = None

    @model_validator(mode="after")
    def local_year_matches_instant(self) -> "HeluoSolarContext":
        if self.birth_instant_utc is not None:
            at = ZonedCalendar.from_isoformat(self.birth_instant_utc)
            if (
                self.context_timezone is not None
                and self.context_local_year is not None
            ):
                if (
                    ZonedCalendar(
                        at.utc, parse_timezone_name(self.context_timezone)
                    ).local_parts[0]
                    != self.context_local_year
                ):
                    raise ValueError(
                        "上下文年份须取已给时区的民用年，不能替换成UTC年。"
                    )
        return self


class HeluoSolarTermEvidence(PartialOutput):
    hg: list[str] | None = None
    fh: list[str] | None = None
    quarter: str | None = None
    tuyong: bool | None = None
    fanhua_rule_ids: list[str] | None = None
    term: str | None = None
    yang_ling: bool | None = None
    anchor_utc: str | None = None
    precision: Literal["birth_instant", "date_midnight_approximation"] | None = None
    tuyong_policy: str | None = None
    tuyong_start_utc: str | None = None
    tuyong_end_utc: str | None = None
    comparison_policy: Annotated[
        Literal["retained_nominal_civil_point_v1"] | None, FULL_FACT
    ] = None
    tuyong_start_point: Annotated[CivilPointEvidence | None, FULL_FACT] = None
    tuyong_end_point: Annotated[CivilPointEvidence | None, FULL_FACT] = None
    boundary_context: HeluoSolarContext | None = None

    @model_validator(mode="after")
    def known_boundary_facts(self) -> "HeluoSolarTermEvidence":
        context = self.boundary_context
        if context is None:
            return self
        if self.anchor_utc is not None and context.birth_instant_utc is not None:
            if ZonedCalendar.from_isoformat(self.anchor_utc).utc != (
                ZonedCalendar.from_isoformat(context.birth_instant_utc).utc
            ):
                raise ValueError("节气上下文与出生锚点不一致。")
        roles = {r.role: r for r in context.dependencies or [] if r.role is not None}
        if (row := roles.get("current_term")) is not None and row.record is not None:
            if (
                self.term is not None
                and row.record.name is not None
                and row.record.name != self.term
            ):
                raise ValueError("实际交节记录与所列节气不一致。")
        if (
            row := roles.get("preceding_solstice")
        ) is not None and row.record is not None:
            if self.yang_ling is not None and row.record.name in {"冬至", "夏至"}:
                if self.yang_ling != (row.record.name == "冬至"):
                    raise ValueError("阴阳令须与实际最近至点一致。")
        if self.anchor_utc is not None:
            anchor = ZonedCalendar.from_isoformat(
                self.anchor_utc
            ).utc.julian_day_exact()
            for role, row in roles.items():
                point = row.record.civil_point if row.record is not None else None
                day = point.known_day() if point is not None else None
                if day is not None:
                    if (role == "next_four_li" and day <= anchor) or (
                        role != "next_four_li" and day > anchor
                    ):
                        raise ValueError("交节包含端点与下一四立的时序不一致。")
        start = (
            self.tuyong_start_point.known_day()
            if self.tuyong_start_point is not None
            else None
        )
        end = (
            self.tuyong_end_point.known_day()
            if self.tuyong_end_point is not None
            else None
        )
        if start is not None and end is not None:
            if start != end - 18:
                raise ValueError("土用精确起点须为下一四立主点前十八个名义日。")
            if self.tuyong is not None and self.anchor_utc is not None:
                anchor = ZonedCalendar.from_isoformat(
                    self.anchor_utc
                ).utc.julian_day_exact()
                if self.tuyong != (start <= anchor < end):
                    raise ValueError("土用匹配与所列精确民用边界不一致。")
        if (row := roles.get("next_four_li")) is not None:
            point = row.record.civil_point if row.record is not None else None
            source_end = point.known_day() if point is not None else None
            if source_end is not None and end is not None and source_end != end:
                raise ValueError("土用终点与下一四立精确主点不一致。")
            if row.instant_utc is not None:
                end_label = ZonedCalendar.from_isoformat(row.instant_utc).utc
                start_label = UTCCalendar(
                    end_label.ordinal - 18, end_label.microseconds_of_day
                )
                if (
                    self.tuyong_start_utc is not None
                    and ZonedCalendar.from_isoformat(self.tuyong_start_utc).utc
                    != start_label
                ):
                    raise ValueError("土用显示起点须为四立显示标签前十八个名义日。")
                if (
                    self.tuyong_end_utc is not None
                    and ZonedCalendar.from_isoformat(self.tuyong_end_utc).utc
                    != end_label
                ):
                    raise ValueError("土用显示终点须为本次下一四立显示标签。")
        return self
