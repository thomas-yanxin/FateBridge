"""Projection-compatible contracts for the actual Heluo solar dependencies."""

from datetime import timedelta
from typing import Dict, List, Literal, Optional

from pydantic import JsonValue, model_validator

from fatebridge.core.output_base import PartialOutput
from fatebridge.utils.civil_clock import parse_iso_datetime
from fatebridge.utils.timezones import parse_timezone_name


class HeluoSolarBoundary(PartialOutput):
    role: Optional[Literal["current_term", "preceding_solstice", "next_four_li"]] = None
    record: Optional[Dict[str, JsonValue]] = None
    instant_utc: Optional[str] = None
    ephemeris_retflags: Optional[List[int]] = None
    ephemeris_library_version: Optional[str] = None

    @model_validator(mode="after")
    def same_instant(self) -> "HeluoSolarBoundary":
        if self.instant_utc is not None:
            at = parse_iso_datetime(self.instant_utc)
            if at.utcoffset() is None:
                raise ValueError("节气边界须为绝对时刻。")
            civil = (self.record or {}).get("datetime_with_offset")
            if isinstance(civil, str) and at != parse_iso_datetime(civil):
                raise ValueError("所列民用节气与UTC边界不是同一时刻。")
        return self


class HeluoSolarContext(PartialOutput):
    policy_id: Optional[str] = None
    context_local_year: Optional[int] = None
    context_timezone: Optional[str] = None
    birth_instant_utc: Optional[str] = None
    dependencies: Optional[List[HeluoSolarBoundary]] = None
    environment_unchanged_at_observation_points: Optional[Literal[True]] = None
    calendar_context_match: Optional[Literal[True]] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def local_year_matches_instant(self) -> "HeluoSolarContext":
        if self.birth_instant_utc is not None:
            at = parse_iso_datetime(self.birth_instant_utc)
            if at.utcoffset() is None:
                raise ValueError("出生节气锚点须为绝对时刻。")
            if (
                self.context_timezone is not None
                and self.context_local_year is not None
            ):
                if (
                    at.astimezone(parse_timezone_name(self.context_timezone)).year
                    != self.context_local_year
                ):
                    raise ValueError(
                        "上下文年份须取已给时区的民用年，不能替换成UTC年。"
                    )
        return self


class HeluoSolarTermEvidence(PartialOutput):
    hg: Optional[List[str]] = None
    fh: Optional[List[str]] = None
    quarter: Optional[str] = None
    tuyong: Optional[bool] = None
    fanhua_rule_ids: Optional[List[str]] = None
    term: Optional[str] = None
    yang_ling: Optional[bool] = None
    anchor_utc: Optional[str] = None
    precision: Optional[Literal["birth_instant", "date_midnight_approximation"]] = None
    tuyong_policy: Optional[str] = None
    tuyong_start_utc: Optional[str] = None
    tuyong_end_utc: Optional[str] = None
    boundary_context: Optional[HeluoSolarContext] = None

    @model_validator(mode="after")
    def known_boundary_facts(self) -> "HeluoSolarTermEvidence":
        context = self.boundary_context
        if context is None:
            return self
        if self.anchor_utc is not None and context.birth_instant_utc is not None:
            if parse_iso_datetime(self.anchor_utc) != parse_iso_datetime(
                context.birth_instant_utc
            ):
                raise ValueError("节气上下文与出生锚点不一致。")
        roles = {r.role: r for r in context.dependencies or [] if r.role is not None}
        if (row := roles.get("current_term")) is not None and row.record is not None:
            if self.term is not None and row.record.get("name") != self.term:
                raise ValueError("实际交节记录与所列节气不一致。")
        if (
            row := roles.get("preceding_solstice")
        ) is not None and row.record is not None:
            if self.yang_ling is not None and row.record.get("name") in {
                "冬至",
                "夏至",
            }:
                if self.yang_ling != (row.record["name"] == "冬至"):
                    raise ValueError("阴阳令须与实际最近至点一致。")
        if self.anchor_utc is not None:
            anchor = parse_iso_datetime(self.anchor_utc)
            for role, row in roles.items():
                if row.instant_utc is not None:
                    at = parse_iso_datetime(row.instant_utc)
                    if (role == "next_four_li" and at <= anchor) or (
                        role != "next_four_li" and at > anchor
                    ):
                        raise ValueError("交节包含端点与下一四立的时序不一致。")
        if (
            row := roles.get("next_four_li")
        ) is not None and row.instant_utc is not None:
            end = parse_iso_datetime(row.instant_utc)
            start = end - timedelta(days=18)
            if (
                self.tuyong_start_utc is not None
                and parse_iso_datetime(self.tuyong_start_utc) != start
            ):
                raise ValueError("土用起点须为本次四立前十八连续日。")
            if (
                self.tuyong_end_utc is not None
                and parse_iso_datetime(self.tuyong_end_utc) != end
            ):
                raise ValueError("土用终点须为本次下一四立。")
            if self.tuyong is not None and self.anchor_utc is not None:
                if self.tuyong != (start <= parse_iso_datetime(self.anchor_utc) < end):
                    raise ValueError("土用匹配与所列绝对边界不一致。")
        return self
