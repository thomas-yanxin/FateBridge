"""Source-derived analytic Sun, with no downloaded ephemeris or oracle inputs.

Adapted from ERFA 2.0.1, derived from SOFA, copyright NumFOCUS Foundation.
See data/astronomy/erfa-license.txt. Neither organization endorses FateBridge.
Earth: simplified VSOP2000 epv00; frame: IAU2006/P03 + IAU2000B nutation.
TT substitutes for TDB as permitted by epv00 note1; this approximation remains
explicit. The author comparison range is1900..2100, not every software epoch.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any, Dict, Sequence, Tuple

from fatebridge.utils.errors import EphemerisSourceError

Vector = Tuple[float, float, float]
State = Tuple[Vector, Vector]
AS2R = math.pi / (180 * 3600)
C_AU_DAY = 299792458.0 * 86400 / 149597870700.0
MODEL_ID = "fatebridge_analytic_solar_v1"
# Reviewed ERFA2.0.1 extraction, including its source and author-scope metadata.
# Updating the named source requires a fresh source review, not a new file hash
# copied from whatever coefficients happen to be installed.
PROFILE_CONTENT_SHA256 = (
    "138972a929da1ef7ac41921ec80f69149b36cda6fae364e90d3bd21b44625873"
)


def _unique_object(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate analytic coefficient key")
        result[key] = value
    return result


@lru_cache(maxsize=1)
def _profile_data() -> Dict[str, Any]:
    try:
        raw = (
            files("fatebridge")
            .joinpath("data/astronomy/analytic-solar-v1.json")
            .read_bytes()
        )
        data: Dict[str, Any] = json.loads(raw, object_pairs_hook=_unique_object)
        content = json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        if hashlib.sha256(content).hexdigest() != PROFILE_CONTENT_SHA256:
            raise ValueError("Unreviewed analytic solar coefficient content")
    except (OSError, ValueError, TypeError) as error:
        raise EphemerisSourceError("solar_analytic_invalid") from error
    data["loaded_sha256"] = hashlib.sha256(raw).hexdigest()
    return data


def profile() -> Dict[str, Any]:
    """Return a detached source view; callers cannot rewrite loaded mathematics."""
    return deepcopy(_profile_data())


# Preserve the existing explicit cache controls, without caching a public view.
profile.cache_clear = _profile_data.cache_clear  # type: ignore[attr-defined]
profile.cache_info = _profile_data.cache_info  # type: ignore[attr-defined]
profile.cache_parameters = _profile_data.cache_parameters  # type: ignore[attr-defined]


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


def earth_state(date1: float, date2: float = 0.0) -> Tuple[State, State]:
    """Heliocentric and barycentric BCRS state, AU and AU/day."""
    t = _epoch(date1, date2, 365.25)
    helio, sun = _series("e", t), _series("s", t)
    position = tuple(a + b for a, b in zip(helio[0], sun[0]))
    velocity = tuple(a + b for a, b in zip(helio[1], sun[1]))
    return helio, (
        (position[0], position[1], position[2]),
        (velocity[0], velocity[1], velocity[2]),
    )


def nutation(date1: float, date2: float = 0.0) -> Tuple[float, float]:
    t = _epoch(date1, date2, 36525.0)
    arguments = [
        math.fmod(a + b * t, 1296000) * AS2R
        for a, b in [
            (485868.249036, 1717915923.2178),
            (1287104.79305, 129596581.0481),
            (335779.526232, 1739527262.8478),
            (1072260.70369, 1602961601.2090),
            (450160.398036, -6962890.5431),
        ]
    ]
    dp = de = 0.0
    for row in reversed(_profile_data()["nut00b"]):
        angle = math.fmod(
            math.fsum(a * b for a, b in zip(row[:5], arguments)), 2 * math.pi
        )
        si, co = math.sin(angle), math.cos(angle)
        ps, pst, pc, ec, ect, es = row[5:]
        dp += (ps + pst * t) * si + pc * co
        de += (ec + ect * t) * co + es * si
    return dp * AS2R / 1e7 - 0.000135 * AS2R, de * AS2R / 1e7 + 0.000388 * AS2R


def _polynomial(t: float, coefficients: Sequence[float]) -> float:
    value = 0.0
    for coefficient in reversed(coefficients):
        value = value * t + coefficient
    return value * AS2R


def precession_angles(date1: float, date2: float = 0.0) -> Tuple[float, ...]:
    t = _epoch(date1, date2, 36525.0)
    return tuple(
        _polynomial(t, coefficients)
        for coefficients in [
            [-0.052928, 10.556378, 0.4932044, -0.00031238, -0.000002788, 0.0000000260],
            [
                84381.412819,
                -46.811016,
                0.0511268,
                0.00053289,
                -0.000000440,
                -0.0000000176,
            ],
            [
                -0.041775,
                5038.481484,
                1.5584175,
                -0.00018522,
                -0.000026452,
                -0.0000000148,
            ],
            [
                84381.406,
                -46.836769,
                -0.0001831,
                0.00200340,
                -0.000000576,
                -0.0000000434,
            ],
        ]
    )


def _rotate(vector: Vector, axis: str, angle: float) -> Vector:
    x, y, z = vector
    co, si = math.cos(angle), math.sin(angle)
    if axis == "x":
        return x, co * y + si * z, -si * y + co * z
    return co * x + si * y, -si * x + co * y, z


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
        vector = _rotate(vector, axis, angle)
    return vector


def aberration(natural: Vector, velocity_c: Vector, sun_distance: float) -> Vector:
    """ERFA ab: annual aberration and solar-potential term; no fitted offset."""
    dot = math.fsum(a * b for a, b in zip(natural, velocity_c))
    bm1 = math.sqrt(1 - math.fsum(v * v for v in velocity_c))
    w1, w2 = 1 + dot / (1 + bm1), 1.97412574336e-8 / sun_distance
    result = tuple(
        p * bm1 + w1 * v + w2 * (v - dot * p) for p, v in zip(natural, velocity_c)
    )
    norm = math.sqrt(math.fsum(v * v for v in result))
    return result[0] / norm, result[1] / norm, result[2] / norm


def solar_longitude(jd_tt: float) -> float:
    """Apparent geocentric solar longitude, degrees, with TT-for-TDB policy."""
    t = _epoch(jd_tt, 0.0, 365.25)
    helio, bary = earth_state(jd_tt)
    earth = bary[0]
    sun = _series("s", t)[0]
    vector = tuple(s - e for s, e in zip(sun, earth))
    for _ in range(3):
        delay = math.sqrt(math.fsum(v * v for v in vector)) / C_AU_DAY
        sun = _series("s", ((jd_tt - 2451545.0) - delay) / 365.25)[0]
        vector = tuple(s - e for s, e in zip(sun, earth))
    distance = math.sqrt(math.fsum(v * v for v in vector))
    natural = (vector[0] / distance, vector[1] / distance, vector[2] / distance)
    velocity = tuple(v / C_AU_DAY for v in bary[1])
    apparent = aberration(
        natural,
        (velocity[0], velocity[1], velocity[2]),
        math.sqrt(math.fsum(v * v for v in helio[0])),
    )
    ecliptic = apparent_ecliptic(apparent, jd_tt)
    return math.degrees(math.atan2(ecliptic[1], ecliptic[0])) % 360


def model_details(jd_tt: float) -> Dict[str, Any]:
    t = _epoch(jd_tt, 0.0, 365.25)
    data = _profile_data()
    return {
        "model_id": MODEL_ID,
        "version": data["version"],
        "coefficient_sha256": data["loaded_sha256"],
        "source_commit": data["source"]["commit"],
        "author_validation_range": "1900-2100 (abs Julian years from J2000 <=100)",
        "outside_author_validation_range": abs(t) > 100,
        "time_argument": "TT substituted for TDB per ERFA epv00 note1",
        "position_frame": "BCRS then IAU2006/P03 and IAU2000B true ecliptic of date",
        "light_time_iterations": 3,
        "native_moshier_relabelled": False,
        "accuracy_certified": False,
        "source_url": data["source"]["files"]["epv00.c"]["url"],
    }


def longitude_crossing_tt(target: float, low: float, high: float) -> Dict[str, Any]:
    """Bracketed TT crossing, independent of all benchmark crossing times.

    Forty bisections are capped by the representable JD grid; the bracket is
    a numerical receipt only. It does not establish physical timing accuracy.
    """
    if not all(math.isfinite(x) for x in (target, low, high)) or low >= high:
        raise ValueError("Solar crossing requires a finite increasing TT bracket")

    def residual(epoch: float) -> float:
        return math.remainder(solar_longitude(epoch) - target, 360)

    flo, fhi = residual(low), residual(high)
    if not flo < 0 <= fhi or fhi - flo >= 90:
        raise ValueError("TT bracket does not contain a forward solar crossing")
    iterations = 0
    for _ in range(40):
        middle = (low + high) / 2
        if middle == low or middle == high:
            break
        if residual(middle) < 0:
            low = middle
        else:
            high = middle
        iterations += 1
    return {
        "jd_tt": (low + high) / 2,
        "bracket_tt": [low, high],
        "bracket_seconds": (high - low) * 86400,
        "iterations": iterations,
        "numerical_resolution_is_physical_accuracy": False,
        "model": model_details((low + high) / 2),
    }
