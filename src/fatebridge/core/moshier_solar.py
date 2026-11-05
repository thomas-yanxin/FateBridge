"""Complete Moshier Sun: December 1996 EMB, full Moon, IAU date frame.

The Earth series is evaluated with its analytic derivative. The public native
Moon calculation supplies the complete geometric lunar series, rather than
Swiss embofs_mosh's short lunar series. No reference crossings or fitted offsets
are used. This is a named FateBridge revision, not stock Swiss Moshier.
"""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from importlib.resources import files
from typing import Sequence, TypedDict

from fatebridge.core import ephemeris_runtime as native
from fatebridge.core.analytic_solar import (
    AS2R,
    C_AU_DAY,
    Vector,
    aberration,
    apparent_ecliptic,
)
from fatebridge.core.analytic_solar import model_details as analytic_frame_details
from fatebridge.utils.errors import EphemerisSourceError

MODEL_ID = "fatebridge_complete_moshier_solar_v1"
PROVIDER = "fatebridge_moshier"
# AA 2006 K7, also the active Swiss 2.10.03 mass ratio. It is a physical
# constant of the reduction, not a value estimated from crossing residuals.
MOON_MASS_FRACTION = 1 / (1 / 0.0123000383 + 1)


class EarthTable(TypedDict):
    model_id: str
    source_url: str
    source_archive_sha256: str
    source_file: str
    source_file_sha256: str
    author: str
    version: str
    distance_au: float
    timescale_days: float
    amplitude_scale: float
    obliquity_j2000_arcseconds: float
    author_peak_longitude_error_arcseconds_1500_2500: float
    tabl: list[int]
    tabb: list[int]
    tabr: list[int]
    args: list[int]


# Simon et al. (1994), with the DE403-origin adjustment used by the author's
# AA5.6 gplan.c mean_elements. Constant-first, in arcseconds / Julian century.
# Index 8 is unused by ear404; indices 9..11 are D, F and the solar anomaly.
MEAN_ELEMENTS = (
    (908103.213, 538101628.6889819, -0.0192789, 6.39e-6),
    (655127.236, 210664136.4335482, 0.0059381, -6.27e-6),
    (361679.198, 129597742.283429, -0.0204411, -5.23e-6),
    (1279558.751, 68905077.493988, 0.0094264, -1.043e-5),
    (123665.420, 10925660.377991, -0.3060378, 5.706e-5, 4.667e-6, 5.91e-8, -3.4e-10),
    (180278.752, 4399609.855372, 0.7561614, -1.6618e-4, -1.1484e-5, -1.452e-7, 8.3e-10),
    (1130597.971, 1542481.193933, -0.0175083, 0.00002156),
    (1095655.149, 786550.320744, 0.0021103, -0.00000895),
    (0.0,),
    (
        1072261.2202445078,
        1602961600.9939659,
        -6.7352202374457519,
        0.0069492746836058421,
        -3.702060118571e-5,
        2.560078201452e-9,
        2.555243317839e-11,
        -3.207663637426e-13,
    ),
    (
        335779.5141288474,
        1739527262.8437717,
        -13.117809789650071,
        -0.00075311878482337989,
        -2.165750777942e-6,
        -2.790392351314e-9,
        4.189032191814e-11,
        4.474984866301e-13,
    ),
    (
        1287102.7407441526,
        129596581.0230432,
        -0.55281306421783094,
        0.000087473717367324703,
        -0.000011297037031,
        -4.77258489e-8,
        8.8555011e-11,
        4.237343e-13,
        -3.83508e-15,
        -1.0390e-17,
        1.62e-20,
    ),
)

Term = tuple[list[tuple[int, int]], list[list[int]]]


@lru_cache(maxsize=1)
def _table() -> tuple[EarthTable, list[Term], str]:
    raw = (
        files("fatebridge")
        .joinpath("data/astronomy/moshier-earth-1996.json")
        .read_bytes()
    )
    data: EarthTable = json.loads(raw)
    arguments = iter(data["args"])
    axes = [iter(data[key]) for key in ("tabl", "tabb", "tabr")]
    terms = []
    for count in arguments:
        if count < 0:
            break
        harmonics = [(next(arguments), next(arguments) - 1) for _ in range(count)]
        degree = next(arguments)
        width = (degree + 1) * (2 if count else 1)
        coefficients = [[next(axis) for _ in range(width)] for axis in axes]
        terms.append((harmonics, coefficients))
    return data, terms, hashlib.sha256(raw).hexdigest()


def _polynomial(coefficients: Sequence[float], t: float) -> tuple[float, float]:
    value = derivative = 0.0
    for coefficient in reversed(coefficients):
        derivative = derivative * t + value
        value = value * t + coefficient
    return value, derivative


def earth_moon_barycenter(jd_tt: float) -> tuple[Vector, Vector]:
    """Heliocentric J2000-equatorial position/velocity, AU and AU/TT day.

    This follows the author's g3plan definition with analytic differentiation
    of every polynomial and trigonometric term, including lunar arguments.
    """
    table, terms, _ = _table()
    century = (jd_tt - 2451545.0) / 36525.0
    angles, rates = [], []
    for mean_coefficients in MEAN_ELEMENTS:
        value, derivative = _polynomial(mean_coefficients, century)
        angles.append((value % 1296000) * AS2R)
        rates.append(derivative * AS2R / 36525.0)
    scale = table["timescale_days"]
    t = (jd_tt - 2451545.0) / scale
    positions: list[list[float]] = [[], [], []]
    velocities: list[list[float]] = [[], [], []]
    for harmonics, axes in terms:
        phase = math.fsum(k * angles[i] for k, i in harmonics)
        rate = math.fsum(k * rates[i] for k, i in harmonics)
        si, co = math.sin(phase), math.cos(phase)
        for axis, coefficients in enumerate(axes):
            if not harmonics:
                value, derivative = _polynomial(coefficients[::-1], t)
                positions[axis].append(value)
                velocities[axis].append(derivative / scale)
            else:
                c, dc = _polynomial(coefficients[::2][::-1], t)
                s, ds = _polynomial(coefficients[1::2][::-1], t)
                positions[axis].append(c * co + s * si)
                velocities[axis].append(
                    (dc * co + ds * si) / scale + (s * co - c * si) * rate
                )
    unit = table["amplitude_scale"] * AS2R
    longitude, latitude, radius = [math.fsum(p) * unit for p in positions]
    dl, db, dr = [math.fsum(v) * unit for v in velocities]
    longitude += angles[2]
    dl += rates[2]
    radius = (radius + 1) * table["distance_au"]
    dr *= table["distance_au"]
    cl, sl, cb, sb = (
        math.cos(longitude),
        math.sin(longitude),
        math.cos(latitude),
        math.sin(latitude),
    )
    x, y, z = radius * cb * cl, radius * cb * sl, radius * sb
    dx = dr * cb * cl - radius * sb * db * cl - radius * cb * sl * dl
    dy = dr * cb * sl - radius * sb * db * sl + radius * cb * cl * dl
    dz = dr * sb + radius * cb * db
    epsilon = table["obliquity_j2000_arcseconds"] * AS2R
    co, si = math.cos(epsilon), math.sin(epsilon)
    return (x, co * y - si * z, si * y + co * z), (
        dx,
        co * dy - si * dz,
        si * dy + co * dz,
    )


def solar_longitude(jd_tt: float) -> float:
    """Apparent geocentric longitude; no native short-Moon Earth offset."""
    if not math.isfinite(jd_tt):
        raise ValueError("Solar TT Julian day must be finite")
    swe = native.swe
    if swe is None:
        raise EphemerisSourceError("solar_native_unavailable")
    position, velocity = earth_moon_barycenter(jd_tt)
    flags = (
        swe.FLG_MOSEPH
        | swe.FLG_TRUEPOS
        | swe.FLG_NONUT
        | swe.FLG_J2000
        | swe.FLG_XYZ
        | swe.FLG_EQUATORIAL
        | swe.FLG_ICRS
        | swe.FLG_SPEED
    )
    moon, returned = native.ephemeris_call("calc", jd_tt, swe.MOON, flags)
    # TRUEPOS implies NOABERR/NOGDEFL. The complete lunar state must remain
    # Moshier, geometric, geocentric and in the requested fixed frame.
    expected = flags | swe.FLG_NOABERR | swe.FLG_NOGDEFL
    if returned != expected or not all(math.isfinite(v) for v in moon):
        raise EphemerisSourceError("coordinate_contract_changed")
    earth = tuple(p - m * MOON_MASS_FRACTION for p, m in zip(position, moon[:3]))
    motion = tuple(v - m * MOON_MASS_FRACTION for v, m in zip(velocity, moon[3:]))
    distance = math.sqrt(math.fsum(p * p for p in earth))
    natural = (-earth[0] / distance, -earth[1] / distance, -earth[2] / distance)
    velocity_c = (motion[0] / C_AU_DAY, motion[1] / C_AU_DAY, motion[2] / C_AU_DAY)
    apparent = aberration(natural, velocity_c, distance)
    vector = apparent_ecliptic(apparent, jd_tt)
    return math.degrees(math.atan2(vector[1], vector[0])) % 360


def model_details() -> dict[str, object]:
    table, _, digest = _table()
    return {
        "model_id": MODEL_ID,
        "coefficient_sha256": digest,
        "frame_coefficient_sha256": analytic_frame_details(2451545.0)[
            "coefficient_sha256"
        ],
        "source_url": table["source_url"],
        "source_archive_sha256": table["source_archive_sha256"],
        "source_file_sha256": table["source_file_sha256"],
        "earth_series": "Moshier December 1996 ear404, complete g3plan",
        "earth_velocity": "analytic derivative of every EMB series term",
        "lunar_series": "complete native Moshier geometric Moon, public swe_calc",
        "native_lunar_library_version": str(getattr(native.swe, "version", "unknown")),
        "time_argument": "TT; native Moshier analytical series time convention",
        "position_frame": "geocentric apparent IAU2006/P03 + IAU2000B true ecliptic of date",
        "native_moshier_relabelled": False,
        "reference_values_used_at_runtime": False,
        "accuracy_certified": False,
        "scope": "Named complete Moshier revision, not stock Swiss Moshier or DE440. Finite TT comparisons do not certify all epochs, civil time or predictive efficacy.",
    }
