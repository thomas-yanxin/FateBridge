"""Exact source clock notation and conditional branch windows for Song qi.

These are coordinates within a named printed calendar's day. No place, solar
clock, civil timezone, UTC instant or historical birth minute is inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Any

from fatebridge.core.song_qi import SOURCE_77_82, SOURCE_83_86, source_term_remainder

BRANCHES = tuple("子丑寅卯辰巳午未申酉戌亥")


@dataclass(frozen=True)
class _ClockRule:
    day_units: int
    chen_input_factor: int
    chen_divisor: Fraction
    ke_remainder_factor: int
    ke_divisor: Fraction
    source_url: str
    source_sha256: str
    pages: tuple[int, ...]
    procedure_basis: str

    @property
    def chen_days(self) -> Fraction:
        return self.chen_divisor / (self.chen_input_factor * self.day_units)

    @property
    def ke_days(self) -> Fraction:
        return self.ke_divisor / (
            self.chen_input_factor * self.ke_remainder_factor * self.day_units
        )


_RULES = MappingProxyType(
    {
        "songshi_jiyuan_v1": _ClockRule(
            7290,
            2,
            Fraction(1215),
            5,
            Fraction(729),
            SOURCE_77_82,
            "b49475698fafa4248db7cfdd32eb6b8fc8b5ef6998115feecd76a99182ef9f7a",
            (58, 59),
            "printed_double_small_then_five_times_remainder",
        ),
        "songshi_tongyuan_v1": _ClockRule(
            6930,
            1,
            Fraction(1155, 2),
            10,
            Fraction(693),
            SOURCE_83_86,
            "0d262f3efed31b79907762c3f81374cf61540be0b50a8d524644607149f9dedf",
            (6,),
            "printed_chen_then_ten_times_remainder; marginal_character_unresolved",
        ),
        "songshi_tongtian_mei_v1": _ClockRule(
            12000,
            1,
            Fraction(1000),
            1,
            Fraction(120),
            SOURCE_83_86,
            "0d262f3efed31b79907762c3f81374cf61540be0b50a8d524644607149f9dedf",
            (94,),
            "normalized_printed_divisors; omitted_procedure; Mei_clock_captions_checked",
        ),
    }
)


def _rule(profile_id: str) -> _ClockRule:
    if not isinstance(profile_id, str) or profile_id not in _RULES:
        raise ValueError("须显式选择已有原页钟制依据的完整宋历profile_id。")
    return _RULES[profile_id]


def _rational(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def source_clock_from_fraction(
    *, profile_id: str, numerator: int, denominator: int
) -> dict[str, Any]:
    """Normalize exact day fractions to source equal-chen/100-ke notation.

    Zero is 子正. 子初 late in the same source day does not silently change
    its day name. Fraction1 belongs to a separately identified following day
    and is rejected here. Ke counts are zero-based; 初刻 is0, not1.
    """
    p = _rule(profile_id)
    if (
        type(numerator) is not int
        or type(denominator) is not int
        or denominator <= 0
        or not 0 <= numerator < denominator
    ):
        raise ValueError(
            "源日分须为整数分子分母，分母为正，且0≤分子<分母；不接受布尔值或浮点。"
        )
    day = Fraction(numerator, denominator)
    scaled = day * p.day_units * p.chen_input_factor
    chen = scaled // p.chen_divisor
    original_ke = (
        (scaled - chen * p.chen_divisor) * p.ke_remainder_factor / p.ke_divisor
    )
    half = day // (p.chen_days / 2)
    phase = "正" if half % 2 == 0 else "初"
    branch = BRANCHES[((half + 1) // 2) % 12]
    phase_ke = (day - half * p.chen_days / 2) / p.ke_days
    whole_ke = phase_ke // 1
    return {
        "profile_id": profile_id,
        "source_day_fraction": _rational(day),
        "day_origin": "子正",
        "chen_per_day": _rational(1 / p.chen_days),
        "ke_per_day": _rational(1 / p.ke_days),
        "source_day_ke": _rational(day / p.ke_days),
        "original_zheng_anchor": {
            "branch": BRANCHES[chen],
            "phase": "正",
            "whole_ke": original_ke // 1,
            "remaining_ke_fraction": _rational(original_ke % 1),
        },
        "normalized_chu_zheng": {
            "branch": branch,
            "phase": phase,
            "whole_ke": whole_ke,
            "remaining_ke_fraction": _rational(phase_ke % 1),
            "label": branch + phase + "初一二三四"[whole_ke] + "刻",
        },
        "source_day_name_advanced_at_zi_chu": False,
        "notation_policy": "whole_ke_zero_is_initial_ke; exact_remainder_retained; no_rounding_to_next_ke",
        "procedure_basis": p.procedure_basis,
        "source_clock_constants": {
            "day_units": p.day_units,
            "chen_input_factor": p.chen_input_factor,
            "chen_divisor": _rational(p.chen_divisor),
            "ke_remainder_factor": p.ke_remainder_factor,
            "ke_divisor": _rational(p.ke_divisor),
        },
        "source": {
            "url": p.source_url,
            "sha256": p.source_sha256,
            "pages": list(p.pages),
        },
        "time_frame": "named_source_clock_coordinates_only; no_modern_minutes_or_UTC",
        "actual_historical_birth_clock_established": False,
    }


def source_term_clock(
    *, profile_id: str, accumulated_years: int, term_index: int
) -> dict[str, Any]:
    """Attach source clock notation to the same exact source qi calculation."""
    p = _rule(profile_id)
    term = source_term_remainder(
        profile_id=profile_id,
        accumulated_years=accumulated_years,
        term_index=term_index,
    )
    if term["source_day_divisor"] != p.day_units:
        raise ValueError("来源气朔日法与已核钟制日法不一致。")
    fraction = term["source_day_fraction"]
    return {
        "profile_id": profile_id,
        "accumulated_years": accumulated_years,
        "source_term": term,
        "source_clock": source_clock_from_fraction(profile_id=profile_id, **fraction),
        "applied_to_public_four_pillars": False,
    }


def compare_branch_window_to_term(
    *,
    profile_id: str,
    accumulated_years: int,
    term_index: int,
    birth_day_offset_from_term_day: int,
    birth_branch: str,
) -> dict[str, Any]:
    """Compare a whole branch window under an explicit shared-clock assumption.

    The signed day offset must be supplied from separately identified dates.
    Sexagenary labels alone do not identify relative dates. A branch never
    supplies an imputed midpoint, minute, longitude or UTC offset.
    """
    if type(birth_day_offset_from_term_day) is not int:
        raise ValueError("相对源历日位移须为明确整数，不能以干支日名或布尔值猜补。")
    if not isinstance(birth_branch, str) or birth_branch not in BRANCHES:
        raise ValueError("出生时支须为一个明确地支，不猜时支或默认时刻。")
    result = source_term_clock(
        profile_id=profile_id,
        accumulated_years=accumulated_years,
        term_index=term_index,
    )
    f = result["source_term"]["source_day_fraction"]
    boundary = Fraction(f["numerator"], f["denominator"])
    branch_index = BRANCHES.index(birth_branch)
    if branch_index == 0:
        segments = [(Fraction(0), Fraction(1, 24)), (Fraction(23, 24), Fraction(1))]
    else:
        segments = [
            (Fraction(2 * branch_index - 1, 24), Fraction(2 * branch_index + 1, 24))
        ]
    windows = [
        (start + birth_day_offset_from_term_day, end + birth_day_offset_from_term_day)
        for start, end in segments
    ]
    before = any(start < boundary for start, _ in windows)
    after = any(end > boundary for _, end in windows)
    relation = (
        "before_and_at_or_after_possible"
        if before and after
        else "entirely_before" if before else "entirely_at_or_after"
    )
    return {
        **result,
        "comparison_assumption": "birth_and_term_share_this_named_source_clock; identity_not_established",
        "day_offset_basis": "caller_identified_ZiZheng_source_days; no_Bazi_ZiChu_day_rollover",
        "birth_day_offset_from_term_day": birth_day_offset_from_term_day,
        "birth_branch": birth_branch,
        "birth_windows_relative_to_term_day": [
            {"start_inclusive": _rational(start), "end_exclusive": _rational(end)}
            for start, end in windows
        ],
        "possible_before_term": before,
        "possible_at_or_after_term": after,
        "boundary_inside_birth_window": any(
            start <= boundary < end for start, end in windows
        ),
        "relation_under_assumption": relation,
        "single_side_determined_under_assumption": not (before and after),
        "birth_instant_imputed": False,
        "public_month_pillar_changed": False,
    }
