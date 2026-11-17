"""Physical terrestrial receiver and its original-source position interface.

SOFA supplies the WGS84 position and nominal instantaneous rotation velocity.
The source bridge compensates Swiss 2.10.03's own reverse clock, ellipsoid,
mean precession and omitted bias without changing the actual geographic site.
It matches source position only: optical calculations must use the physical
velocity, rather than inherit the source's velocity from a virtual location.

Source interface: original sweph.c swi_get_observer, v2.10.03.
https://github.com/aloistr/swisseph/blob/175e1fcb3108bcd5c0d146c803f51dcf23508012/sweph.c
"""

from __future__ import annotations

import math
from typing import Protocol

import erfa

from fatebridge.core.astro.cartesian import CartesianState
from fatebridge.core.astro.earth_attitude import PhysicalEquator, RotationSource
from fatebridge.core.astro.reference_frames import (
    mv,
    native_precession_frame,
    transpose,
)
from fatebridge.utils.errors import EphemerisSourceError

AU_METRES = 149_597_870_700.0
SOURCE_EQUATORIAL_RADIUS_METRES = 6_378_136.6
SOURCE_FLATTENING = 1 / 298.25642


class ObserverSource(RotationSource, Protocol):
    def sidtime0(self, jd_ut1: float, obliquity: float, nutation: float) -> float: ...


def terrestrial_observer(
    equator: PhysicalEquator,
    *,
    longitude: float,
    latitude: float,
    height: float,
) -> CartesianState:
    """Geocentric receiver in ICRS axes, AU and AU/day, at one epoch pair.

    Pairing GAST with the matching true-equinox triad is equivalent to the
    standard ERA/CIRS construction. Polar motion and TIO locator are zero;
    this is a declared WGS84 ellipsoid/nominal spin, not a surveyed geoid,
    measured EOP or a derivative of an extrapolated orientation model.
    """
    pv = erfa.pvtob(
        math.radians(longitude),
        math.radians(latitude),
        height,
        0.0,
        0.0,
        0.0,
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
