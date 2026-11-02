"""Named historical syzygy research; no accepted civil calendar or modern epoch.

The Gujin witness supplies angular corrections, but its per-limit velocity
table has not been adjudicated. Li & Zhang (1996) supplies an independently
named, complete published-formula reconstruction. Neither is a native chart
calculation, and the paper's printed formula must not be silently emended to
match its numerical table.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, STEMS
from fatebridge.core.guolao_lunations import GUJIN, source_mean_lunation

DATA = Path(__file__).resolve().parents[1] / "data/guolao/shoushi-conjunctions-v1.json"
GUJIN_COMPONENTS = "gujin36_37_printed_components"
LI_1996 = "li_zhang_1996_printed_formula"


def _profile(profile_id: str) -> tuple[dict[str, Any], str]:
    blob = DATA.read_bytes()
    data = json.loads(blob)
    if not isinstance(profile_id, str) or profile_id not in data["profiles"]:
        raise ValueError("须明确选择具名定朔研究参数，不自动选择或混用原典与论文")
    profile = data["profiles"][profile_id]
    if profile["terminal_limit_method"] not in {
        "printed_168_minus_limit",
        "half_month_minus_within_then_scale",
    }:
        raise ValueError("未核对的末限算法，不自动回退")
    return profile, hashlib.sha256(blob).hexdigest()


def _exact(value: Fraction, name: str) -> None:
    if not isinstance(value, Fraction):
        raise TypeError(f"{name}须为Fraction原历日数，不接收现代JD浮点值")


def solar_correction(days_from_winter: Fraction, *, profile_id: str) -> dict[str, Any]:
    """Signed 盈縮 in source 古度; a fixed printed half-year, not modern degrees."""
    _exact(days_from_winter, "距冬至日数")
    p, digest = _profile(profile_id)
    half = Fraction(p["half_year_days"])
    phase = days_from_winter % (2 * half)
    surplus = phase < half
    within = phase if surplus else phase - half
    cut = Fraction(
        p["surplus_initial_limit_days"] if surplus else p["deficit_initial_limit_days"]
    )
    initial = within <= cut
    argument = within if initial else half - within
    branch = (
        "surplus_initial_deficit_terminal"
        if surplus == initial
        else "deficit_initial_surplus_terminal"
    )
    fixed, linear, cubic = map(Fraction, p["solar_polynomials"][branch])
    correction = (
        argument * (fixed - argument * (linear + cubic * argument)) / 100_000_000
    )
    if not surplus:
        correction = -correction
    return {
        "profile_id": profile_id,
        "source_data_sha256": digest,
        "solar_phase_days_exact": str(phase),
        "half_year_days_exact": str(half),
        "phase": "盈" if surplus else "縮",
        "limit": "初" if initial else "末",
        "argument_days_exact": str(argument),
        "polynomial_branch": branch,
        "polynomial_coefficients": p["solar_polynomials"][branch],
        "signed_correction_ancient_du_exact": str(correction),
        "modern_degrees": None,
    }


def lunar_correction(anomaly_days: Fraction, *, profile_id: str) -> dict[str, Any]:
    """Signed 遲疾, preserving the witness's non-closing 12.2/168 limits."""
    _exact(anomaly_days, "入转日数")
    p, digest = _profile(profile_id)
    period = Fraction(p["anomalistic_month_days"])
    half = period / 2
    phase = anomaly_days % period
    fast = phase <= half
    within = phase if fast else phase - half
    limit = within * Fraction(p["lunar_limits_per_day"])
    initial = limit <= 84
    if initial:
        argument = limit
    elif p["terminal_limit_method"] == "printed_168_minus_limit":
        argument = 168 - limit
    elif p["terminal_limit_method"] == "half_month_minus_within_then_scale":
        argument = (half - within) * Fraction(p["lunar_limits_per_day"])
    else:
        raise ValueError("未核对的末限算法，不自动回退")
    raw = argument * (11_110_000 - argument * (28_100 + 325 * argument)) / 100_000_000
    signed = -raw if fast else raw
    valid = 0 <= argument <= 84
    return {
        "profile_id": profile_id,
        "source_data_sha256": digest,
        "anomaly_phase_days_exact": str(phase),
        "phase": "疾" if fast else "遲",
        "limit": "初" if initial else "末",
        "within_half_days_exact": str(within),
        "unreflected_limit_exact": str(limit),
        "polynomial_argument_limits_exact": str(argument),
        "raw_signed_polynomial_ancient_du_exact": str(signed),
        "argument_within_printed_limits": valid,
        "signed_correction_ancient_du_exact": str(signed) if valid else None,
        "limit_clipped_or_rescaled": False,
        "half_month_limit_closure_residual_exact": str(
            half * Fraction(p["lunar_limits_per_day"]) - 168
        ),
        "modern_degrees": None,
    }


def li_1996_lunar_velocity(anomaly_days: Fraction) -> dict[str, Any]:
    """Paper eqs22--26, including its two exceptional constant-speed bands.

    Overlapping printed endpoints use the first listed interval (<=). This
    research convention is reported; it does not adjudicate the original
    Gujin table's cell boundaries or replace discrete lookup by interpolation.
    """
    _exact(anomaly_days, "入转日数")
    p, digest = _profile(LI_1996)
    phase = anomaly_days % Fraction(p["anomalistic_month_days"])
    half = Fraction(p["anomalistic_month_days"]) / 2
    rate_day = Fraction(p["limit_duration_days"])
    if phase <= Fraction("6.6420"):
        equation, argument, sign = 22, phase / rate_day, 1
    elif phase <= Fraction("7.0520"):
        equation, argument, sign = 23, Fraction(), 0
    elif phase <= Fraction("20.4193"):
        equation, argument, sign = 24, abs(half - phase) / rate_day, -1
    elif phase <= Fraction("20.8293"):
        equation, argument, sign = 25, Fraction(), 0
    else:
        equation, argument, sign = 26, (2 * half - phase) / rate_day, 1
    q = (
        Fraction("0.11081575")
        - Fraction("0.0005815") * argument
        - Fraction("0.00000975") * argument * (argument - 1)
    )
    velocity = Fraction(p["mean_lunar_velocity_ancient_du_per_limit"]) + sign * q
    return {
        "profile_id": LI_1996,
        "source_data_sha256": digest,
        "equation_number": equation,
        "anomaly_phase_days_exact": str(phase),
        "argument_limits_exact": str(argument),
        "velocity_ancient_du_per_limit_exact": str(velocity),
        "limit_duration_days_exact": str(rate_day),
        "endpoint_policy": "first_listed_closed_upper_endpoint",
        "original_gujin_discrete_table_reconstructed": False,
    }


def source_conjunction(
    zhongji_days: Fraction, lunation_index: int, *, profile_id: str
) -> dict[str, Any]:
    """Mean -> solar/lunar -> published correction, with explicit missing links.

    Index0 is 天正經朔. It is not an assigned civil month, including when the
    corrected conjunction crosses a midnight or a winter-solstice boundary.
    """
    return _source_phase_components(
        zhongji_days, lunation_index, Fraction(), profile_id=profile_id
    )


def _source_phase_components(
    zhongji_days: Fraction,
    lunation_index: int,
    fraction_of_mean_month: Fraction,
    *,
    profile_id: str,
) -> dict[str, Any]:
    """Shared components; legacy conjunction keys stay internal for other phases."""
    _exact(zhongji_days, "中积")
    _exact(fraction_of_mean_month, "朔内经月份额")
    if not 0 <= fraction_of_mean_month < 1:
        raise ValueError("朔内经月份额须在0至1之间，不能隐式转移经朔序号")
    if zhongji_days < 0:
        raise ValueError("中积须非负；不以负数猜测上考")
    if isinstance(lunation_index, bool) or not isinstance(lunation_index, int):
        raise TypeError("经朔序号须为非负整数")
    if lunation_index < 0:
        raise ValueError("经朔序号须非负；0为天正经朔")
    p, digest = _profile(profile_id)
    mean = source_mean_lunation(zhongji_days, Fraction(), profile_id=GUJIN)
    if Fraction(p["runying_days"]) != Fraction(mean["runying_days_exact"]):
        raise ValueError("具名角差与经朔闰应不符，不能混参")
    runyu = Fraction(mean["runyu_days_exact"])
    month = Fraction(mean["synodic_month_days_exact"])
    offset = (lunation_index + fraction_of_mean_month) * month - runyu
    mean_total = zhongji_days + Fraction("55.06") + offset
    anomaly = (zhongji_days + Fraction(p["zhuanying_days"]) + offset) % Fraction(
        p["anomalistic_month_days"]
    )
    solar = solar_correction(offset, profile_id=profile_id)
    lunar = lunar_correction(anomaly, profile_id=profile_id)
    velocity = li_1996_lunar_velocity(anomaly) if profile_id == LI_1996 else None
    correction = None
    if velocity is not None and lunar["signed_correction_ancient_du_exact"] is not None:
        correction = (
            Fraction(p["limit_duration_days"])
            * (
                Fraction(solar["signed_correction_ancient_du_exact"])
                + Fraction(lunar["signed_correction_ancient_du_exact"])
            )
            / Fraction(velocity["velocity_ancient_du_per_limit_exact"])
        )
    true_total = mean_total + correction if correction is not None else None
    cycle = true_total % 60 if true_total is not None else None
    day = cycle // 1 if cycle is not None else None
    return {
        "model_id": "shoushi_named_conjunction_research_v1",
        "profile_id": profile_id,
        "source_profile": p,
        "source_data_sha256": digest,
        "mean_lunation_source_data_sha256": mean["source_data_sha256"],
        "zhongji_days_exact": str(zhongji_days),
        "lunation_index": lunation_index,
        "runyu_days_exact": str(runyu),
        "mean_conjunction_offset_from_winter_days_exact": str(offset),
        "mean_conjunction_day_cycle_exact": str(mean_total % 60),
        "solar": solar,
        "lunar": lunar,
        "lunar_velocity": velocity,
        "time_correction_days_exact": (
            str(correction) if correction is not None else None
        ),
        "research_conjunction_offset_from_winter_days_exact": (
            str(offset + correction) if correction is not None else None
        ),
        "research_conjunction_day_cycle_exact": (
            str(cycle) if cycle is not None else None
        ),
        "research_conjunction_sexagenary_day": (
            STEMS[day % 10] + BRANCHES[day % 12] if day is not None else None
        ),
        "midnight_displacement_from_mean_days": (
            true_total // 1 - mean_total // 1 if true_total is not None else None
        ),
        "status": (
            "source_limit_out_of_range_not_repaired"
            if not lunar["argument_within_printed_limits"]
            else (
                "published_formula_research_not_adjudicated"
                if correction is not None
                else "angular_components_only_missing_adjudicated_velocity"
            )
        ),
        "sunrise_shift_applied_to_new_moon": False,
        "lunar_date": None,
        "true_new_moon_calibrated": False,
        "intercalation_reconstructed": False,
        "modern_epoch_calibrated": False,
        "used_in_native_birth_chart": False,
    }
