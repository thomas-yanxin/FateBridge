"""Angular, zodiacal and calendar geometry shared by chart families."""

from __future__ import annotations

import math
from datetime import datetime
from fractions import Fraction
from typing import Any, Dict, List, Optional, Union

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import ecliptic_horizon_angle_definition
from fatebridge.core.astro.julian_day import _julian_day as _julian_day
from fatebridge.core.astro.reference import NAKSHATRAS, SU28
from fatebridge.core.astrology_tables import SIGNS as SIGNS
from fatebridge.utils.errors import EphemerisSourceError

Angle = Union[float, Fraction]


def angle_fraction(value: Angle) -> Fraction:
    """Exact value of a supplied finite double, or an intermediate rational.

    This preserves numerical distinctions already present in the inputs. It
    does not reconstruct a decimal intention or add observational precision.
    """
    if isinstance(value, Fraction):
        return value
    if not math.isfinite(value):
        raise ValueError("Angle must be finite")
    return Fraction(value)


def angular_separation_fraction(first: Angle, second: Angle) -> Fraction:
    """Unsigned circular separation, before any rounding for delivery."""
    difference = (angle_fraction(first) - angle_fraction(second)) % 360
    return min(difference, 360 - difference)


def longitude_float(value: Fraction) -> float:
    """Nearest float on the same side of a 30/360-degree partition."""
    reduced = value % 360
    result = float(reduced)
    if result // 30 != reduced // 30:
        result = math.nextafter(result, -math.inf)
    return result


def normalize_angle(angle: float) -> float:
    if not math.isfinite(angle):
        raise ValueError("Angle must be finite")
    wrapped = angle % 360.0
    # A tiny negative double can round its modulo to 360.0. Keep the
    # representable result on the original side of the half-open boundary.
    return math.nextafter(360.0, 0.0) if wrapped == 360.0 else wrapped


def combine_longitudes(*terms: float) -> float:
    """Reduce a linear angle formula before rounding its float result.

    Exact arithmetic over the supplied doubles avoids losing a small residual
    at cancellation or while adding an unnecessary 360 degrees to a modulo.
    It adds no astronomical information beyond those supplied coordinates.
    """
    reduced = sum((angle_fraction(term) for term in terms), Fraction()) % 360
    return longitude_float(reduced)


def _deg_to_rad(value: float) -> float:
    return math.radians(value)


def _rad_to_deg(value: float) -> float:
    return math.degrees(value)


def _sin_deg(value: float) -> float:
    return math.sin(_deg_to_rad(value))


def _cos_deg(value: float) -> float:
    return math.cos(_deg_to_rad(value))


def _sign_name(longitude: float) -> str:
    return SIGNS[int(normalize_angle(longitude) // 30)]


def _degree_in_sign(longitude: float) -> float:
    return normalize_angle(longitude) % 30


def _continuous_house_cusps(house_cusps: List[float]) -> List[Fraction]:
    continuous: List[Fraction] = []
    for cusp in house_cusps:
        if not math.isfinite(cusp):
            raise ValueError("Angle must be finite")
        normalized = Fraction(cusp) % 360
        if continuous:
            while normalized <= continuous[-1]:
                normalized += 360
        continuous.append(normalized)
    return continuous


def is_prograde_house_partition(house_cusps: List[float]) -> bool:
    """Whether labelled cusps form twelve disjoint forward zodiac intervals.

    Polar Regiomontanus/Polich-Page cusps can reverse or fold. Unwrapping
    those labels over multiple turns does not produce a house partition.
    """
    if len(house_cusps) != 12:
        raise ValueError("House placement requires twelve labelled cusps")
    if not all(math.isfinite(cusp) for cusp in house_cusps):
        raise ValueError("Angle must be finite")
    cusps = [Fraction(cusp) % 360 for cusp in house_cusps]
    return (
        len(set(cusps)) == 12
        and sum(cusps[index] >= cusps[(index + 1) % 12] for index in range(12)) == 1
    )


def _house_for_longitude(
    longitude: Angle,
    ascendant: float,
    house_system: str,
    house_cusps: Optional[List[float]] = None,
) -> int:
    if not math.isfinite(longitude) or not math.isfinite(ascendant):
        raise ValueError("Angle must be finite")
    if house_cusps:
        if not is_prograde_house_partition(house_cusps):
            raise ValueError(
                "宫头不构成单圈顺行黄经区间，须使用声明的原生宫位投影，不能展开多圈或默认第十二宫"
            )
        continuous_cusps = _continuous_house_cusps(house_cusps)
        cycle_end = continuous_cusps[0] + 360
        # Adding 360 to nextafter(60, -inf) can round it onto 420 and
        # promote house 12 to house 1. Compare the input doubles exactly.
        continuous_longitude = Fraction(longitude) % 360
        while continuous_longitude < continuous_cusps[0]:
            continuous_longitude += 360
        while continuous_longitude >= cycle_end:
            continuous_longitude -= 360
        for index, start in enumerate(continuous_cusps):
            end = (
                continuous_cusps[index + 1]
                if index < len(continuous_cusps) - 1
                else cycle_end
            )
            if start <= continuous_longitude < end:
                return index + 1
        return 12
    if house_system == "whole_sign":
        asc_sign_index = int((Fraction(ascendant) % 360) // 30)
        sign_index = int((Fraction(longitude) % 360) // 30)
        return ((sign_index - asc_sign_index) % 12) + 1
    return int(((Fraction(longitude) - Fraction(ascendant)) % 360) // 30) + 1


def _sector13_for_longitude(longitude: float, ascendant: float) -> int:
    # Float subtraction/division can promote a point just below a cusp, and
    # rounding a negative tiny angle modulo 360 can even produce sector 14.
    relative = (Fraction(longitude) - Fraction(ascendant)) % 360
    return int(relative * 13 // 360) + 1


def native_lahiri_ayanamsha(
    julian_day_ut1: float | None = None, *, julian_day_tt: float | None = None
) -> float:
    """Native apparent Lahiri offset; explicit TT is independent of UT1."""
    if julian_day_ut1 is not None and not math.isfinite(julian_day_ut1):
        raise ValueError("Finite UT1 Julian day required")
    if julian_day_tt is None and julian_day_ut1 is None:
        raise ValueError("A TT or UT1 Julian day is required")
    if runtime.swe is None:
        raise ImportError("Swiss Ephemeris is required for native Lahiri coordinates")
    from fatebridge.core.astro.iers_ut1 import active_ut1

    selected = active_ut1.get()
    if julian_day_tt is None and selected is not None and julian_day_ut1 is not None:
        julian_day_tt = selected.tt_from_ut1(julian_day_ut1)
    if julian_day_tt is not None and not math.isfinite(julian_day_tt):
        raise ValueError("Finite TT Julian day required")
    try:
        with runtime.preserve_ephemeris_path():
            runtime.swe.set_sid_mode(runtime.swe.SIDM_LAHIRI, 0, 0)
            flags, value = (
                runtime.ephemeris_call(
                    "get_ayanamsa_ex", julian_day_tt, runtime.swe.FLG_SWIEPH
                )
                if julian_day_tt is not None
                else runtime.ephemeris_call(
                    "get_ayanamsa_ex_ut", julian_day_ut1, runtime.swe.FLG_SWIEPH
                )
            )
        if flags < 0 or not math.isfinite(value):
            raise RuntimeError("Native Lahiri ayanamsha unavailable")
        return float(value)
    except EphemerisSourceError:
        raise
    except Exception as error:
        raise RuntimeError("Native Lahiri ayanamsha unavailable") from error


def _ayanamsha(julian_day: float) -> float:
    """Lahiri offset including nutation, for apparent tropical coordinates.

    New chart positions use native FLG_SIDEREAL. Legacy offset-based callers
    must also remove nutation rather than subtract the mean precession alone.
    The linear fallback is only a mean-offset approximation, logged explicitly;
    it carries no full-epoch astronomical accuracy guarantee.
    """
    if runtime.swe is not None:
        try:
            return native_lahiri_ayanamsha(julian_day)
        except EphemerisSourceError:
            raise
        except Exception as exc:  # pragma: no cover - swisseph runtime guard
            runtime._log_swe_runtime_failure("get_ayanamsa_ex_ut", exc)
    else:
        runtime._log_swe_runtime_failure(
            "get_ayanamsa_ex_ut",
            RuntimeError("swisseph unavailable; using linear ayanamsha approximation"),
        )
    # Lahiri-like ayanamsha: base value at J2000.0 plus precession drift.
    # J2000 baseline ≈ 23.853°, precession ≈ 50.29"/yr ≈ 1.3971°/Julian century.
    centuries_since_j2000 = (julian_day - 2451545.0) / 36525.0
    return 23.853 + centuries_since_j2000 * 1.3971


def _nakshatra(longitude: float) -> str:
    index = int((angle_fraction(longitude) % 360) * 27 // 360)
    return NAKSHATRAS[index]


def _su28(longitude: float) -> str:
    index = int((angle_fraction(longitude) % 360) * 28 // 360)
    return SU28[index]


def _week_ruler(target: datetime) -> str:
    weekday_index = target.weekday()
    return [
        "Moon",
        "Mars",
        "Mercury",
        "Jupiter",
        "Venus",
        "Saturn",
        "Sun",
    ][weekday_index]


def _gmst(julian_day: float) -> float:
    t = (julian_day - 2451545.0) / 36525.0
    return normalize_angle(
        280.46061837
        + 360.98564736629 * (julian_day - 2451545.0)
        + 0.000387933 * t * t
        - (t * t * t) / 38710000.0
    )


def _angles(julian_day: float, longitude: float, latitude: float) -> Dict[str, Any]:
    armc = normalize_angle(_gmst(julian_day) + longitude)
    epsilon = 23.439291 - 0.0130042 * ((julian_day - 2451545.0) / 36525.0)
    ascendant = _rad_to_deg(
        math.atan2(
            _cos_deg(armc),
            -(
                _sin_deg(armc) * _cos_deg(epsilon)
                + math.tan(_deg_to_rad(latitude)) * _sin_deg(epsilon)
            ),
        )
    )
    ascendant = normalize_angle(ascendant)
    # atan2 selects one of two antipodal horizon/ecliptic intersections. In
    # polar regions that branch can lie west of the supplied meridian. The
    # east projection of that candidate has the sign of this expression
    # (cos(latitude) is non-negative in the geographic latitude domain).
    # Select the eastern intersection, as in Swiss Ephemeris §6.4. This is a
    # geometric convention; at a geographic pole it is not a daily rising.
    east_orientation = _cos_deg(epsilon) + (
        math.tan(_deg_to_rad(latitude)) * _sin_deg(epsilon) * _sin_deg(armc)
    )
    if east_orientation < 0:
        ascendant = combine_longitudes(ascendant, 180.0)
    midheaven = _rad_to_deg(
        math.atan2(
            _sin_deg(armc),
            _cos_deg(armc) * _cos_deg(epsilon),
        )
    )
    midheaven = normalize_angle(midheaven)
    result: Dict[str, Any] = {"ascendant": ascendant, "midheaven": midheaven}
    definition = ecliptic_horizon_angle_definition(
        latitude=latitude,
        armc=armc,
        obliquity=epsilon,
        angle_method="approximate_angles",
    )
    if definition is not None:
        result["angle_definition"] = definition
    return result
