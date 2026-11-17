"""Numerical root resolution for the declared 88-degree solar function.

Endpoint witnesses describe the evaluated binary64 function, not a physical
time error bound. No ephemeris, calendar or bodygraph implementation lives here.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, Callable

from fatebridge.core.human_design_solar_lattice import (
    derive_lattice,
    lattice_summary,
    lattice_times,
)

ROOT_POLICY = (
    "minimum_absolute_exact_residual_over_observed_forward_contacts_then_earlier_TT"
)
SOLAR_COORDINATE_POLICY = "same_apparent_ecliptic_date_SPEED_flags_as_activations_v1"
ROOT_SCOPE = "初始括区及其有限邻点中按精确残差、较早TT选择正到负括区或零点，保留最终二进制TT端点见证；不认证未观测区域的最优性、物理时刻精度、出生钟、连续坐标误差界或其他天体在根区间中的细分稳定性。"


def solar_residual(birth_sun: float, design_sun: float) -> Fraction:
    return (Fraction(birth_sun) - Fraction(design_sun)) % 360 - 88


def solve_solar_root(birth_tt: float, sun: Callable[[float], float]) -> dict[str, Any]:
    birth_tt = float(birth_tt)
    birth_sun = sun(birth_tt)
    values: dict[float, tuple[float, Fraction]] = {}

    def evaluate(tt: float) -> tuple[float, Fraction]:
        if tt not in values:
            longitude = sun(tt)
            if not math.isfinite(longitude) or not 0 <= longitude < 360:
                raise RuntimeError("太阳求根函数未返回有效黄经")
            values[tt] = (longitude, solar_residual(birth_sun, longitude))
        return values[tt]

    lo, hi = birth_tt - 110, birth_tt - 70
    if not evaluate(lo)[1] > 0 > evaluate(hi)[1]:
        raise RuntimeError("设计时刻的太阳黄经未能括定 88 度根")
    iterations = 0
    while math.nextafter(lo, math.inf) < hi:
        mid = lo + (hi - lo) / 2
        if mid in (lo, hi):
            break
        residual = evaluate(mid)[1]
        iterations += 1
        if residual == 0:
            lo = hi = mid
            break
        if residual > 0:
            lo = mid
        else:
            hi = mid

    def row(tt: float) -> dict[str, Any]:
        longitude, residual = evaluate(tt)
        return {
            "jd_tt": tt,
            "sun_longitude": longitude,
            "residual_degrees": float(residual),
            # Decimal strings preserve the exact rational in JSON clients too.
            "exact_residual": {
                "numerator": str(residual.numerator),
                "denominator": str(residual.denominator),
            },
        }

    lattice = derive_lattice(
        birth_sun,
        lo,
        hi,
        [
            {"jd_tt": tt, "sun_longitude": evaluate(tt)[0]}
            for tt in lattice_times(lo, hi)
        ],
    )
    contact = lattice["preferred_numeric_contact"]
    # The initial forward bracket or exact zero is always among these contacts.
    assert contact is not None
    lo = lattice["samples"][contact["lower_index"]]["jd_tt"]
    hi = lattice["samples"][contact["upper_index"]]["jd_tt"]
    selected = lattice["samples"][contact["selected_index"]]["jd_tt"]

    return {
        "design_jd_tt": selected,
        "residual_degrees": float(evaluate(selected)[1]),
        "bracket_width_seconds": (hi - lo) * 86400,
        "iterations": iterations,
        "numerical_precision": {
            "method_id": "human_design_observed_contact_solar_root_v2",
            "local_solar_lattice": lattice,
            "local_solar_lattice_summary": lattice_summary(lattice),
            "birth_sun_longitude": birth_sun,
            "lower": row(lo),
            "upper": row(hi),
            "selected": row(selected),
            "selection_policy": ROOT_POLICY,
            "termination": (
                "observed_exact_function_zero"
                if lo == hi
                else "adjacent_float_TT_endpoints"
            ),
            "physical_time_accuracy_certified": False,
            "other_bodies_bracket_sensitivity_assessed": False,
            "scope": ROOT_SCOPE,
        },
    }
