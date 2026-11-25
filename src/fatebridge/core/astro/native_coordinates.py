"""Validate coordinate frame and reference point before consuming native values."""

import math
from typing import Any, Sequence, Tuple

from fatebridge.utils.errors import EphemerisSourceError

COORDINATE_FLAGS = (
    "FLG_EQUATORIAL",
    "FLG_XYZ",
    "FLG_RADIANS",
    "FLG_J2000",
    "FLG_ICRS",
    "FLG_SIDEREAL",
    "FLG_TOPOCTR",
    "FLG_HELCTR",
    "FLG_BARYCTR",
    "FLG_TRUEPOS",
    "FLG_NONUT",
    "FLG_NOABERR",
    "FLG_NOGDEFL",
    "FLG_JPLHOR",
    "FLG_JPLHOR_APPROX",
    "FLG_CENTER_BODY",
)


def require_spherical_coordinates(
    coordinates: Sequence[float],
    returned_flags: int,
    *,
    native: Any,
    equatorial: bool = False,
    sidereal: bool = False,
) -> Tuple[float, float, float]:
    """Geocentric apparent spherical degrees, of date, in the requested frame.

    Native sidereal computation automatically sets NONUT. The standard consumer
    does not request a center-of-body override of the native reference point.
    Model selection and SPEED availability have separate guards.
    """
    mask = 0
    for name in COORDINATE_FLAGS:
        mask |= getattr(native, name)
    expected = (native.FLG_EQUATORIAL if equatorial else 0) | (
        native.FLG_SIDEREAL | native.FLG_NONUT if sidereal else 0
    )
    if returned_flags < 0 or returned_flags & mask != expected:
        raise EphemerisSourceError("coordinate_contract_changed")
    try:
        count = 6 if returned_flags & native.FLG_SPEED else 3
        values = tuple(float(coordinates[i]) for i in range(count))
    except (IndexError, TypeError, ValueError, OverflowError) as error:
        raise EphemerisSourceError("coordinate_values_unavailable") from error
    if (
        not all(math.isfinite(v) for v in values)
        or not -90 <= values[1] <= 90
        or values[2] < 0
    ):
        raise EphemerisSourceError("coordinate_values_unavailable")
    return values[0], values[1], values[2]


def require_altitude(value: float) -> float:
    if not math.isfinite(value) or not -90 <= value <= 90:
        raise EphemerisSourceError("coordinate_values_unavailable")
    return value
