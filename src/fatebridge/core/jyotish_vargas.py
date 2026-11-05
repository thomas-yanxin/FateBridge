"""Classical sign assignments; rational partitioning preserves cusp sides.

D30 in the selected BPHS table has five unequal ranges. That table assigns
signs, not a unique degree inside them, so no invented D30 longitude is returned.
Equal-division coordinates are a declared linear display convention.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Optional

SUPPORTED_DIVISIONS = (2, 3, 7, 9, 10, 12, 30)
SAPTA_DIVISIONS = (1, 2, 3, 7, 9, 12, 30)
RASI_LORDS = [
    "Mars",
    "Venus",
    "Mercury",
    "Moon",
    "Sun",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Saturn",
    "Jupiter",
]


def longitude_ratio(longitude: float | Fraction) -> tuple[int, int]:
    if not math.isfinite(longitude):
        raise ValueError("经度必须为有限数。")
    n, d = (
        longitude.as_integer_ratio()
        if isinstance(longitude, Fraction)
        else float(longitude).as_integer_ratio()
    )
    return n % (360 * d), d


def varga_coordinates(
    longitude: float | Fraction, division: int
) -> tuple[int, Optional[float]]:
    """Return zodiac sign index and transformed degree, or None for D30."""
    n, d = longitude_ratio(longitude)
    sign, degree_numerator = divmod(n, 30 * d)
    if division == 1:
        return sign, min(degree_numerator / d, math.nextafter(30.0, 0.0))
    if division == 30:
        bounds, destinations = (
            ([5, 10, 18, 25, 30], [0, 10, 8, 2, 6])
            if sign % 2 == 0
            else ([5, 12, 20, 25, 30], [1, 5, 11, 9, 7])
        )
        for end, destination in zip(bounds, destinations):
            if degree_numerator < end * d:
                return destination, None
        raise AssertionError("Normalized longitude must belong to one D30 interval")
    if division not in SUPPORTED_DIVISIONS:
        raise ValueError("本版本支持 D1、D2、D3、D7、D9、D10、D12、D30。")
    part, remainder = divmod(degree_numerator * division, 30 * d)
    if division == 2:
        destination = ([4, 3] if sign % 2 == 0 else [3, 4])[part]
    elif division == 3:
        destination = (sign + 4 * part) % 12
    elif division == 7:
        destination = (sign + (0 if sign % 2 == 0 else 6) + part) % 12
    elif division == 9:
        destination = ([0, 9, 6, 3][sign % 4] + part) % 12
    elif division == 10:
        destination = (sign + (0 if sign % 2 == 0 else 8) + part) % 12
    else:  # D12
        destination = (sign + part) % 12
    return destination, min(remainder / d, math.nextafter(30.0, 0.0))


def varga_sign(longitude: float | Fraction, division: int) -> int:
    return varga_coordinates(longitude, division)[0]


def varga_longitude(longitude: float | Fraction, division: int) -> float:
    sign, degree = varga_coordinates(longitude, division)
    if degree is None:
        raise ValueError("D30 仅分配星座；所选原典未规定唯一的盘内度数。")
    return min(sign * 30.0 + degree, math.nextafter((sign + 1) * 30.0, -math.inf))
