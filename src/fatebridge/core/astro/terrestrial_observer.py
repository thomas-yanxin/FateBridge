"""Physical terrestrial receiver and its original-source position interface.

SOFA supplies the WGS84 position and nominal instantaneous rotation velocity.
The source bridge compensates Swiss 2.10.03's own reverse clock, ellipsoid,
mean precession and omitted bias without changing the actual geographic site.
It matches source position only: optical calculations must use the physical
velocity, rather than inherit the source's velocity from a virtual location.

Source interface: original sweph.c swi_get_observer, v2.10.03.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Protocol

import erfa

from fatebridge.core.astro.cartesian import CartesianState, dot, mm, mv, transpose
from fatebridge.core.astro.earth_attitude import (
    EarthAttitude,
    PhysicalEquator,
    RotationSource,
)
from fatebridge.core.astro.reference_frames import native_precession_frame
from fatebridge.utils.errors import EphemerisSourceError

AU_METRES = 149_597_870_700.0
SOURCE_EQUATORIAL_RADIUS_METRES = 6_378_136.6
SOURCE_FLATTENING = 1 / 298.25642


class ObserverSource(RotationSource, Protocol):
    def sidtime0(self, jd_ut1: float, obliquity: float, nutation: float) -> float: ...


@dataclass(frozen=True)
class TerrestrialFrame:
    """Geodetic east, north and up, expressed in the selected equator."""

    east: tuple[float, float, float]
    north: tuple[float, float, float]
    up: tuple[float, float, float]

    def equatorial_site(self) -> tuple[float, float]:
        """Right ascension and declination of the model vertical, in degrees."""
        x, y, z = self.up
        return (
            math.degrees(math.atan2(y, x)) % 360,
            math.degrees(math.atan2(z, math.hypot(x, y))),
        )


def terrestrial_frame(
    equator: PhysicalEquator, *, longitude: float, latitude: float
) -> TerrestrialFrame:
    """Use the same polar motion and rotation as the physical receiver.

    SOFA C2TEQX is W R3(GAST) N; local ENU rows in N axes are therefore
    L W R3(GAST). The zero-EOP branch retains the original scalar geometry.
    The vertical is the declared ellipsoid normal, not a surveyed plumb line.
    """
    phi = math.radians(latitude)
    if equator.polar_motion is None:
        local = math.radians(equator.greenwich_sidereal_degrees + longitude)
        return TerrestrialFrame(
            (-math.sin(local), math.cos(local), 0.0),
            (
                -math.sin(phi) * math.cos(local),
                -math.sin(phi) * math.sin(local),
                math.cos(phi),
            ),
            (
                math.cos(phi) * math.cos(local),
                math.cos(phi) * math.sin(local),
                math.sin(phi),
            ),
        )
    lam = math.radians(longitude)
    local_itrs = (
        (-math.sin(lam), math.cos(lam), 0.0),
        (
            -math.sin(phi) * math.cos(lam),
            -math.sin(phi) * math.sin(lam),
            math.cos(phi),
        ),
        (
            math.cos(phi) * math.cos(lam),
            math.cos(phi) * math.sin(lam),
            math.sin(phi),
        ),
    )
    pole = erfa.pom00(*equator.polar_motion)
    polar_motion = (
        (float(pole[0][0]), float(pole[0][1]), float(pole[0][2])),
        (float(pole[1][0]), float(pole[1][1]), float(pole[1][2])),
        (float(pole[2][0]), float(pole[2][1]), float(pole[2][2])),
    )
    theta = math.radians(equator.greenwich_sidereal_degrees)
    rotation = (
        (math.cos(theta), math.sin(theta), 0.0),
        (-math.sin(theta), math.cos(theta), 0.0),
        (0.0, 0.0, 1.0),
    )
    east, north, up = mm(mm(local_itrs, polar_motion), rotation)
    return TerrestrialFrame(
        (east[0], east[1], east[2]),
        (north[0], north[1], north[2]),
        (up[0], up[1], up[2]),
    )


def house_site(
    attitude: EarthAttitude, *, longitude: float, latitude: float
) -> tuple[float, float]:
    """ARMC and vertical latitude for the house model's actual equator."""
    if attitude.equator.polar_motion is None:
        return (attitude.house_sidereal_degrees + longitude) % 360, latitude
    frame = terrestrial_frame(attitude.equator, longitude=longitude, latitude=latitude)
    right_ascension, declination = frame.equatorial_site()
    origin = math.degrees(
        math.atan2(
            dot(attitude.reduction.house_frame[0], attitude.equator.matrix[1]),
            dot(attitude.reduction.house_frame[0], attitude.equator.matrix[0]),
        )
    )
    return (
        float((Fraction(right_ascension) - Fraction(origin)) % 360) % 360,
        declination,
    )


def terrestrial_observer(
    equator: PhysicalEquator,
    *,
    longitude: float,
    latitude: float,
    height: float,
) -> CartesianState:
    """Geocentric receiver in ICRS axes, AU and AU/day, at one epoch pair.

    Pairing GAST with its matching triad is equivalent to the ERA/CIRS
    construction. Selected polar motion and TIO locator are supplied with
    that attitude; the default retains zero EOP. This is a WGS84 ellipsoid
    and nominal spin, not a surveyed geoid or full station-motion derivative.
    """
    xp, yp, sp = equator.polar_motion or (0.0, 0.0, 0.0)
    pv = erfa.pvtob(
        math.radians(longitude),
        math.radians(latitude),
        height,
        xp,
        yp,
        sp,
        math.radians(equator.greenwich_sidereal_degrees),
    )
    inverse = transpose(equator.matrix)
    x, y, z = mv(inverse, tuple(float(value) for value in pv["p"]))
    vx, vy, vz = mv(inverse, tuple(float(value) for value in pv["v"]))
    return CartesianState(
        (x / AU_METRES, y / AU_METRES, z / AU_METRES),
        (vx * 86400 / AU_METRES, vy * 86400 / AU_METRES, vz * 86400 / AU_METRES),
    )


def native_observer_site(
    module: ObserverSource,
    equator: PhysicalEquator,
    receiver: CartesianState,
    *,
    ephemeris_flags: int,
) -> tuple[float, float, float]:
    """SDK location whose original observer *position* is the physical one.

    The original source adds a bias-free mean-J2000 receiver to its inertial
    ephemeris state. Reproduce that specific position map in reverse, using
    its own TT-based UT approximation and mean sidereal phase. These source
    coordinates belong only to a native coordinate call; the horizon and
    physical velocity continue to use the actual site and physical triad.
    """
    native = native_precession_frame(equator.jd_tt)
    source_position = tuple(
        value * AU_METRES for value in mv(native, receiver.position)
    )
    longitude, latitude, height = erfa.gc2gde(
        SOURCE_EQUATORIAL_RADIUS_METRES, SOURCE_FLATTENING, source_position
    )
    values, returned = module.calc(equator.jd_tt, module.ECL_NUT, ephemeris_flags)
    if returned < 0:
        raise EphemerisSourceError("coordinate_values_unavailable")
    internal_ut1 = equator.jd_tt - module.deltat_ex(equator.jd_tt, ephemeris_flags)
    internal_phase = module.sidtime0(internal_ut1, values[1], 0.0) * 15
    return (
        math.remainder(math.degrees(longitude) - internal_phase, 360),
        math.degrees(latitude),
        float(height),
    )
