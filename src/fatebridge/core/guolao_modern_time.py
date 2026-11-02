"""Modern TT season roots and explicitly declared historical clock comparison.

Neither numerical root resolution nor an approximate meridian site calibrates
an ancient observation. Historical TDB-UT1 values remain model estimates.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fatebridge.core.ephemeris_runtime import (
    ephemeris_call,
    ephemeris_model_from_retflag,
    lock_ephemeris_configuration,
    swe,
)

SOLAR_PROFILE = "modern_moshier_apparent_solar_crossing_tt_v1"
CLOCK_POLICY = "pre1962_horizons_TDB_minus_UT1_approx_TT_minus_UT1"


def apparent_solar_state_tt(
    jd_tt: float, *, backend: str, frame: str
) -> dict[str, Any]:
    """Explicit frame/model diagnostic; keep default date coordinates intact."""
    if type(jd_tt) not in (int, float) or not math.isfinite(jd_tt):
        raise ValueError("太阳参考须为有限TT JD")
    if swe is None or backend not in ("moshier", "swieph_de441"):
        raise ValueError("须明确Moshier或具有DE441文件的Swiss模型")
    if frame not in ("apparent_equatorial_icrf", "native_apparent_tropical_date"):
        raise ValueError("须明确惯性或原生日期坐标，不以拟合残差改坐标")
    flag = swe.FLG_MOSEPH if backend == "moshier" else swe.FLG_SWIEPH
    flag |= swe.FLG_SPEED
    if frame == "apparent_equatorial_icrf":
        flag |= swe.FLG_J2000 | swe.FLG_ICRS | swe.FLG_EQUATORIAL
    with lock_ephemeris_configuration():
        position, returned = ephemeris_call("calc", jd_tt, swe.SUN, flag)
        if ephemeris_model_from_retflag(returned) != (
            "moshier" if backend == "moshier" else "swieph"
        ):
            raise ValueError("太阳诊断模型降级或改变，不能混作声明结果")
        if not all(math.isfinite(v) for v in position):
            raise ValueError("太阳诊断出现非有限坐标")
        files = []
        if backend == "swieph_de441":
            for file_id in (0, 1):
                name, first, last, denum = ephemeris_call(
                    "get_current_file_data", file_id
                )
                if not name or denum != 441 or not first <= jd_tt <= last:
                    raise ValueError("太阳诊断未实际使用覆盖该TT的DE441文件")
                path = Path(name)
                raw = path.read_bytes()
                files.append(
                    {
                        "filename": path.name,
                        "native_file_id": file_id,
                        "jpl_denum": denum,
                        "start_jd": first,
                        "end_jd": last,
                        "bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                )
        return {
            "backend": backend,
            "frame": frame,
            "tt_jd_exact": str(F(jd_tt)),
            "position": list(position),
            "native_return_flags": returned,
            "observed_source_files": files,
            "observed_files_prove_complete_atomic_file_read": False,
            "frame_matched_to_Horizons_by_fitted_offset": False,
        }


def solar_crossing_tt(target: float, start_tt: float, end_tt: float) -> dict[str, Any]:
    """Unique forward apparent tropical solar crossing in [start,end), TT JD.

    Scan the entire declared window. Return the first representable evaluated
    nonnegative endpoint; retain the binary64 bracket without display rounding.
    """
    if any(type(v) not in (int, float) for v in (target, start_tt, end_tt)):
        raise TypeError("太阳目标度和TT窗口须为明确数值，不接收布尔或隐式时区")
    if not all(math.isfinite(v) for v in (target, start_tt, end_tt)) or not (
        0 <= target < 360 and 0 < end_tt - start_tt <= 31
    ):
        raise ValueError("目标须在0至360度，TT窗口须有限、递增且不超过31日")
    if swe is None:
        raise ValueError("现代太阳参考需要pyswisseph")
    values: dict[float, tuple[float, int]] = {}

    def evaluate(at: float) -> float:
        if at not in values:
            position, flag = ephemeris_call(
                "calc", at, swe.SUN, swe.FLG_MOSEPH | swe.FLG_SPEED
            )
            if ephemeris_model_from_retflag(flag) != "moshier":
                raise ValueError("现代太阳未使用声明的Moshier，不静默切换模型")
            longitude, speed = float(position[0]), float(position[3])
            if (
                not math.isfinite(longitude)
                or not 0 <= longitude < 360
                or not (math.isfinite(speed) and 0 < speed < 2)
            ):
                raise ValueError("太阳位置或速度无效，不输出猜测根")
            values[at] = longitude, flag
        return values[at][0]

    def residual(at: float) -> float:
        difference = evaluate(at) - target
        if difference >= 180:
            difference -= 360
        elif difference < -180:
            difference += 360
        return difference

    with lock_ephemeris_configuration():
        left = float(start_tt)
        longitude = evaluate(left)
        candidates = [(left, left)] if residual(left) == 0 else []
        while left < end_tt:
            right = min(left + 1, float(end_tt))
            if right <= left:
                raise ValueError("TT窗口小于可表示间隔")
            next_longitude = evaluate(right)
            if not 0 < (next_longitude - longitude) % 360 < 2:
                raise ValueError("日采样太阳未按声明方向前行")
            if residual(left) < 0 <= residual(right):
                if not (right == end_tt and residual(right) == 0):
                    candidates.append((left, right))
            left, longitude = right, next_longitude
        if len(candidates) != 1:
            raise ValueError("固定TT窗口内无唯一交点，不扩大窗口追拟原历")
        low, high = candidates[0]
        iterations = 0
        while math.nextafter(low, math.inf) < high:
            middle = low + (high - low) / 2
            if middle in (low, high):
                break
            if residual(middle) < 0:
                low = middle
            else:
                high = middle
            iterations += 1
        if not start_tt <= high < end_tt or not 0 <= residual(high) < 1e-6:
            raise ValueError("TT交点未收敛或不在声明窗口")
        flags = sorted({flag for _, flag in values.values()})
        if len(flags) != 1:
            raise ValueError("求根中原生标志改变，不混合计算环境")
        return {
            "profile_id": SOLAR_PROFILE,
            "backend": "moshier",
            "native_version": str(swe.version),
            "native_flags": flags,
            "timescale": "TT",
            "coordinate_system": "apparent_geocentric_tropical_ecliptic_of_date",
            "target_degrees": target,
            "window_tt_jd": [start_tt, end_tt],
            "membership": "start_inclusive_end_exclusive",
            "selected_jd_tt_exact": str(F(high)),
            "bracket_tt_jd_exact": [str(F(low)), str(F(high))],
            "bracket_residual_degrees_exact": [
                str(F(residual(low))),
                str(F(residual(high))),
            ],
            "bracket_width_seconds_exact": str((F(high) - F(low)) * 86400),
            "iterations": iterations,
            "selection_policy": "first_representable_evaluated_nonnegative_endpoint",
            "solver": "complete_daily_scan_then_adjacent_binary64_bisection",
            "numerical_resolution_is_physical_accuracy": False,
            "UTC_or_historical_local_clock_assigned": False,
        }


def historical_clock_components(
    tt_jd: F,
    tdb_minus_ut1_seconds: F,
    apparent_solar_hours: F,
    longitude_east_degrees: F,
    *,
    year: int,
    timescale_difference_policy: str,
) -> dict[str, Any]:
    """Separate TT, Earth rotation, meridian and apparent-solar corrections.

    Only the pre1962 Horizons convention is supported. Post1962 TDB-UTC must
    never be silently treated as TDB-UT1. The site and ΔT are external inputs.
    """
    if type(year) is not int or not 1 <= year < 1962:
        raise ValueError("仅支持明确的1962年前年份，后期TDB-UTC不能冒充UT1差")
    if timescale_difference_policy != CLOCK_POLICY:
        raise ValueError("须声明历史TDB-UT1近似TT-UT1的政策")
    if any(
        not isinstance(v, F)
        for v in (
            tt_jd,
            tdb_minus_ut1_seconds,
            apparent_solar_hours,
            longitude_east_degrees,
        )
    ):
        raise TypeError("时间、太阳时和经度须为精确Fraction输入")
    ordinal = (tt_jd + F(1, 2)).numerator // (tt_jd + F(1, 2)).denominator - 1721425
    if (
        not 1 <= ordinal <= date.max.toordinal()
        or date.fromordinal(ordinal).year != year
    ):
        raise ValueError("年份须对应TT的前推格里历标签，不能伪报旧年份套用UT1政策")
    if not 0 <= apparent_solar_hours < 24 or not -180 <= longitude_east_degrees <= 180:
        raise ValueError("太阳时须在0至24小时、东经在正负180度范围内")
    ut1_approx = tt_jd - tdb_minus_ut1_seconds / 86400
    meridian = longitude_east_degrees / 360
    mean_local_serial = ut1_approx + F(1, 2) + meridian
    apparent_fraction = apparent_solar_hours / 24
    equation = (apparent_fraction - mean_local_serial % 1 + F(1, 2)) % 1 - F(1, 2)
    if abs(equation) >= F(1, 20):
        raise ValueError("太阳时与地方平太阳时差异常，不猜日界或改符号")
    return {
        "timescale_difference_policy": timescale_difference_policy,
        "tt_jd_exact": str(tt_jd),
        "supplied_TDB_minus_UT1_seconds_exact": str(tdb_minus_ut1_seconds),
        "TT_TDB_periodic_difference_not_maintained_bound_seconds": "0.002",
        "approximate_ut1_jd_exact": str(ut1_approx),
        "longitude_east_degrees_exact": str(longitude_east_degrees),
        "meridian_day_correction_exact": str(meridian),
        "mean_local_calendar_label_serial_exact": str(mean_local_serial),
        "supplied_apparent_solar_hours_exact": str(apparent_solar_hours),
        "equation_of_time_seconds_exact": str(equation * 86400),
        "apparent_local_calendar_label_serial_exact": str(mean_local_serial + equation),
        "historical_earth_rotation_model_uncertainty_quantified": False,
        "precise_historical_observatory_location_established": False,
        "source_midnight_and_clock_policy_calibrated": False,
        "UTC_assigned": False,
    }
