"""Separate source selectors for cardinal partial-day solar subtraction.

Gujin39's prose selector and Gujin43's named table indices disagree. Exact
products preserve both, while a third lane retains the old normalized printed
rates. None is selected by closure, numerical agreement or modern ephemerides.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_daily_solar import DATA as DAILY_DATA
from fatebridge.core.guolao_daily_solar import SourceDailySolar
from fatebridge.core.guolao_solar_generation import (
    DAILY_PROFILE,
    GeneratedDailySolar,
    load_generated_daily_solar,
)

DATA = Path(__file__).resolve().parents[1] / "data/guolao/midnight-anchors-v1.json"
PROFILE = "gujin318_midnight_recomputed_v1"
RATE_POLICIES = (
    "gujin43_printed_rate_products",
    "gujin39_literal_selector_products",
    "gujin43_indexed_generated_rate_products",
)
CARDINALS = ("winter", "spring", "summer", "autumn", "next_winter")


def _number(value: str) -> F:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError("源数须为十进制字符串，不强转浮点、不补字或选舍入")
    return F(value)


def _source() -> tuple[dict[str, Any], str]:
    blob = DATA.read_bytes()
    raw = json.loads(blob)
    if raw.get("schema") != PROFILE or raw.get("profile_id") != PROFILE:
        raise ValueError("未核对的四正夜半选率版本")
    return raw, hashlib.sha256(blob).hexdigest()


def gujin39_cardinal_rate(cardinal: str, *, distance_days: int | None) -> F:
    """Only the explicit source cases; no universal seasonal extrapolation."""
    raw, _ = _source()
    if cardinal not in CARDINALS:
        raise ValueError("须明确原文四正，不按月份或现代日期猜测")
    rates = raw["gujin39_literal_selector_rates"]
    if cardinal in ("spring", "autumn"):
        if type(distance_days) is not int:
            raise TypeError("相距日须为原历整数，不接收布尔、浮点或默认距离")
        if str(distance_days) not in rates[cardinal]:
            raise ValueError("超出卷39明确给出的相距日，不补一个最接近日率")
        return _number(rates[cardinal][str(distance_days)])
    if distance_days is not None:
        raise ValueError("冬夏初日率不使用相距日，不能混入春秋分支")
    return _number(rates[cardinal])


@dataclass(frozen=True)
class RecomputedMidnightSolar:
    generated: GeneratedDailySolar
    rate_policy: str
    policy_data_sha256: str
    anchor_records_json: str

    def _metadata(self) -> dict[str, Any]:
        return {
            "model_id": PROFILE,
            "profile_id": PROFILE,
            "anchor_rate_policy": self.rate_policy,
            "anchor_policy_data_sha256": self.policy_data_sha256,
            "retained_Gujin43_span_section_midnight_anchors": False,
            "cardinal_anchors_recomputed_from_products": True,
            "cardinal_anchors_recomputed_from_generated_rates": (
                self.rate_policy == RATE_POLICIES[2]
            ),
            "Gujin43_event_positions_and_fractions_retained": True,
            "daily_motion_basis": "exact_Gujin40_generation_with_reverse_spring_autumn",
            "Gujin39_and_Gujin43_selector_disagreement_adjudicated": False,
            "Gujin43_spring_rate_numeric_normalization_adjudicated": False,
            "anchor_source_cells_or_previous_profiles_emended": False,
            "anchor_products_are_printed_values": False,
            "source_calendar_or_UTC_epoch_accepted": False,
            "physical_solar_position_validated": False,
            "used_in_native_birth_chart": False,
        }

    def day(self, index: int, *, policy: str) -> dict[str, Any]:
        result = {**self.generated.day(index, policy=policy), **self._metadata()}
        boundary = result["cardinal_boundary_left_limit"]
        if boundary is not None:
            boundary["recomputed_right_anchor_du_exact"] = boundary.pop(
                "printed_right_anchor_du_exact"
            )
        return result

    def audit(self) -> dict[str, Any]:
        result = self.generated.audit()
        for segment in result["segments"]:
            segment["recomputed_midnight_span_du_exact"] = segment.pop(
                "printed_midnight_span_du_exact"
            )
        return {
            **result,
            **self._metadata(),
            "cardinal_anchor_records": json.loads(self.anchor_records_json),
            "all5_cardinals_retained": True,
            "endpoint_closure_is_not_an_accuracy_score": True,
            "rate_policy_automatically_selected_as_best": False,
        }


def load_recomputed_midnight(
    profile: str, *, rate_policy: str
) -> RecomputedMidnightSolar:
    if profile != PROFILE or rate_policy not in RATE_POLICIES:
        raise ValueError("须明确具名四正算例及选率政策，不默认选最有利结果")
    raw, policy_sha = _source()
    daily_blob = DAILY_DATA.read_bytes()
    if hashlib.sha256(daily_blob).hexdigest() != raw["source_daily_data_sha256"]:
        raise ValueError("四正源操作数已改变，不能沿用已冻结的选率版本")
    base = load_generated_daily_solar(DAILY_PROFILE)
    if base.generator.data_sha256 != raw["generator_parameter_sha256"]:
        raise ValueError("立成生成参数已改变，不能静默重新基准化锚点")
    source = json.loads(daily_blob)
    if tuple(source["cardinals"]) != CARDINALS:
        raise ValueError("四正操作数顺序不符，不能排序后补成同一版本")
    operands = source["source_subtraction_components"]
    fields = (
        "event_unwrapped_du",
        "event_fraction_of_source_day",
        "printed_event_rate_du",
        "separately_printed_subtraction_du",
    )
    if any(len(operands[name]) != 5 for name in fields):
        raise ValueError("须保留五组加时操作数，不丢弃不闭合的一正")
    selections = raw["gujin43_explicit_generator_indices"]
    if selections != [
        {"origin": "winter", "index": 0},
        {"origin": "summer", "index": 93},
        {"origin": "summer", "index": 0},
        {"origin": "winter", "index": 88},
        {"origin": "winter", "index": 0},
    ] or any(type(row["index"]) is not int for row in selections):
        raise ValueError("卷43具名查表日序不符，不移一行凑减分")
    anchors: list[F] = []
    records = []
    for i, cardinal in enumerate(CARDINALS):
        position, fraction, printed_rate, printed_subtraction = (
            _number(operands[name][i]) for name in fields
        )
        if not 0 <= fraction < 1:
            raise ValueError("小余须在一个原历日内，不按UTC或刻数重新缩放")
        distance = (
            base.literal.offsets[i + 1] - base.literal.offsets[i]
            if cardinal in ("spring", "autumn")
            else None
        )
        selection = selections[i]
        row = base.generator.branch(selection["origin"]).rows()[selection["index"]]
        if row.motion_du is None:
            raise ValueError("原表所选日无下一日率，不外推端点")
        if rate_policy == RATE_POLICIES[0]:
            rate = printed_rate
        elif rate_policy == RATE_POLICIES[1]:
            rate = gujin39_cardinal_rate(cardinal, distance_days=distance)
        else:
            rate = row.motion_du
        product = fraction * rate
        anchor = position - product
        anchors.append(anchor)
        records.append(
            {
                "cardinal": cardinal,
                "event_position_du_exact": str(position),
                "event_fraction_of_source_day_exact": str(fraction),
                "distance_to_next_cardinal_source_days": distance,
                "legacy_normalized_printed_rate_du": operands[fields[2]][i],
                "selected_rate_du_exact": str(rate),
                "selected_rate_minus_legacy_printed_du_exact": str(rate - printed_rate),
                "Gujin43_declared_generator_index": selection,
                "generated_rate_at_Gujin43_index_du_exact": str(row.motion_du),
                "exact_fraction_times_selected_rate_du": str(product),
                "separately_printed_subtraction_du_exact": str(printed_subtraction),
                "product_minus_printed_subtraction_du_exact": str(
                    product - printed_subtraction
                ),
                "recomputed_midnight_du_exact": str(anchor),
                "printed_span_section_midnight_du_exact": str(base.literal.anchors[i]),
                "recomputed_minus_printed_midnight_du_exact": str(
                    anchor - base.literal.anchors[i]
                ),
                "readding_product_recovers_printed_event_by_identity": anchor + product
                == position,
                "spring_source_lexeme": (
                    raw["gujin43_spring_rate_source_lexeme"]
                    if cardinal == "spring"
                    else None
                ),
                "legacy_spring_normalization_not_adjudicated": cardinal == "spring",
                "source_cells_emended": False,
            }
        )
    if any(b <= a for a, b in zip(anchors, anchors[1:])):
        raise ValueError("复算夜半锚点未递增，不用取模或拉伸掩盖异常")
    trajectory = SourceDailySolar(
        PROFILE,
        policy_sha,
        base.generator.source_url,
        base.literal.circle,
        base.literal.offsets,
        tuple(anchors),
        base.trajectory.segments,
    )
    generated = GeneratedDailySolar(base.generator, base.literal, trajectory)
    return RecomputedMidnightSolar(
        generated, rate_policy, policy_sha, json.dumps(records, ensure_ascii=False)
    )
