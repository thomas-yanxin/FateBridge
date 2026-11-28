"""Source-derived analytic Sun, with no downloaded ephemeris or oracle inputs.

Adapted from ERFA 2.0.1, derived from SOFA, copyright NumFOCUS Foundation.
See data/astronomy/erfa-license.txt. Neither organization endorses FateBridge.
Earth: simplified VSOP2000 epv00; frame: IAU2006/P03 + IAU2000B nutation.
TT substitutes for TDB as permitted by epv00 note1; this approximation remains
explicit. The author comparison range is1900..2100, not every software epoch.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from copy import deepcopy
from functools import lru_cache
from typing import Any

from fatebridge.core.astro.cartesian import dot
from fatebridge.core.astro.reference_frames import precession_angles, rotate
from fatebridge.core.native_solar_loader import (
    bisect_forward_crossing,
    load_astronomy_json,
    validate_crossing_inputs,
    validate_forward_bracket,
)
from fatebridge.utils.errors import EphemerisSourceError

Vector = tuple[float, float, float]
State = tuple[Vector, Vector]
AS2R = math.pi / (180 * 3600)
C_AU_DAY = 299792458.0 * 86400 / 149597870700.0
MODEL_ID = "fatebridge_analytic_solar_v1"


@lru_cache(maxsize=1)
def _profile_data() -> dict[str, Any]:
    try:
        return load_astronomy_json("analytic-solar-v1.json", label="analytic key")
    except (OSError, ValueError, TypeError) as error:
        raise EphemerisSourceError("solar_analytic_invalid") from error


class _ProfileAccessor:
    """Typed callable accessor exposing cache controls without dynamic attributes."""

    def __call__(self) -> dict[str, Any]:
        """Return a detached source view; callers cannot rewrite loaded mathematics."""
        return deepcopy(_profile_data())

    @property
    def cache_clear(self) -> Any:
        return _profile_data.cache_clear

    @property
    def cache_info(self) -> Any:
        return _profile_data.cache_info

    @property
    def cache_parameters(self) -> Any:
        return _profile_data.cache_parameters


profile = _ProfileAccessor()


def _epoch(date1: float, date2: float, scale: float) -> float:
    if not math.isfinite(date1) or not math.isfinite(date2):
        raise ValueError("Analytic solar epoch must be finite")
    return ((date1 - 2451545.0) + date2) / scale


def _orientation(vector: Sequence[float]) -> Vector:
    a = _profile_data()["orientation"]
    x, y, z = vector
    return (
        x + a["am12"] * y + a["am13"] * z,
        a["am21"] * x + a["am22"] * y + a["am23"] * z,
        a["am32"] * y + a["am33"] * z,
    )


def _series(kind: str, t: float) -> State:
    coefficients = _profile_data()["epv00"]
    positions, velocities = [], []
    for axis in "xyz":
        position = velocity = 0.0
        for power in range(3):
            for amplitude, phase, frequency in coefficients[f"{kind}{power}{axis}"]:
                angle = phase + frequency * t
                co, si = math.cos(angle), math.sin(angle)
                position += amplitude * t**power * co
                velocity += amplitude * (
                    (power * t ** (power - 1) * co if power else 0)
                    - t**power * frequency * si
                )
        positions.append(position)
        velocities.append(velocity / 365.25)
    return _orientation(positions), _orientation(velocities)


def earth_state(date1: float, date2: float = 0.0) -> tuple[State, State]:
    """Heliocentric and barycentric BCRS state, AU and AU/day."""
    t = _epoch(date1, date2, 365.25)
    helio, sun = _series("e", t), _series("s", t)
    position = tuple(a + b for a, b in zip(helio[0], sun[0]))
    velocity = tuple(a + b for a, b in zip(helio[1], sun[1]))
    return helio, (
        (position[0], position[1], position[2]),
        (velocity[0], velocity[1], velocity[2]),
    )


@lru_cache(maxsize=1)
def _nut00b_rows() -> tuple[tuple[float, ...], ...]:
    return tuple(
        tuple(float(v) for v in row) for row in reversed(_profile_data()["nut00b"])
    )


def nutation(date1: float, date2: float = 0.0) -> tuple[float, float]:
    t = _epoch(date1, date2, 36525.0)
    a0 = math.fmod(485868.249036 + 1717915923.2178 * t, 1296000.0) * AS2R
    a1 = math.fmod(1287104.79305 + 129596581.0481 * t, 1296000.0) * AS2R
    a2 = math.fmod(335779.526232 + 1739527262.8478 * t, 1296000.0) * AS2R
    a3 = math.fmod(1072260.70369 + 1602961601.2090 * t, 1296000.0) * AS2R
    a4 = math.fmod(450160.398036 - 6962890.5431 * t, 1296000.0) * AS2R
    two_pi = 2.0 * math.pi
    sin, cos, fmod = math.sin, math.cos, math.fmod
    dp = de = 0.0
    for n0, n1, n2, n3, n4, ps, pst, pc, ec, ect, es in _nut00b_rows():
        angle = fmod(n0 * a0 + n1 * a1 + n2 * a2 + n3 * a3 + n4 * a4, two_pi)
        si, co = sin(angle), cos(angle)
        dp += (ps + pst * t) * si + pc * co
        de += (ec + ect * t) * co + es * si
    return dp * AS2R / 1e7 - 0.000135 * AS2R, de * AS2R / 1e7 + 0.000388 * AS2R


def apparent_ecliptic(vector: Vector, date1: float, date2: float = 0.0) -> Vector:
    """BCRS/ICRS vector to true ecliptic/equinox of date (radians internally)."""
    gamma, phi, psi, epsilon = precession_angles(date1, date2)
    dpsi, deps = nutation(date1, date2)
    for axis, angle in [
        ("z", gamma),
        ("x", phi),
        ("z", -psi - dpsi),
        ("x", -epsilon - deps),
        ("x", epsilon + deps),
    ]:
        vector = rotate(vector, axis, angle)
    return vector


def aberration(natural: Vector, velocity_c: Vector, sun_distance: float) -> Vector:
    """ERFA ab: annual aberration and solar-potential term; no fitted offset."""
    projection = dot(natural, velocity_c)
    bm1 = math.sqrt(1 - dot(velocity_c, velocity_c))
    w1, w2 = 1 + projection / (1 + bm1), 1.97412574336e-8 / sun_distance
    result = tuple(
        p * bm1 + w1 * v + w2 * (v - projection * p)
        for p, v in zip(natural, velocity_c)
    )
    norm = math.sqrt(dot(result, result))
    return result[0] / norm, result[1] / norm, result[2] / norm


def solar_longitude(jd_tt: float) -> float:
    """Apparent geocentric solar longitude, degrees, with TT-for-TDB policy."""
    t = _epoch(jd_tt, 0.0, 365.25)
    helio, bary = earth_state(jd_tt)
    earth = bary[0]
    sun = _series("s", t)[0]
    vector = tuple(s - e for s, e in zip(sun, earth))
    for _ in range(3):
        delay = math.sqrt(dot(vector, vector)) / C_AU_DAY
        sun = _series("s", ((jd_tt - 2451545.0) - delay) / 365.25)[0]
        vector = tuple(s - e for s, e in zip(sun, earth))
    distance = math.sqrt(dot(vector, vector))
    natural = (vector[0] / distance, vector[1] / distance, vector[2] / distance)
    velocity = tuple(v / C_AU_DAY for v in bary[1])
    apparent = aberration(
        natural,
        (velocity[0], velocity[1], velocity[2]),
        math.sqrt(dot(helio[0], helio[0])),
    )
    ecliptic = apparent_ecliptic(apparent, jd_tt)
    return math.degrees(math.atan2(ecliptic[1], ecliptic[0])) % 360


def model_details(jd_tt: float) -> dict[str, Any]:
    t = _epoch(jd_tt, 0.0, 365.25)
    data = _profile_data()
    return {
        "model_id": MODEL_ID,
        "version": data["version"],
        "source_commit": data["source"]["commit"],
        "author_validation_range": "1900-2100 (abs Julian years from J2000 <=100)",
        "outside_author_validation_range": abs(t) > 100,
        "time_argument": "TT substituted for TDB per ERFA epv00 note1",
        "position_frame": "BCRS then IAU2006/P03 and IAU2000B true ecliptic of date",
        "light_time_iterations": 3,
        "native_moshier_relabelled": False,
        "accuracy_certified": False,
    }


def longitude_crossing_tt(target: float, low: float, high: float) -> dict[str, Any]:
    """Bracketed TT crossing, independent of all benchmark crossing times.

    Forty bisections are capped by the representable JD grid; the bracket is
    a numerical receipt only. It does not establish physical timing accuracy.
    """
    validate_crossing_inputs(
        target,
        low,
        high,
        message="Solar crossing requires a finite increasing TT bracket",
    )

    def residual(epoch: float) -> float:
        return math.remainder(solar_longitude(epoch) - target, 360)

    flo, fhi = residual(low), residual(high)
    validate_forward_bracket(
        flo,
        fhi,
        message="TT bracket does not contain a forward solar crossing",
    )
    low, high, iterations = bisect_forward_crossing(residual, low, high, 40)
    return {
        "jd_tt": (low + high) / 2,
        "bracket_tt": [low, high],
        "bracket_seconds": (high - low) * 86400,
        "iterations": iterations,
        "numerical_resolution_is_physical_accuracy": False,
        "model": model_details((low + high) / 2),
    }
