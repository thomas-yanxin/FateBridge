"""Finite observations around a numeric Sun root, never a continuous certificate."""

import math
from fractions import Fraction
from typing import Any

RADIUS_ULPS = 4
SCOPE = "初始相邻TT括区外各取4个可表示TT，保存实际太阳函数及精确残差；逐点反向或多次符号变化属于该数值函数的有限观察，不是物理逆行、多个真实时刻或误差界。主盘保留原括区的最小残差选根，不为数值噪声换根；未观测区域与连续唯一性不认证。"


def lattice_times(lower: float, upper: float) -> list[float]:
    times = {lower, upper}
    lo, hi = lower, upper
    for _ in range(RADIUS_ULPS):
        lo, hi = math.nextafter(lo, -math.inf), math.nextafter(hi, math.inf)
        times.update((lo, hi))
    return sorted(times)


def derive_lattice(
    birth_sun: float, lower: float, upper: float, samples: list[dict[str, Any]]
) -> dict[str, Any]:
    times = lattice_times(lower, upper)
    if len(samples) != len(times):
        raise ValueError("Missing local Sun lattice samples")
    rows = []
    for tt, source in zip(times, samples, strict=True):
        if (
            set(source) != {"jd_tt", "sun_longitude"}
            or type(source["jd_tt"]) is not float
            or source["jd_tt"] != tt
            or type(source["sun_longitude"]) is not float
            or not math.isfinite(source["sun_longitude"])
            or not 0 <= source["sun_longitude"] < 360
        ):
            raise ValueError("Detached local Sun lattice sample")
        lon = source["sun_longitude"]
        residual = (Fraction(birth_sun) - Fraction(lon)) % 360 - 88
        rows.append(
            {
                **source,
                "exact_residual": {
                    "numerator": str(residual.numerator),
                    "denominator": str(residual.denominator),
                },
            }
        )
    residuals = [
        Fraction(r["exact_residual"]["numerator"])
        / Fraction(r["exact_residual"]["denominator"])
        for r in rows
    ]
    reversed_steps = [
        i
        for i in range(len(rows) - 1)
        if (
            Fraction(rows[i + 1]["sun_longitude"])
            - Fraction(rows[i]["sun_longitude"])
            + 180
        )
        % 360
        - 180
        < 0
    ]
    brackets = [
        [i, i + 1] for i in range(len(rows) - 1) if residuals[i] * residuals[i + 1] < 0
    ]
    zeros = [i for i, r in enumerate(residuals) if r == 0]
    indices = sorted({i for pair in brackets for i in pair} | set(zeros))
    return {
        "radius_ulps": RADIUS_ULPS,
        "initial_lower_jd_tt": lower,
        "initial_upper_jd_tt": upper,
        "samples": rows,
        "observed_decreasing_step_indices": reversed_steps,
        "observed_sign_brackets": brackets,
        "observed_exact_zero_indices": zeros,
        "candidate_epoch_indices": indices,
        "multiple_numeric_contacts_observed": len(brackets) + len(zeros) > 1,
        "continuous_monotonicity_certified": False,
        "unique_physical_root_certified": False,
        "selection_changed_by_lattice": False,
        "scope": SCOPE,
    }


def lattice_summary(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "radius_ulps": value["radius_ulps"],
        "actual_sample_count": len(value["samples"]),
        "observed_decreasing_step_count": len(
            value["observed_decreasing_step_indices"]
        ),
        "observed_sign_bracket_count": len(value["observed_sign_brackets"]),
        "observed_exact_zero_count": len(value["observed_exact_zero_indices"]),
        "multiple_numeric_contacts_observed": value[
            "multiple_numeric_contacts_observed"
        ],
        "unique_physical_root_certified": False,
        "selection_changed_by_lattice": False,
    }
