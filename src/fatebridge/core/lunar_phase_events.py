"""Modern physical phase events in TT, independent of any classical profile.

The complete input window is scanned before bracketing. No almanac event times,
source calendar coefficients or civil time-zone offsets seed the solver.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    ephemeris_model_from_retflag,
    swe,
)

KINDS = ("new_moon", "first_quarter", "full_moon", "last_quarter")
MILLISECONDS_PER_DAY = 86_400_000


def _phase(jd_tt: float) -> float:
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
    return float((states[1][0] - states[0][0]) % 360)


def phase_events_tt(start_tt: float, end_tt: float) -> dict[str, Any]:
    """Every 90-degree apparent elongation crossing in [start_tt, end_tt).

    Endpoint membership uses the first representable post-crossing JD; output
    is rounded to a millisecond, with its resolution explicit. This numerical
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
    left = float(start_tt)
    phase = _phase(left)
    unwrapped = phase
    target = (math.floor(phase / 90) + 1) * 90
    rows = []

    def append(at: float, angle: float) -> None:
        count = round(at * MILLISECONDS_PER_DAY)
        rows.append(
            {
                "phase_kind": KINDS[int(angle // 90) % 4],
                "target_elongation_degrees": int(angle) % 360,
                "julian_day_tt_millisecond_count": count,
                "julian_day_tt_exact": str(Fraction(count, MILLISECONDS_PER_DAY)),
            }
        )

    if phase % 90 == 0:
        append(left, phase)
    while left < end_tt:
        right = min(left + 1.0, end_tt)
        if right <= left:
            raise ValueError("窗口小于可表示JD间隔")
        next_phase = _phase(right)
        advance = (next_phase - phase) % 360
        if not 0 < advance < 30:
            raise ValueError("日采样黄经差越界，不跨越未知相位或漏项")
        next_unwrapped = unwrapped + advance
        if target <= next_unwrapped:
            lo, hi = left, right
            angle = target % 360

            def offset(at: float) -> float:
                difference = _phase(at) - angle
                # Avoid adding180 first: it can round a tiny negative residual
                # to zero and move an exact endpoint into the preceding window.
                if difference >= 180:
                    difference -= 360
                elif difference < -180:
                    difference += 360
                return difference

            if not offset(lo) < 0 <= offset(hi):
                raise ValueError("视黄经相位未被固定采样区间夹住")
            for _ in range(64):
                mid = (lo + hi) / 2
                if mid in (lo, hi):
                    break
                if offset(mid) < 0:
                    lo = mid
                else:
                    hi = mid
            if not 0 <= offset(hi) < 1e-6:
                raise ValueError("相位求根未收敛，不输出近似猜测")
            exact_end_crossing = right == end_tt and next_phase == angle
            if start_tt <= hi < end_tt and not exact_end_crossing:
                append(hi, angle)
            target += 90
        left, phase, unwrapped = right, next_phase, next_unwrapped
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
