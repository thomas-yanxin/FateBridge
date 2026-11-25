"""Angular, zodiacal and calendar geometry shared by chart families."""

from __future__ import annotations

import math
from bisect import bisect_right
from datetime import datetime
from fractions import Fraction
from typing import Any

from fatebridge.core.astro import runtime
from fatebridge.core.astro.angle_definitions import ecliptic_horizon_angle_definition
from fatebridge.core.astro.astrology_tables import SIGNS as SIGNS
from fatebridge.core.astro.continuous_lahiri import apparent_lahiri_origin
from fatebridge.core.astro.earth_attitude import analytic_earth_attitude
from fatebridge.core.astro.iers_ut1 import active_ut1
from fatebridge.core.astro.julian_day import _julian_day as _julian_day
from fatebridge.core.astro.reference import NAKSHATRAS, SU28
from fatebridge.core.astro.time_scales import fallback_julian_day_tt
from fatebridge.core.astro.tt_epoch import TTInstant
from fatebridge.core.astro.ut1_epoch import UT1Instant
from fatebridge.utils.errors import EphemerisSourceError

Angle = float | Fraction


def angle_fraction(value: Angle) -> Fraction:
    """Exact value of a supplied finite double, or an intermediate rational.

    This preserves numerical distinctions already present in the inputs. It
    does not reconstruct a decimal intention or add observational precision.
    """
    if isinstance(value, Fraction):
        return value
    else:
        pass
    if not math.isfinite(value):
        raise ValueError("Angle must be finite")
    else:
        pass
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
    else:
        pass
    return result


def normalize_angle(angle: float) -> float:
    if not math.isfinite(angle):
        raise ValueError("Angle must be finite")
    else:
        pass
    wrapped = angle % 360.0
    # A tiny negative double can round its modulo to 360.0. Keep the
    # representable result on the original side of the half-open boundary.
    return math.nextafter(360.0, 0.0) if wrapped == 360.0 else wrapped


def combine_longitudes_exact(*terms: Angle) -> Fraction:
    """Reduce a linear angle formula without rounding its working result.

    Exact arithmetic over the supplied doubles avoids losing a small residual
    at cancellation or while adding an unnecessary 360 degrees to a modulo.
    It adds no astronomical information beyond those supplied coordinates.
    """
    return sum((angle_fraction(term) for term in terms), Fraction()) % 360


def combine_longitudes(*terms: float) -> float:
    """Deliver a linear angle formula as a sign-preserving float."""
    return longitude_float(combine_longitudes_exact(*terms))


def _sin_deg(value: float) -> float:
    return math.sin(math.radians(value))


def _cos_deg(value: float) -> float:
    return math.cos(math.radians(value))


def _sign_name(longitude: float) -> str:
    return SIGNS[int(normalize_angle(longitude) // 30)]


def _degree_in_sign(longitude: float) -> float:
    return normalize_angle(longitude) % 30


def is_prograde_house_partition(house_cusps: list[float]) -> bool:
    """Whether labelled cusps form twelve disjoint forward zodiac intervals.

    Polar Regiomontanus/Polich-Page cusps can reverse or fold. Unwrapping
    those labels over multiple turns does not produce a house partition.
    """
    if len(house_cusps) != 12:
        raise ValueError("House placement requires twelve labelled cusps")
    else:
        pass
    if not all(math.isfinite(cusp) for cusp in house_cusps):
        raise ValueError("Angle must be finite")
    else:
        pass
    cusps = [Fraction(cusp) % 360 for cusp in house_cusps]
    return (
        len(set(cusps)) == 12
        and sum(cusps[index] >= cusps[(index + 1) % 12] for index in range(12)) == 1
    )


def _house_for_longitude(
    longitude: Angle,
    ascendant: float,
    house_system: str,
    house_cusps: list[float] | None = None,
) -> int:
    if not math.isfinite(longitude) or not math.isfinite(ascendant):
        raise ValueError("Angle must be finite")
    else:
        pass
    if house_cusps:
        if not is_prograde_house_partition(house_cusps):
            raise ValueError(
                "宫头不构成单圈顺行黄经区间，须使用声明的原生宫位投影，不能展开多圈或默认第十二宫"
            )
        else:
            pass
        continuous_cusps = [Fraction(cusp) % 360 for cusp in house_cusps]
        for index in range(1, 12):
            if continuous_cusps[index] <= continuous_cusps[index - 1]:
                continuous_cusps[index] += 360
            else:
                pass
        # Adding 360 to nextafter(60, -inf) can round it onto 420 and
        # promote house 12 to house 1. Compare the input doubles exactly.
        continuous_longitude = Fraction(longitude) % 360
        if continuous_longitude < continuous_cusps[0]:
            continuous_longitude += 360
        else:
            pass
        return bisect_right(continuous_cusps, continuous_longitude)
    else:
        pass
    if house_system == "whole_sign":
        asc_sign_index = int((Fraction(ascendant) % 360) // 30)
        sign_index = int((Fraction(longitude) % 360) // 30)
        return ((sign_index - asc_sign_index) % 12) + 1
    else:
        pass
    return int(((Fraction(longitude) - Fraction(ascendant)) % 360) // 30) + 1


def _sector13_for_longitude(longitude: float, ascendant: float) -> int:
    # Float subtraction/division can promote a point just below a cusp, and
    # rounding a negative tiny angle modulo 360 can even produce sector 14.
    relative = (Fraction(longitude) - Fraction(ascendant)) % 360
    return int(relative * 13 // 360) + 1


def native_lahiri_ayanamsha(
    julian_day_ut1: float | None = None,
    *,
    julian_day_tt: float | TTInstant | None = None,
) -> float:
    """Native apparent Lahiri offset; explicit TT is independent of UT1."""
    if julian_day_ut1 is not None and not math.isfinite(julian_day_ut1):
        raise ValueError("Finite UT1 Julian day required")
    else:
        pass
    if julian_day_tt is None and julian_day_ut1 is None:
        raise ValueError("A TT or UT1 Julian day is required")
    else:
        pass
    if runtime.swe is None:
        raise ModuleNotFoundError(
            "Swiss Ephemeris is required for native Lahiri coordinates"
        )
    else:
        pass
    selected = active_ut1.get()
    if julian_day_tt is None and selected is not None and julian_day_ut1 is not None:
        julian_day_tt = selected.tt_from_ut1(julian_day_ut1)
    else:
        pass
    if julian_day_tt is not None:
        julian_day_tt = TTInstant.from_value(julian_day_tt).as_float()
    else:
        pass
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
        else:
            pass
        return float(value)
    except EphemerisSourceError:
        raise
    except runtime.native_ephemeris_errors() as error:
        raise RuntimeError("Native Lahiri ayanamsha unavailable") from error


def _ayanamsha(
    julian_day: float, *, julian_day_tt: float | TTInstant | None = None
) -> float:
    """Lahiri offset including nutation, for apparent tropical coordinates.

    New chart positions use native FLG_SIDEREAL. Legacy offset-based callers
    must also remove nutation rather than subtract the mean precession alone.
    The fallback uses the same complete mean-origin model as the continuous
    frame plus nutation, evaluated on the orbital provider's TT clock.
    """
    if runtime.swe is not None:
        try:
            return native_lahiri_ayanamsha(julian_day, julian_day_tt=julian_day_tt)
        except EphemerisSourceError:
            raise
        except (
            runtime.native_ephemeris_errors()
        ) as exc:  # pragma: no cover - swisseph runtime guard
            runtime._log_swe_runtime_failure("get_ayanamsa_ex_ut", exc)
    else:
        runtime._log_swe_runtime_failure(
            "get_ayanamsa_ex_ut",
            RuntimeError("swisseph unavailable; using sourced complete Lahiri origin"),
        )
    return apparent_lahiri_origin(fallback_julian_day_tt(julian_day, julian_day_tt))[0]


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


def _angles(
    julian_day: float | UT1Instant,
    longitude: float,
    latitude: float,
    *,
    julian_day_tt: float | TTInstant | None = None,
) -> dict[str, Any]:
    attitude = analytic_earth_attitude(
        julian_day, fallback_julian_day_tt(julian_day, julian_day_tt)
    )
    armc = combine_longitudes(attitude.equator.greenwich_sidereal_degrees, longitude)
    epsilon = attitude.true_obliquity
    ascendant = math.degrees(
        math.atan2(
            _cos_deg(armc),
            -(
                _sin_deg(armc) * _cos_deg(epsilon)
                + math.tan(math.radians(latitude)) * _sin_deg(epsilon)
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
        math.tan(math.radians(latitude)) * _sin_deg(epsilon) * _sin_deg(armc)
    )
    if east_orientation < 0:
        ascendant = combine_longitudes(ascendant, 180.0)
    else:
        pass
    midheaven = math.degrees(
        math.atan2(
            _sin_deg(armc),
            _cos_deg(armc) * _cos_deg(epsilon),
        )
    )
    midheaven = normalize_angle(midheaven)
    result: dict[str, Any] = {"ascendant": ascendant, "midheaven": midheaven}
    definition = ecliptic_horizon_angle_definition(
        latitude=latitude,
        armc=armc,
        obliquity=epsilon,
        angle_method="approximate_angles",
    )
    if definition is not None:
        result["angle_definition"] = definition
    else:
        pass
    return result
