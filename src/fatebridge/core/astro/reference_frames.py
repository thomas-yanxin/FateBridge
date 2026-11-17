"""Source-defined equatorial/ecliptic frames shared by astronomy domains.

Vondrak, Capitaine & Wallace (2011/2012) pole series follow ERFA2.0.1.
The separate scalar obliquity and full-Simon 77-term nutation reproduce the
inspected Swiss2.10.03 default date convention. The scalar and coupled-pole
ecliptics are distinct approximations. IAU2006 Fukushima-Williams angles
also serve the explicitly separate P03/2000B analytic solar model.

The immutable historical coefficient packet contains common frame tables
and Lahiri anchor parameters; only continuous_lahiri consumes the anchor.
Sources: https://doi.org/10.1051/0004-6361/201117274
https://doi.org/10.1051/0004-6361/201117274e
https://github.com/liberfa/erfa/tree/v2.0.1/src
https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/swephlib.c
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence, Tuple, TypedDict

from fatebridge.core.astro.nutation import nutation

Vector = Tuple[float, ...]
Matrix = Tuple[Vector, ...]

NATIVE_TROPICAL_MODEL = "vondrak_scalar_obliquity_full_simon77_iau2006_bias_v1"

# Swiss 2.10.03 swi_bias(), forward ICRS -> native mean J2000. These
# source constants differ by about one microarcsecond from the separately
# derived Fukushima-Williams bias used by the DE441 source frame below.
# https://github.com/astrorigin/swisseph/blob/696bda432298d482d27e67a0cf1238920301a7dd/swephlib.c
_NATIVE_BIAS_2006: Matrix = (
    (0.99999999999999412, -0.00000007078368961, 0.00000008056213978),
    (0.00000007078368695, 0.99999999999999700, 0.00000003306428553),
    (-0.00000008056214212, -0.00000003306427981, 0.99999999999999634),
)


class ReferenceFrameParameters(TypedDict):
    native_tables: dict[str, list[list[str]]]
    anchor_tt: str
    anchor_origin_degrees_terms: list[str]
    IAU1976_angles_arcsec_coefficients: dict[str, list[str]]


COEFFICIENT_SHA256 = "577c38bf4db44728523e126ac8a50b899fe761d666a1253c0c6e9788bbf68791"
_COEFFICIENT_BYTES = (
    Path(__file__).resolve().parents[2] / "data/astronomy/lahiri-frame-v1.json"
).read_bytes()
if hashlib.sha256(_COEFFICIENT_BYTES).hexdigest() != COEFFICIENT_SHA256:
    raise RuntimeError("Reference frame coefficients differ from the declared source")
DATA: ReferenceFrameParameters = json.loads(_COEFFICIENT_BYTES)
AS2R = math.pi / 648000.0


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    return math.fsum(x * y for x, y in zip(a, b))


def cross(a: Sequence[float], b: Sequence[float]) -> Vector:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def add(a: Sequence[float], b: Sequence[float]) -> Vector:
    return tuple(x + y for x, y in zip(a, b))


def transpose(a: Sequence[Sequence[float]]) -> Matrix:
    return tuple(zip(*a))


def mv(a: Sequence[Sequence[float]], v: Sequence[float]) -> Vector:
    return tuple(dot(row, v) for row in a)


def rotate_spherical(
    matrix: Matrix, longitude: float, latitude: float
) -> tuple[float, float]:
    """Rotate a direction in degrees, without changing its physical distance."""
    lon, lat = math.radians(longitude), math.radians(latitude)
    cosine = math.cos(lat)
    x, y, z = mv(
        matrix, (cosine * math.cos(lon), cosine * math.sin(lon), math.sin(lat))
    )
    return (
        math.degrees(math.atan2(y, x)) % 360,
        math.degrees(math.atan2(z, math.hypot(x, y))),
    )


def mm(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> Matrix:
    columns = transpose(b)
    return tuple(tuple(dot(row, column) for column in columns) for row in a)


def madd(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> Matrix:
    return tuple(add(x, y) for x, y in zip(a, b))


def pair(tt: float, polynomial: str, periodic: str) -> Tuple[Vector, Vector]:
    century = (tt - 2451545.0) / 36525.0
    poly = DATA["native_tables"][polynomial]
    terms = DATA["native_tables"][periodic]
    values = []
    derivatives = []
    for axis in range(2):
        value_terms = [
            float(row[axis]) * century**power for power, row in enumerate(poly)
        ]
        derivative_terms = [
            power * float(row[axis]) * century ** (power - 1)
            for power, row in enumerate(poly)
            if power
        ]
        for period, cosine, sine in zip(terms[0], terms[1 + axis], terms[3 + axis]):
            frequency = 2.0 * math.pi / float(period)
            angle = frequency * century
            c, s = math.cos(angle), math.sin(angle)
            cv, sv = float(cosine), float(sine)
            value_terms.append(cv * c + sv * s)
            derivative_terms.append(frequency * (-cv * s + sv * c))
        values.append(math.fsum(value_terms) * AS2R)
        derivatives.append(math.fsum(derivative_terms) * AS2R / 36525.0)
    return tuple(values), tuple(derivatives)


def precession(tt: float) -> Tuple[Matrix, Matrix]:
    (p, q), (pd, qd) = pair(tt, "pqpol", "pqper")
    eps0 = 84381.406 * AS2R
    ce, se = math.cos(eps0), math.sin(eps0)
    z = math.sqrt(1.0 - p * p - q * q)
    zd = -(p * pd + q * qd) / z
    ecliptic = (p, -q * ce - z * se, -q * se + z * ce)
    ecliptic_d = (pd, -qd * ce - zd * se, -qd * se + zd * ce)
    (x, y), (xd, yd) = pair(tt, "xypol", "xyper")
    z = math.sqrt(1.0 - x * x - y * y)
    zd = -(x * xd + y * yd) / z
    equator = (x, y, z)
    equator_d = (xd, yd, zd)
    raw = cross(equator, ecliptic)
    raw_d = add(cross(equator_d, ecliptic), cross(equator, ecliptic_d))
    radius = math.sqrt(dot(raw, raw))
    equinox = tuple(v / radius for v in raw)
    radial = dot(equinox, raw_d)
    equinox_d = tuple((d - v * radial) / radius for d, v in zip(raw_d, equinox))
    middle = cross(equator, equinox)
    middle_d = add(cross(equator_d, equinox), cross(equator, equinox_d))
    return (equinox, middle, equator), (equinox_d, middle_d, equator_d)


def ecliptic_rotation(epsilon: float, epsilon_d: float = 0.0) -> Tuple[Matrix, Matrix]:
    c, s = math.cos(epsilon), math.sin(epsilon)
    return (
        ((1.0, 0.0, 0.0), (0.0, c, s), (0.0, -s, c)),
        (
            (0.0, 0.0, 0.0),
            (0.0, -s * epsilon_d, c * epsilon_d),
            (0.0, -c * epsilon_d, -s * epsilon_d),
        ),
    )


def pmat76(tt: float) -> Matrix:
    century = (tt - 2451545.0) / 36525.0
    angles = {
        name: math.fsum(float(c) * century**i for i, c in enumerate(terms)) * AS2R
        for name, terms in DATA["IAU1976_angles_arcsec_coefficients"].items()
    }
    Z, z, theta = angles["zeta"], angles["z"], angles["theta"]
    cZ, sZ, cz, sz, cT, sT = (
        math.cos(Z),
        math.sin(Z),
        math.cos(z),
        math.sin(z),
        math.cos(theta),
        math.sin(theta),
    )
    return (
        (cZ * cT * cz - sZ * sz, -sZ * cT * cz - cZ * sz, -sT * cz),
        (cZ * cT * sz + sZ * cz, -sZ * cT * sz + cZ * cz, -sT * sz),
        (cZ * sT, -sZ * sT, cT),
    )


def _polynomial(t: float, coefficients: Sequence[float]) -> float:
    value = 0.0
    for coefficient in reversed(coefficients):
        value = value * t + coefficient
    return value * AS2R


def precession_angles(date1: float, date2: float = 0.0) -> Tuple[float, ...]:
    if not math.isfinite(date1) or not math.isfinite(date2):
        raise ValueError("Frame epoch must be finite")
    t = ((date1 - 2451545.0) + date2) / 36525.0
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


def rotate(
    vector: Sequence[float], axis: str, angle: float
) -> tuple[float, float, float]:
    x, y, z = vector
    co, si = math.cos(angle), math.sin(angle)
    if axis == "x":
        return x, co * y + si * z, -si * y + co * z
    return co * x + si * y, -si * x + co * y, z


def mean_ecliptic_frame(tt: float) -> Tuple[Matrix, Matrix]:
    """Mean-J2000 to scalar-obliquity ecliptic of date and TT derivative."""
    matrix, matrix_d = precession(tt)
    values, derivatives = pair(tt, "pepol", "peper")
    rotation, rotation_d = ecliptic_rotation(values[1], derivatives[1])
    return mm(rotation, matrix), madd(mm(rotation_d, matrix), mm(rotation, matrix_d))


@lru_cache(maxsize=512)
def native_precession_frame(tt: float) -> Matrix:
    """Original Swiss precession, including its exact J2000 shortcut."""
    return (
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        if tt == 2451545.0
        else precession(tt)[0]
    )


def native_equatorial_frame(
    tt: float,
    mean_obliquity: float,
    nutation_longitude: float,
    nutation_obliquity: float,
) -> Matrix:
    """Verified Swiss default ICRS -> true equator/equinox of date.

    The three angles are the actual ECL_NUT values in degrees at this TT.
    Keep the native bias and the exact native J2000 precession shortcut;
    this matrix describes that coordinate model, not full IAU 2006/2000A.
    """
    import erfa

    if not all(
        math.isfinite(x)
        for x in (tt, mean_obliquity, nutation_longitude, nutation_obliquity)
    ):
        raise ValueError("Native frame inputs must be finite")
    precessed = native_precession_frame(tt)
    nutated: Matrix = tuple(
        tuple(float(value) for value in row)
        for row in erfa.numat(
            math.radians(mean_obliquity),
            math.radians(nutation_longitude),
            math.radians(nutation_obliquity),
        )
    )
    return mm(nutated, mm(precessed, _NATIVE_BIAS_2006))


@dataclass(frozen=True)
class EquatorialReduction:
    """Coordinate transport and house parameters for one target equator.

    The native ecliptic coordinates retain their declared source plane and
    origin. Earth attitude can use a different, explicitly supplied pole.
    The house equinox is their actual intersection, so cusp parameters do
    not combine the target pole with the old scalar obliquity.
    """

    native_to_target: Matrix
    target_to_native: Matrix
    native_to_house: Matrix
    ecliptic_to_target: Matrix
    target_to_ecliptic: Matrix
    house_frame: Matrix
    house_obliquity: float
    house_longitude_origin: float


@lru_cache(maxsize=512)
def iau_equatorial_frame(tt: float) -> Matrix:
    """IAU 2006 precession with matched IAU 2000A nutation, from ERFA.

    This is a coordinate triad, not a physical ephemeris, measured pole or
    long-term extrapolation policy. Epoch selection belongs to its caller.
    """
    import erfa

    return tuple(tuple(float(value) for value in row) for row in erfa.pnm06a(tt, 0.0))


@lru_cache(maxsize=512)
def equatorial_reduction(
    tt: float,
    true_obliquity: float,
    mean_obliquity: float,
    nutation_longitude: float,
    nutation_obliquity: float,
    target: Matrix,
) -> EquatorialReduction:
    """Transport source coordinates to a supplied physical equatorial triad.

    IAU/SOFA row matrices map ICRS vectors into each coordinate frame.
    Their product with the source transpose transports coordinates; the
    source ecliptic pole and target equatorial pole determine the house
    equinox and inclination without changing the source ecliptic plane.
    """
    if not math.isfinite(true_obliquity):
        raise ValueError("Native true obliquity must be finite")
    native = native_equatorial_frame(
        tt, mean_obliquity, nutation_longitude, nutation_obliquity
    )
    rotation, _ = ecliptic_rotation(math.radians(true_obliquity))
    ecliptic = mm(rotation, native)
    native_to_target = mm(target, transpose(native))
    ecliptic_to_target = mm(target, transpose(ecliptic))
    pole = target[2]
    equinox_raw = cross(pole, ecliptic[2])
    sine_obliquity = math.sqrt(dot(equinox_raw, equinox_raw))
    equinox = tuple(value / sine_obliquity for value in equinox_raw)
    house = (equinox, cross(pole, equinox), pole)
    return EquatorialReduction(
        native_to_target=native_to_target,
        target_to_native=transpose(native_to_target),
        native_to_house=mm(house, transpose(native)),
        ecliptic_to_target=ecliptic_to_target,
        target_to_ecliptic=transpose(ecliptic_to_target),
        house_frame=house,
        house_obliquity=math.degrees(
            math.atan2(sine_obliquity, dot(pole, ecliptic[2]))
        ),
        house_longitude_origin=math.degrees(
            math.atan2(dot(equinox, ecliptic[1]), dot(equinox, ecliptic[0]))
        ),
    )


@lru_cache(maxsize=1)
def icrs_to_mean_j2000() -> Matrix:
    """IAU2006 frame bias, derived from the source Fukushima-Williams angles."""
    gamma, phi, psi, epsilon = precession_angles(2451545.0)
    columns = []
    for basis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
        for axis, angle in (("z", gamma), ("x", phi), ("z", -psi), ("x", -epsilon)):
            basis = rotate(basis, axis, angle)
        columns.append(basis)
    return transpose(columns)


def mean_j2000_apparent_ecliptic(vector: Sequence[float], tt: float) -> Vector:
    """Mean-J2000 apparent ray to the native true ecliptic of date."""
    mean, _ = mean_ecliptic_frame(tt)
    projected = mv(mean, vector)
    dpsi, _, _, _ = nutation(tt)
    return rotate(projected, "z", -math.radians(dpsi))


def native_apparent_ecliptic(vector: Sequence[float], tt: float) -> Vector:
    """ICRS ray to the inspected native scalar-obliquity true ecliptic.

    This is a coordinate convention, not a physical-accuracy certificate.
    Frame bias, long-term precession, scalar obliquity and nutation share
    the same documented convention as file-backed native solar positions.
    """
    return mean_j2000_apparent_ecliptic(mv(icrs_to_mean_j2000(), vector), tt)
