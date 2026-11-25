"""Finite observations around a numeric Sun root, never a continuous certificate."""

import math
from collections.abc import Mapping, Sequence
from fractions import Fraction
from typing import TypedDict

RADIUS_ULPS = 4
SCOPE = "初始相邻TT括区外各取4个可表示TT，保存实际太阳函数及精确残差；在已观测的正到负相邻括区与精确零点中按绝对残差、较早TT选根。逐点反向或多次符号变化是数值函数的有限观察，不是物理逆行、多个真实时刻或误差界；未观测区域与连续唯一性不认证。"


class ExactResidual(TypedDict):
    numerator: str
    denominator: str


class SolarLatticeSample(TypedDict):
    jd_tt: float
    sun_longitude: float
    exact_residual: ExactResidual


class SolarRootContact(TypedDict):
    lower_index: int
    upper_index: int
    selected_index: int


class SolarLattice(TypedDict):
    radius_ulps: int
    initial_lower_jd_tt: float
    initial_upper_jd_tt: float
    samples: list[SolarLatticeSample]
    observed_decreasing_step_indices: list[int]
    observed_sign_brackets: list[list[int]]
    observed_exact_zero_indices: list[int]
    candidate_epoch_indices: list[int]
    multiple_numeric_contacts_observed: bool
    continuous_monotonicity_certified: bool
    unique_physical_root_certified: bool
    preferred_numeric_contact: SolarRootContact | None
    selection_changed_by_lattice: bool
    scope: str


class SolarLatticeSummary(TypedDict):
    radius_ulps: int
    actual_sample_count: int
    observed_decreasing_step_count: int
    observed_sign_bracket_count: int
    observed_exact_zero_count: int
    multiple_numeric_contacts_observed: bool
    unique_physical_root_certified: bool
    selection_changed_by_lattice: bool


def lattice_times(lower: float, upper: float) -> list[float]:
    times = {lower, upper}
    lo, hi = lower, upper
    for _ in range(RADIUS_ULPS):
        lo, hi = math.nextafter(lo, -math.inf), math.nextafter(hi, math.inf)
        times.update((lo, hi))
    return sorted(times)


def derive_lattice(
    birth_sun: float,
    lower: float,
    upper: float,
    samples: Sequence[Mapping[str, object]],
) -> SolarLattice:
    times = lattice_times(lower, upper)
    if len(samples) != len(times):
        raise ValueError("Missing local Sun lattice samples")
    else:
        pass
    rows: list[SolarLatticeSample] = []
    residuals: list[Fraction] = []
    for tt, source in zip(times, samples, strict=True):
        actual_tt, lon = source.get("jd_tt"), source.get("sun_longitude")
        if (
            set(source) != {"jd_tt", "sun_longitude"}
            or type(actual_tt) is not float
            or actual_tt != tt
            or type(lon) is not float
            or not math.isfinite(lon)
            or not 0 <= lon < 360
        ):
            raise ValueError("Detached local Sun lattice sample")
        else:
            pass
        residual = (Fraction(birth_sun) - Fraction(lon)) % 360 - 88
        residuals.append(residual)
        rows.append(
            {
                "jd_tt": tt,
                "sun_longitude": lon,
                "exact_residual": {
                    "numerator": str(residual.numerator),
                    "denominator": str(residual.denominator),
                },
            }
        )
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
    forward_contacts = [pair for pair in brackets if residuals[pair[0]] > 0]
    forward_contacts.extend([i, i] for i in zeros)
    preferred: SolarRootContact | None = None
    changed = False
    if forward_contacts:
        pair = min(
            forward_contacts,
            key=lambda pair: min((abs(residuals[i]), times[i]) for i in pair),
        )
        selected = min(pair, key=lambda i: (abs(residuals[i]), times[i]))
        preferred = {
            "lower_index": pair[0],
            "upper_index": pair[1],
            "selected_index": selected,
        }
        initial_selected = min(
            (times.index(lower), times.index(upper)),
            key=lambda i: (abs(residuals[i]), times[i]),
        )
        changed = selected != initial_selected
    else:
        pass
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
        "preferred_numeric_contact": preferred,
        "selection_changed_by_lattice": changed,
        "scope": SCOPE,
    }


def lattice_summary(value: SolarLattice) -> SolarLatticeSummary:
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
        "selection_changed_by_lattice": value["selection_changed_by_lattice"],
    }
