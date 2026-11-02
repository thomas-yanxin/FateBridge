"""Named Gujin43 year318 daily solar reconstruction from literal motion columns.

The two explicit policies replay different source operations. One uses Gujin36's
rate-sum bridge; the other keeps Gujin43's printed daily differences, including
their nonclosure. Neither repairs table glyphs, infers a modern epoch, or supplies
an accepted folded argument to the sunrise component.
"""

from __future__ import annotations

import hashlib
import json
import re
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / "data/guolao/daily-solar-motion-v1.json"
PROFILE = "gujin43_siku318_literal_motion"
NAMES = ("winter", "spring", "summer", "autumn")
POLICIES = ("gujin36_rate_sum_bridge", "gujin43_printed_daily_differences")


def _integer(value: int, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name}须为明确原历整数日，不接收布尔、浮点或现代日期")


def _policy(value: str) -> None:
    if value not in POLICIES:
        raise ValueError("须显式选择卷36累计率日差或卷43刊载日差，不自动选择较吻合者")


def _segment_index(value: int) -> None:
    _integer(value, "四正段序")
    if not 0 <= value < 4:
        raise ValueError("四正段序须为0至3，不用Python负下标代替原历段序")


def _number(value: str) -> F:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value) is None
    ):
        raise ValueError("原刊操作数须为明确精度的十进制字符串，不接收浮点或布尔")
    return F(value)


@dataclass(frozen=True)
class MotionSegment:
    name: str
    days: int
    rates: tuple[F, ...]
    printed_cumulative: F
    printed_difference: F

    def cumulative(self, offset: int) -> F:
        _integer(offset, "段内距日")
        if not 0 <= offset <= self.days:
            raise ValueError("段内距日越界，不取模或跨段套率")
        return sum(self.rates[:offset], F())


@dataclass(frozen=True)
class SourceDailySolar:
    profile_id: str
    data_sha256: str
    source_url: str
    circle: F
    offsets: tuple[int, ...]
    anchors: tuple[F, ...]
    segments: tuple[MotionSegment, ...]

    def difference(self, segment: int, *, policy: str) -> F:
        _segment_index(segment)
        _policy(policy)
        s = self.segments[segment]
        if policy == "gujin43_printed_daily_differences":
            return s.printed_difference
        return (
            self.anchors[segment + 1] - self.anchors[segment] - s.cumulative(s.days)
        ) / s.days

    def point(self, segment: int, offset: int, *, policy: str) -> F:
        _segment_index(segment)
        s = self.segments[segment]
        return (
            self.anchors[segment]
            + s.cumulative(offset)
            + offset * self.difference(segment, policy=policy)
        )

    def day(self, day_index: int, *, policy: str) -> dict[str, Any]:
        """Source midnight day0..365; each cardinal anchor has explicit left limit."""
        _integer(day_index, "距岁前冬至晨前夜半日数")
        _policy(policy)
        if not 0 <= day_index <= 365:
            raise ValueError("仅复原具名318算例的0至365日，不外推年份或认作公历日")
        segment = bisect_right(self.offsets, day_index) - 1
        terminal = segment == 4
        offset = day_index - self.offsets[segment]
        midnight = (
            self.anchors[-1] if terminal else self.point(segment, offset, policy=policy)
        )
        rate = None
        if not terminal:
            rate = self.segments[segment].rates[offset] + self.difference(
                segment, policy=policy
            )
        left = None
        if offset == 0 and segment:
            previous = self.segments[segment - 1]
            value = self.point(segment - 1, previous.days, policy=policy)
            left = {
                "previous_segment": previous.name,
                "calculated_left_limit_du_exact": str(value),
                "printed_right_anchor_du_exact": str(midnight),
                "left_minus_right_du_exact": str(value - midnight),
                "nonclosing_left_limit_preserved": True,
            }
        return {
            "model_id": "gujin43_daily_solar_literal_motion_v1",
            "profile_id": self.profile_id,
            "calculation_policy": policy,
            "source_url": self.source_url,
            "data_sha256": self.data_sha256,
            "elapsed_source_years": 318,
            "day_index_from_first_midnight": day_index,
            "unwrapped_source_day_integer": 42 + day_index,
            "segment": "next_winter" if terminal else self.segments[segment].name,
            "offset_in_segment": offset,
            "midnight_unwrapped_from_ji_start_du_exact": str(midnight),
            "midnight_modulo_source_circle_du_exact": str(midnight % self.circle),
            "source_circle_du_exact": str(self.circle),
            "following_corrected_daily_motion_du_exact": (
                str(rate) if rate is not None else None
            ),
            "noon_unwrapped_from_ji_start_du_exact": (
                str(midnight + rate / 2) if rate is not None else None
            ),
            "cardinal_boundary_left_limit": left,
            "coordinate_unit": "historical_du_not_modern_degrees",
            "time_unit": "source_day_not_UTC_TT_or_modern_JD",
            "unadjudicated_literal_motion_conflicts_present": True,
            "source_precision_or_editorial_error_adjudicated": False,
            "physical_solar_position_validated": False,
            "modern_calendar_date_assigned": False,
            "folded_sunrise_argument": None,
            "sunrise_or_phase_day_backfilled": False,
            "redated_mansion_or_life_degree_assigned": False,
            "used_in_native_birth_chart": False,
        }

    def audit(self) -> dict[str, Any]:
        records = []
        for i, s in enumerate(self.segments):
            span = self.anchors[i + 1] - self.anchors[i]
            records.append(
                {
                    "segment": s.name,
                    "distance_source_days": s.days,
                    "printed_rates_used": s.days,
                    "literal_rate_sum_du_exact": str(s.cumulative(s.days)),
                    "separately_printed_worked_cumulative_du_exact": str(
                        s.printed_cumulative
                    ),
                    "rate_sum_minus_printed_worked_cumulative_du_exact": str(
                        s.cumulative(s.days) - s.printed_cumulative
                    ),
                    "printed_midnight_span_du_exact": str(span),
                    "rate_sum_bridge_daily_difference_du_exact": str(
                        self.difference(i, policy=POLICIES[0])
                    ),
                    "separately_printed_daily_difference_du_exact": str(
                        s.printed_difference
                    ),
                    "printed_daily_difference_endpoint_residual_du_exact": str(
                        self.point(i, s.days, policy=POLICIES[1]) - self.anchors[i + 1]
                    ),
                    "rate_sum_bridge_endpoint_residual_du_exact": str(
                        self.point(i, s.days, policy=POLICIES[0]) - self.anchors[i + 1]
                    ),
                    "bridge_closure_is_source_formula_identity_not_independent_acceptance": True,
                }
            )
        return {
            "profile_id": self.profile_id,
            "data_sha256": self.data_sha256,
            "source_url": self.source_url,
            "segments": records,
            "all_days_in_named_example": 366,
            "daily_rates_in_named_example": 365,
            "source_motion_numeric_cells": 366,
            "source_motion_printed_empty_cells": 4,
            "full_cumulative_columns_transcribed": False,
            "source_internal_arithmetic_is_accuracy_score": False,
            "source_calendar_or_UTC_epoch_accepted": False,
            "used_in_native_birth_chart": False,
            "real_world_predictive_efficacy_tested": False,
        }


def load_daily_solar(profile: str) -> SourceDailySolar:
    if profile != PROFILE:
        raise ValueError(
            "须明确选择gujin43_siku318_literal_motion，不默认出生年或拼用大统"
        )
    blob = DATA.read_bytes()
    raw = json.loads(blob)
    if (
        raw.get("schema") != "gujin43_daily_solar_literal_motion_v1"
        or raw.get("profile_id") != profile
    ):
        raise ValueError("未核对的原历日太阳参数版本")
    if (
        raw.get("coordinate_unit") != "historical_du_not_modern_degrees"
        or raw.get("source_day_unit") != "source_day_not_UTC_TT_or_modern_JD"
    ):
        raise ValueError("原历日度单位不能自动转换为现代角度或时间尺度")
    offsets = tuple(raw["integer_day_offsets"])
    if offsets != (0, 88, 182, 276, 365) or any(type(n) is not int for n in offsets):
        raise ValueError("具名四正相距日不可重采或补成平均象限")
    if (
        raw.get("elapsed_source_years") != 318
        or raw.get("source_first_midnight_day") != "42"
    ):
        raise ValueError("具名距算及首日不能更换后沿用同一参数版本")
    anchors = tuple(_number(v) for v in raw["midnight_unwrapped_du"])
    if len(anchors) != 5 or any(b <= a for a, b in zip(anchors, anchors[1:])):
        raise ValueError("须保留五个递增的四正夜半操作数，不取模去周后相减")
    segments: list[MotionSegment] = []
    for name, count in zip(NAMES, (89, 94, 94, 89), strict=True):
        source = raw["segments"][name]
        rows = source["rows"]
        # Winter contains the extra89th motion supporting the printed table's
        # terminal89-day position; this year's first segment uses only88 rates.
        if len(rows) != count + 1 or any(
            type(q["index"]) is not int or q["index"] != i for i, q in enumerate(rows)
        ):
            raise ValueError("须保留所选完整行度列的位置和刊空，不补缺或排序")
        values = [q["rate_du"] for q in rows[:-1]]
        if rows[-1]["rate_du"] is not None or any(
            not isinstance(v, str) or re.fullmatch(r"[01]\.[0-9]{6}", v) is None
            for v in values
        ):
            raise ValueError("刊率须为六位精度字符串；末格刊空不得补零")
        days = source["distance_source_days"]
        if (
            type(days) is not int
            or days != offsets[len(segments) + 1] - offsets[len(segments)]
        ):
            raise ValueError("相距日与所选行度列长度不符")
        rates = tuple(F(v) for v in values)
        if any(not 0 < rate < 2 for rate in rates):
            raise ValueError("源行度超出本具名模型范围，不截断或以邻值填充")
        segments.append(
            MotionSegment(
                name,
                days,
                rates,
                _number(source["printed_worked_cumulative_du"]),
                _number(source["printed_daily_difference_du"]),
            )
        )
    return SourceDailySolar(
        profile,
        hashlib.sha256(blob).hexdigest(),
        raw["source_url"],
        _number(raw["circle_du"]),
        offsets,
        anchors,
        tuple(segments),
    )
