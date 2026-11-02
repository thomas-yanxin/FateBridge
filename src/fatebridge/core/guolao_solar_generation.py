"""Exact source-derived solar differences, separate from literal motion tables.

Gujin40's printed seed columns and Gujin36's cubic coefficients specify the
same finite-difference polynomial. Reconstructing the update order is explicit;
it does not silently emend later printed cells or establish astronomical truth.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_daily_solar import PROFILE as LITERAL_PROFILE
from fatebridge.core.guolao_daily_solar import (
    MotionSegment,
    SourceDailySolar,
    load_daily_solar,
)

DATA = Path(__file__).resolve().parents[1] / "data/guolao/solar-generation-v1.json"
GENERATOR_PROFILE = "gujin40_exact_recurrence_v1"
DAILY_PROFILE = "gujin40_exact_recurrence_on_g43_span_anchors"


def _integer(value: int) -> None:
    if type(value) is not int:
        raise TypeError("仅接收明确原历整数日序，不接收布尔、浮点或现代JD")


def _decimal(value: str) -> F:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value) is None
    ):
        raise ValueError("源值须为保留精度的十进制字符串，不自动补字、补零或改单位")
    return F(value)


@dataclass(frozen=True)
class GeneratedRow:
    index: int
    combined_difference_fen: F | None
    correction_increment_fen: F | None
    cumulative_correction_fen: F
    motion_du: F | None


@dataclass(frozen=True)
class GenerationBranch:
    name: str
    coefficients: tuple[F, F, F]
    initial_increment: F
    initial_difference: F
    terminal_index: int
    motion_sign: int

    @property
    def difference_step(self) -> F:
        return 6 * self.coefficients[2] / 10000

    def rows(self) -> tuple[GeneratedRow, ...]:
        difference, increment, cumulative = (
            self.initial_difference,
            self.initial_increment,
            F(),
        )
        result = []
        for index in range(self.terminal_index):
            result.append(
                GeneratedRow(
                    index,
                    difference,
                    increment,
                    cumulative,
                    1 + self.motion_sign * increment / 10000,
                )
            )
            cumulative += increment
            increment -= difference
            difference += self.difference_step
        # The endpoint has a generated cumulative value. Its following motion
        # is outside this selected source table, even though a cubic extends.
        result.append(GeneratedRow(self.terminal_index, None, None, cumulative, None))
        return tuple(result)

    def polynomial_correction(self, index: int) -> F:
        _integer(index)
        if not 0 <= index <= self.terminal_index:
            raise ValueError("超出所选立成日序，不延长初末限或按年取模")
        a, b, c = self.coefficients
        return F(index) * (a - index * (b + c * index)) / 100000000


@dataclass(frozen=True)
class SolarGenerator:
    profile_id: str
    data_sha256: str
    source_url: str
    branches: tuple[GenerationBranch, GenerationBranch]
    literal_checkpoints_json: str

    def branch(self, origin: str) -> GenerationBranch:
        for branch in self.branches:
            if branch.name == origin:
                return branch
        raise ValueError("须明确winter或summer原表，不根据月份猜测")

    def row(self, origin: str, index: int) -> dict[str, Any]:
        _integer(index)
        branch = self.branch(origin)
        if not 0 <= index <= branch.terminal_index:
            raise ValueError("越过原表末行，不补下一日行度")
        row = branch.rows()[index]
        return {
            "model_id": "gujin40_exact_solar_generation_v1",
            "profile_id": self.profile_id,
            "source_url": self.source_url,
            "data_sha256": self.data_sha256,
            "origin": origin,
            "index": index,
            "generated_combined_difference_fen_exact": (
                str(row.combined_difference_fen)
                if row.combined_difference_fen is not None
                else None
            ),
            "generated_correction_increment_fen_exact": (
                str(row.correction_increment_fen)
                if row.correction_increment_fen is not None
                else None
            ),
            "generated_cumulative_correction_fen_exact": str(
                row.cumulative_correction_fen
            ),
            "generated_cumulative_correction_ancient_du_exact": str(
                row.cumulative_correction_fen / 10000
            ),
            "generated_motion_ancient_du_exact": (
                str(row.motion_du) if row.motion_du is not None else None
            ),
            "column_fen_per_ancient_du": "10000",
            "difference_step_fen_exact": str(branch.difference_step),
            "reconstructed_update_order": "cumulative += increment; increment -= difference; difference += step",
            "rounding_applied": False,
            "literal_printed_cells_emended": False,
            "origin_cumulative_is_empty_sum_not_a_transcribed_zero": index == 0,
            "next_day_motion_outside_selected_table": index == branch.terminal_index,
            "source_full_Gujin40_table_collated": False,
            "physical_solar_position_validated": False,
            "used_in_native_birth_chart": False,
        }


@dataclass(frozen=True)
class GeneratedDailySolar:
    generator: SolarGenerator
    literal: SourceDailySolar
    trajectory: SourceDailySolar

    def _metadata(self) -> dict[str, Any]:
        return {
            "model_id": "gujin40_generated_solar_on_g43_span_anchors_v1",
            "profile_id": DAILY_PROFILE,
            "generator_profile_id": self.generator.profile_id,
            "generator_parameter_data_sha256": self.generator.data_sha256,
            "anchor_source_profile_id": self.literal.profile_id,
            "anchor_source_data_sha256": self.literal.data_sha256,
            "motion_basis": "exact_Gujin40_seed_recurrence_checked_against_Gujin36_cubic",
            "motion_values_from_literal_Gujin41_42_cells": False,
            "retained_Gujin43_span_section_midnight_anchors": True,
            "cardinal_anchors_recomputed_from_generated_rates": False,
            "recurrence_update_order_is_reconstruction": True,
            "literal_source_cells_repaired_or_rebaselined": False,
            "generated_model_automatically_selected_as_best": False,
            "physical_solar_position_validated": False,
            "used_in_native_birth_chart": False,
        }

    def day(self, index: int, *, policy: str) -> dict[str, Any]:
        return {**self.trajectory.day(index, policy=policy), **self._metadata()}

    def audit(self) -> dict[str, Any]:
        result = self.trajectory.audit()
        # Those fields describe the separate literal corpus, not generator input.
        result.pop("source_motion_numeric_cells")
        result.pop("source_motion_printed_empty_cells")
        # The shared arithmetic works with either rate source; its literal-only
        # labels must not describe the reconstructed rates as printed evidence.
        for segment in result["segments"]:
            for old, new in (
                ("printed_rates_used", "generated_rates_used"),
                ("literal_rate_sum_du_exact", "generated_rate_sum_du_exact"),
                (
                    "rate_sum_minus_printed_worked_cumulative_du_exact",
                    "generated_rate_sum_minus_printed_worked_cumulative_du_exact",
                ),
            ):
                segment[new] = segment.pop(old)
        return {
            **result,
            **self._metadata(),
            "source_seed_and_checkpoint_rows_collated": 29,
            "source_seed_and_checkpoint_numeric_cells": 81,
            "source_seed_and_checkpoint_printed_empty_cells": 6,
            "full_Gujin40_numeric_transcription_claimed": False,
        }


def load_generator(profile: str) -> SolarGenerator:
    if profile != GENERATOR_PROFILE:
        raise ValueError(
            "须明确选择gujin40_exact_recurrence_v1，不自动换成刊率或最佳拟合"
        )
    blob = DATA.read_bytes()
    raw = json.loads(blob)
    if (
        raw.get("schema") != "gujin40_exact_solar_generation_v1"
        or raw.get("profile_id") != profile
    ):
        raise ValueError("未核对的太阳立成生成版本")
    if (
        raw.get("column_fen_per_ancient_du") != "10000"
        or raw.get("coefficient_polynomial_du_divisor") != "100000000"
    ):
        raise ValueError("此处立成分不是百分之一古度的角分，不能自动换尺度")
    branches: list[GenerationBranch] = []
    for name, terminal, sign in [("winter", 89, 1), ("summer", 94, -1)]:
        source = raw["branches"][name]
        coeff = tuple(_decimal(v) for v in source["volume36_polynomial_coefficients"])
        if len(coeff) != 3:
            raise ValueError("须保留定差、平差、立差三个源系数")
        a, b, c = coeff
        increment = _decimal(source["volume40_initial_correction_increment_fen"])
        difference = _decimal(source["volume40_initial_combined_difference_fen"])
        if increment != (a - b - c) / 10000 or difference != (2 * b + 6 * c) / 10000:
            raise ValueError("原页首行种子与所声明三次式不符，不能改种子或静默选一方")
        if (
            type(source["terminal_cumulative_index"]) is not int
            or source["terminal_cumulative_index"] != terminal
            or type(source["motion_sign"]) is not int
            or source["motion_sign"] != sign
        ):
            raise ValueError("原表末行或盈缩方向不符，不扩域或猜正负")
        branches.append(
            GenerationBranch(name, (a, b, c), increment, difference, terminal, sign)
        )
    return SolarGenerator(
        profile,
        hashlib.sha256(blob).hexdigest(),
        raw["source_url"],
        (branches[0], branches[1]),
        json.dumps(raw["literal_checkpoints"], ensure_ascii=False),
    )


def load_generated_daily_solar(profile: str) -> GeneratedDailySolar:
    if profile != DAILY_PROFILE:
        raise ValueError(
            "须明确选择gujin40_exact_recurrence_on_g43_span_anchors，不改动既有刊率版本"
        )
    generator = load_generator(GENERATOR_PROFILE)
    literal = load_daily_solar(LITERAL_PROFILE)

    def motions(origin: str) -> tuple[F, ...]:
        values = []
        for row in generator.branch(origin).rows()[:-1]:
            if row.motion_du is None:
                raise ValueError("段内生成率缺失，不丢行补齐计算")
            values.append(row.motion_du)
        return tuple(values)

    winter = motions("winter")
    summer = motions("summer")
    # Separate named construction, not in-place repairs of either literal column.
    rates = (winter, tuple(reversed(summer)), summer, tuple(reversed(winter)))
    segments = tuple(
        MotionSegment(
            s.name, s.days, values, s.printed_cumulative, s.printed_difference
        )
        for s, values in zip(literal.segments, rates, strict=True)
    )
    trajectory = SourceDailySolar(
        DAILY_PROFILE,
        generator.data_sha256,
        generator.source_url,
        literal.circle,
        literal.offsets,
        literal.anchors,
        segments,
    )
    return GeneratedDailySolar(generator, literal, trajectory)
