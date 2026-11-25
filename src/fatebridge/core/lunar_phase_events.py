"""Modern physical phase events in TT, independent of any classical profile.

The complete input window is scanned, with each detected crossing bracketed.
No almanac times, source calendar coefficients or civil offsets seed the solver.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal, Protocol, TypedDict

from fatebridge.core.astro.geometry import Angle, angle_fraction
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    ephemeris_model_from_retflag,
    swe,
)

KINDS = ("new_moon", "first_quarter", "full_moon", "last_quarter")
MILLISECONDS_PER_DAY = 86_400_000


class PhaseAtJulianDay(Protocol):
    def __call__(self, julian_day_tt: float, /) -> Angle: ...


class LunarPhaseEvent(TypedDict):
    phase_kind: str
    target_elongation_degrees: int
    julian_day_tt_millisecond_count: int
    julian_day_tt_exact: str


class LunarPhaseEvents(TypedDict):
    model_id: str
    backend: str
    window_tt_jd: list[float]
    window_membership: str
    timescale: Literal["TT"]
    coordinate_system: str
    output_resolution_milliseconds: int
    solver: str
    events: list[LunarPhaseEvent]
    source_profile_reconstruction: bool
    utc_or_local_civil_calendar_assigned: bool
    physical_accuracy_claimed_from_numerical_resolution: bool


@dataclass(frozen=True)
class PhaseCrossing:
    lower_tt: TTInstant
    upper_tt: TTInstant
    target_elongation: int
    residual: Fraction

    @property
    def tt(self) -> TTInstant:
        return self.upper_tt


def _phase(jd_tt: float) -> Fraction:
    if swe is None:
        raise ValueError("现代相位需要pyswisseph")
    states = []
    for body in (swe.SUN, swe.MOON):
        state, flag = ephemeris_call(
            "calc", jd_tt, body, swe.FLG_MOSEPH | swe.FLG_SPEED
        )
        if ephemeris_model_from_retflag(flag) != "moshier":
            raise ValueError("现代相位未使用声明的Moshier模型，不静默降级或改换模型")
        if not all(math.isfinite(float(state[i])) for i in (0, 3)):
            raise ValueError("星历经度或速度不是有限数")
        states.append(state)
    if states[1][3] <= states[0][3]:
        raise ValueError("月日视黄经差未递增，不能沿用此搜索方法")
    return (Fraction(states[1][0]) - Fraction(states[0][0])) % 360


def phase_crossings_tt(
    start_tt: TTInstant,
    end_tt: TTInstant,
    phase_at: PhaseAtJulianDay,
    *,
    step_degrees: Literal[45, 90],
    include_end: bool = False,
) -> list[PhaseCrossing]:
    """Find first on-or-post crossing source points in the exact TT window."""
    left = start_tt.as_float()
    if left < start_tt.days:
        left = math.nextafter(left, math.inf)
    last = end_tt.as_float()
    if last > end_tt.days or (last == end_tt.days and not include_end):
        last = math.nextafter(last, -math.inf)
    if left > last:
        return []

    rows: list[PhaseCrossing] = []
    max_residual = 1e-6
    phase = angle_fraction(phase_at(left))
    start_residual = phase % step_degrees
    if start_residual < max_residual:
        # The first eligible grid point can already be just past a crossing.
        # Only consult its predecessor for a point within the root tolerance.
        previous = left
        crosses_at_start = start_residual == 0
        if not crosses_at_start:
            previous = math.nextafter(left, -math.inf)
            advance = (phase - angle_fraction(phase_at(previous))) % 360
            crosses_at_start = start_residual < advance < 30
        if crosses_at_start:
            rows.append(
                PhaseCrossing(
                    TTInstant.from_float(previous),
                    TTInstant.from_float(left),
                    int(phase - start_residual) % 360,
                    start_residual,
                )
            )

    while left < last:
        right = min(left + 1.0, last)
        if right <= left:
            raise ValueError("窗口小于可表示JD间隔")
        next_phase = angle_fraction(phase_at(right))
        advance = (next_phase - phase) % 360
        if not 0 < advance < 30:
            raise ValueError("日采样黄经差越界，不跨越未知相位或漏项")
        distance = step_degrees - phase % step_degrees
        if distance <= advance:
            lo, hi = left, right
            angle = int(phase + distance) % 360
            residual = advance - distance
            for _ in range(64):
                mid = (lo + hi) / 2
                if mid in (lo, hi):
                    break
                difference = (angle_fraction(phase_at(mid)) - angle + 180) % 360 - 180
                if difference < 0:
                    lo = mid
                else:
                    hi, residual = mid, difference
            if residual >= max_residual:
                raise ValueError("相位求根未收敛，不输出近似猜测")
            rows.append(
                PhaseCrossing(
                    TTInstant.from_float(lo),
                    TTInstant.from_float(hi),
                    angle,
                    residual,
                )
            )
        left, phase = right, next_phase
    return rows


def phase_events_tt(start_tt: float, end_tt: float) -> LunarPhaseEvents:
    """Every 90-degree apparent elongation crossing in [start_tt, end_tt).

    Endpoint membership uses the first representable post-crossing JD; output
    is rounded once to the nearest millisecond, with ties to even. This
    resolution is not an astronomical accuracy claim or a TT-to-UTC conversion.
    """
    if any(type(v) not in (int, float) for v in (start_tt, end_tt)):
        raise TypeError("TT窗口须为明确的数值JD，不接收布尔、文本或默认时刻")
    if (
        not math.isfinite(start_tt)
        or not math.isfinite(end_tt)
        or not 0 < end_tt - start_tt <= 3660
    ):
        raise ValueError("TT窗口须有限、递增且不超过3660天")
    rows: list[LunarPhaseEvent] = []
    for crossing in phase_crossings_tt(
        TTInstant.from_float(float(start_tt)),
        TTInstant.from_float(float(end_tt)),
        _phase,
        step_degrees=90,
    ):
        count = round(crossing.tt.days * MILLISECONDS_PER_DAY)
        rows.append(
            {
                "phase_kind": KINDS[crossing.target_elongation // 90],
                "target_elongation_degrees": crossing.target_elongation,
                "julian_day_tt_millisecond_count": count,
                "julian_day_tt_exact": str(Fraction(count, MILLISECONDS_PER_DAY)),
            }
        )
    return {
        "model_id": "modern_moshier_apparent_lunar_phases_tt_v1",
        "backend": "moshier",
        "window_tt_jd": [start_tt, end_tt],
        "window_membership": "start_inclusive_end_exclusive_before_millisecond_rounding",
        "timescale": "TT",
        "coordinate_system": "apparent_geocentric_tropical_ecliptic_of_date",
        "output_resolution_milliseconds": 1,
        "solver": "complete_daily_scan_then_bracketed_bisection_no_almanac_seeds",
        "events": rows,
        "source_profile_reconstruction": False,
        "utc_or_local_civil_calendar_assigned": False,
        "physical_accuracy_claimed_from_numerical_resolution": False,
    }
