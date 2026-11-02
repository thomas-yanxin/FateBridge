"""Frozen finite-search replay for allowlisted pre-coordinate cycle receipts.

The validator selects this only after matching a historical ruleset and complete
contract hash. Current calculations always use the current algorithm.
"""

import math
from fractions import Fraction
from typing import Any

from fatebridge.core.human_design_cycles import (
    BODIES,
    HORIZON_DAYS,
    PHASE_METHOD,
    RESIDUAL_DEGREES,
    ROOT_METHOD,
    ROOT_SECONDS,
    STATION_METHOD,
    STATION_SECONDS,
    STEP_DAYS,
    CycleUnavailable,
    Reader,
    Row,
    _increment,
    validate_row,
)

NUMERICAL_SCOPE = "交会/驻点收敛至观测零值或相邻TT，分别取最小精确角残差/速度端点，平局取早；仅同一零值去重。黄经量化可掩盖极近峰值，不认证连续根数量、物理精度或传统首末触优先性。"


def derive_pre_coordinate_body_contacts(
    body: str, birth_tt: float, read: Reader, *, require_swiss_files: bool = False
) -> dict[str, Any]:
    """Replayable numerical derivation. Reader owns native calls or witnesses."""
    _, target = BODIES[body]
    target_exact = Fraction(target)
    contacts: list[dict[str, Any]] = []
    stations: list[dict[str, Any]] = []
    end = birth_tt + HORIZON_DAYS
    first: Row | None = None
    model: str | None = None
    covered_end: float | None = None

    def at(t: float) -> Row:
        nonlocal model
        row = read(t)
        actual = validate_row(row, t, require_swiss_files)
        if model is None:
            model = actual
        elif actual != model:
            raise CycleUnavailable("native_model_changed_within_search", t)
        return row

    def station(left: Row, right: Row) -> tuple[Row, Row, Row]:
        lo, hi = left, right
        while math.nextafter(float(lo[0]), math.inf) < hi[0]:
            t = float(lo[0] + (hi[0] - lo[0]) / 2)
            if t in (lo[0], hi[0]):
                break
            mid = at(t)
            if mid[2] == 0:
                lo = hi = mid
                break
            if (mid[2] > 0) == (lo[2] > 0):
                lo = mid
            else:
                hi = mid
        chosen = min((lo, hi), key=lambda row: (abs(row[2]), row[0]))
        if (hi[0] - lo[0]) * 86400 > STATION_SECONDS:
            raise CycleUnavailable("station_bracket_did_not_converge", float(chosen[0]))
        return chosen, lo, hi

    def crossing(left: Row, lp: Fraction, right: Row, rp: Fraction) -> dict[str, Any]:
        lo, hi, lv, hv = left, right, lp - target_exact, rp - target_exact
        for _ in range(128):
            if lv == 0:
                hi, hv = lo, lv
                break
            if hv == 0:
                lo, lv = hi, hv
                break
            if math.nextafter(float(lo[0]), math.inf) >= hi[0]:
                break
            t = float(lo[0] + (hi[0] - lo[0]) / 2)
            if t in (lo[0], hi[0]):
                break
            mid = at(t)
            mv = lv + _increment(float(mid[1]), float(lo[1]))
            if (mv > 0) == (lv > 0):
                lo, lv = mid, mv
            else:
                hi, hv = mid, mv
        solved, residual = min(
            ((lo, lv), (hi, hv)), key=lambda item: (abs(item[1]), item[0][0])
        )
        t = float(solved[0])
        if (hi[0] - lo[0]) * 86400 > ROOT_SECONDS or (
            lo[0] != hi[0] and math.nextafter(float(lo[0]), math.inf) != hi[0]
        ):
            raise CycleUnavailable("contact_bracket_did_not_converge", t)
        if abs(residual) > RESIDUAL_DEGREES:
            raise CycleUnavailable("angular_root_residual_exceeded", t)
        return {
            "jd_tt": t,
            "longitude": solved[1],
            "longitude_speed": solved[2],
            "return_flags": solved[3],
            "motion": (
                "direct"
                if solved[2] > 0
                else "retrograde" if solved[2] < 0 else "stationary"
            ),
            "residual_degrees": float(residual),
            "exact_residual": {
                "numerator": str(residual.numerator),
                "denominator": str(residual.denominator),
            },
            "phase_arithmetic_method": PHASE_METHOD,
            "root_method": ROOT_METHOD,
            "bracket_jd_tt": [lo[0], hi[0]],
            "bracket_residual_degrees": [float(lv), float(hv)],
            "bracket_exact_residuals": [
                {"numerator": str(v.numerator), "denominator": str(v.denominator)}
                for v in (lv, hv)
            ],
            "bracket_width_seconds": (hi[0] - lo[0]) * 86400,
        }

    failure: dict[str, Any] | None = None
    try:
        first = at(birth_tt)
        left, phase = first, Fraction(0)
        covered_end = birth_tt
        for k in range(1, math.ceil(HORIZON_DAYS / STEP_DAYS) + 1):
            t = min(birth_tt + k * STEP_DAYS, end)
            right = at(t)
            delta = _increment(float(right[1]), float(left[1]))
            if abs(delta) >= 90:
                raise CycleUnavailable("sample_longitude_jump", t)
            right_phase = phase + delta
            points = [(left, phase)]
            if left[2] * right[2] < 0:
                turning, station_lo, station_hi = station(left, right)
                turning_phase = phase + _increment(float(turning[1]), float(left[1]))
                station_residual = turning_phase - target_exact
                stations.append(
                    {
                        "jd_tt": turning[0],
                        "phase_degrees": float(turning_phase),
                        "longitude_speed": turning[2],
                        "method_id": STATION_METHOD,
                        "bracket_jd_tt": [station_lo[0], station_hi[0]],
                        "bracket_longitude_speeds": [station_lo[2], station_hi[2]],
                        "bracket_width_seconds": (station_hi[0] - station_lo[0])
                        * 86400,
                        "target_phase_exact_residual": {
                            "numerator": str(station_residual.numerator),
                            "denominator": str(station_residual.denominator),
                        },
                        "continuous_contact_multiplicity_certified": False,
                    }
                )
                for sample in (station_lo, station_hi):
                    if sample[0] != points[-1][0][0]:
                        points.append(
                            (
                                sample,
                                phase + _increment(float(sample[1]), float(left[1])),
                            )
                        )
            points.append((right, right_phase))
            for (a, ap), (b, bp) in zip(points, points[1:]):
                if min(ap, bp) <= target <= max(ap, bp) and ap != bp:
                    event = crossing(a, ap, b, bp)
                    # Two distinct crossings can share a NONZERO station
                    # endpoint. Only the identical observed zero is duplicate.
                    duplicate_zero = (
                        contacts
                        and event["bracket_width_seconds"] == 0
                        and contacts[-1]["bracket_width_seconds"] == 0
                        and event["jd_tt"] == contacts[-1]["jd_tt"]
                        and event["exact_residual"]["numerator"] == "0"
                        and contacts[-1]["exact_residual"]["numerator"] == "0"
                    )
                    if not duplicate_zero:
                        contacts.append(event)
            left, phase, covered_end = right, right_phase, t
    except CycleUnavailable as exc:
        failure = {"reason": exc.reason, "jd_tt": exc.jd_tt}
    return {
        "body": body,
        "native_body_id": BODIES[body][0],
        "target_arc_degrees": target,
        "birth_jd_tt": birth_tt,
        "natal_longitude": first[1] if first is not None else None,
        "phase_arithmetic_method": PHASE_METHOD,
        "root_method": ROOT_METHOD,
        "station_method": STATION_METHOD,
        "numerical_scope": NUMERICAL_SCOPE,
        "native_return_flag_model": model,
        "body_orbit_source": (
            "swiss_main_asteroid_file"
            if body == "Chiron"
            else "native_planet_ephemeris"
        ),
        "native_flag_scope": (
            "native Earth/correction backend flag; Chiron orbit still requires a Swiss asteroid file"
            if body == "Chiron"
            else "native physical planet backend"
        ),
        "status": (
            "sampled_search_completed"
            if failure is None
            else "partial" if covered_end is not None else "unavailable"
        ),
        "search_start_jd_tt": birth_tt,
        "search_end_jd_tt": end,
        "covered_end_jd_tt": covered_end,
        "failure": failure,
        "contacts": contacts,
        "observed_station_count": len(stations),
        "station_witnesses": stations,
    }
