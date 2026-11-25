"""Numerical root resolution for the declared 88-degree solar function.

Endpoint witnesses describe the evaluated binary64 function, not a physical
time error bound. No ephemeris, calendar or bodygraph implementation lives here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal, Protocol, TypedDict

from typing_extensions import NotRequired

from fatebridge.core.human_design.human_design_solar_lattice import (
    SolarLattice,
    SolarLatticeSample,
    SolarLatticeSummary,
    derive_lattice,
    lattice_summary,
    lattice_times,
)

ROOT_POLICY = (
    "minimum_absolute_exact_residual_over_observed_forward_contacts_then_earlier_TT"
)
SOLAR_COORDINATE_POLICY = "same_apparent_ecliptic_date_SPEED_flags_as_activations_v1"
ROOT_SCOPE = "初始括区及其有限邻点中按精确残差、较早TT选择正到负括区或零点，保留最终二进制TT端点见证；不认证未观测区域的最优性、物理时刻精度、出生钟、连续坐标误差界或其他天体在根区间中的细分稳定性。"


class SolarLongitude(Protocol):
    def __call__(self, jd_tt: float, /) -> float: ...


@dataclass(frozen=True, kw_only=True)
class SolarEvaluation:
    longitude_degrees: float
    residual_degrees: Fraction


class SolarRootEndpoint(SolarLatticeSample):
    residual_degrees: float


class SolarRootPrecision(TypedDict):
    method_id: str
    local_solar_lattice: SolarLattice
    local_solar_lattice_summary: SolarLatticeSummary
    birth_sun_longitude: float
    lower: SolarRootEndpoint
    upper: SolarRootEndpoint
    selected: SolarRootEndpoint
    selection_policy: str
    termination: Literal["observed_exact_function_zero", "adjacent_float_TT_endpoints"]
    physical_time_accuracy_certified: bool
    other_bodies_bracket_sensitivity_assessed: bool
    scope: str
    sun_coordinate_policy: NotRequired[str]


class SolarRoot(TypedDict):
    design_jd_tt: float
    residual_degrees: float
    bracket_width_seconds: float
    iterations: int
    numerical_precision: SolarRootPrecision


def solar_residual(birth_sun: float, design_sun: float) -> Fraction:
    return (Fraction(birth_sun) - Fraction(design_sun)) % 360 - 88


def solve_solar_root(birth_tt: float, sun: SolarLongitude) -> SolarRoot:
    birth_tt = float(birth_tt)
    birth_sun_degrees = sun(birth_tt)
    evaluations: dict[float, SolarEvaluation] = {}

    def evaluate(jd_tt: float) -> SolarEvaluation:
        if jd_tt not in evaluations:
            longitude_degrees = sun(jd_tt)
            if not math.isfinite(longitude_degrees) or not 0 <= longitude_degrees < 360:
                raise RuntimeError("太阳求根函数未返回有效黄经")
            else:
                pass
            evaluations[jd_tt] = SolarEvaluation(
                longitude_degrees=longitude_degrees,
                residual_degrees=solar_residual(birth_sun_degrees, longitude_degrees),
            )
        else:
            pass
        return evaluations[jd_tt]

    lower_jd_tt, upper_jd_tt = birth_tt - 110, birth_tt - 70
    if (
        not evaluate(lower_jd_tt).residual_degrees
        > 0
        > evaluate(upper_jd_tt).residual_degrees
    ):
        raise RuntimeError("设计时刻的太阳黄经未能括定 88 度根")
    else:
        pass
    iterations = 0
    while math.nextafter(lower_jd_tt, math.inf) < upper_jd_tt:
        midpoint_jd_tt = lower_jd_tt + (upper_jd_tt - lower_jd_tt) / 2
        if midpoint_jd_tt in (lower_jd_tt, upper_jd_tt):
            break
        else:
            pass
        residual_degrees = evaluate(midpoint_jd_tt).residual_degrees
        iterations += 1
        if residual_degrees == 0:
            lower_jd_tt = upper_jd_tt = midpoint_jd_tt
            break
        elif residual_degrees > 0:
            lower_jd_tt = midpoint_jd_tt
        else:
            upper_jd_tt = midpoint_jd_tt

    def row(jd_tt: float) -> SolarRootEndpoint:
        evaluation = evaluate(jd_tt)
        return {
            "jd_tt": jd_tt,
            "sun_longitude": evaluation.longitude_degrees,
            "residual_degrees": float(evaluation.residual_degrees),
            # note (precision): Decimal strings preserve the exact rational in JSON clients.
            "exact_residual": {
                "numerator": str(evaluation.residual_degrees.numerator),
                "denominator": str(evaluation.residual_degrees.denominator),
            },
        }

    lattice = derive_lattice(
        birth_sun_degrees,
        lower_jd_tt,
        upper_jd_tt,
        [
            {"jd_tt": jd_tt, "sun_longitude": evaluate(jd_tt).longitude_degrees}
            for jd_tt in lattice_times(lower_jd_tt, upper_jd_tt)
        ],
    )
    contact = lattice["preferred_numeric_contact"]
    # note (bracket): The initial forward bracket or exact zero is among the contacts.
    assert contact is not None
    lower_jd_tt = lattice["samples"][contact["lower_index"]]["jd_tt"]
    upper_jd_tt = lattice["samples"][contact["upper_index"]]["jd_tt"]
    selected_jd_tt = lattice["samples"][contact["selected_index"]]["jd_tt"]

    return {
        "design_jd_tt": selected_jd_tt,
        "residual_degrees": float(evaluate(selected_jd_tt).residual_degrees),
        "bracket_width_seconds": (upper_jd_tt - lower_jd_tt) * 86400,
        "iterations": iterations,
        "numerical_precision": {
            "method_id": "human_design_observed_contact_solar_root_v2",
            "local_solar_lattice": lattice,
            "local_solar_lattice_summary": lattice_summary(lattice),
            "birth_sun_longitude": birth_sun_degrees,
            "lower": row(lower_jd_tt),
            "upper": row(upper_jd_tt),
            "selected": row(selected_jd_tt),
            "selection_policy": ROOT_POLICY,
            "termination": (
                "observed_exact_function_zero"
                if lower_jd_tt == upper_jd_tt
                else "adjacent_float_TT_endpoints"
            ),
            "physical_time_accuracy_certified": False,
            "other_bodies_bracket_sensitivity_assessed": False,
            "scope": ROOT_SCOPE,
        },
    }
