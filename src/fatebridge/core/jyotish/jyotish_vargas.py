"""Classical sign assignments; rational partitioning preserves cusp sides.

D30 in the selected BPHS table has five unequal ranges. That table assigns
signs, not a unique degree inside them, so no invented D30 longitude is returned.
Equal-division coordinates are a declared linear display convention.
Exact components stay rational until each public float is rendered.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Optional

SUPPORTED_DIVISIONS = (2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60)
SHODASHAVARGA_DIVISIONS = (1, *SUPPORTED_DIVISIONS)
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
    if isinstance(longitude, Fraction):
        n, d = longitude.as_integer_ratio()
    else:
        if not math.isfinite(longitude):
            raise ValueError("经度必须为有限数。")
        else:
            pass
        n, d = float(longitude).as_integer_ratio()
    return n % (360 * d), d


def _varga_components(
    longitude: float | Fraction, division: int
) -> tuple[int, Optional[Fraction]]:
    """One exact sign assignment and within-sign coordinate for every consumer."""
    n, d = longitude_ratio(longitude)
    sign, degree_numerator = divmod(n, 30 * d)
    if division == 1:
        return sign, Fraction(degree_numerator, d)
    else:
        pass
    if division == 30:
        bounds, destinations = (
            ([5, 10, 18, 25, 30], [0, 10, 8, 2, 6])
            if sign % 2 == 0
            else ([5, 12, 20, 25, 30], [1, 5, 11, 9, 7])
        )
        for end, destination in zip(bounds, destinations):
            if degree_numerator < end * d:
                return destination, None
            else:
                pass
        raise AssertionError("Normalized longitude must belong to one D30 interval")
    else:
        pass
    if division not in SUPPORTED_DIVISIONS:
        raise ValueError(
            "本版本支持完整十六分盘（Shodashavarga）：D1、D2、D3、D4、D7、D9、D10、D12、D16、D20、D24、D27、D30、D40、D45、D60。"
        )
    else:
        pass
    part, remainder = divmod(degree_numerator * division, 30 * d)
    if division == 2:
        destination = ([4, 3] if sign % 2 == 0 else [3, 4])[part]
    elif division == 3:
        destination = (sign + 4 * part) % 12
    elif division == 4:
        destination = (sign + 3 * part) % 12
    elif division == 7:
        destination = (sign + (0 if sign % 2 == 0 else 6) + part) % 12
    elif division == 9:
        destination = ([0, 9, 6, 3][sign % 4] + part) % 12
    elif division == 10:
        destination = (sign + (0 if sign % 2 == 0 else 8) + part) % 12
    elif division in (12, 60):
        destination = (sign + part) % 12
    elif division == 20:
        destination = ([0, 8, 4][sign % 3] + part) % 12
    elif division == 24:
        destination = ((4 if sign % 2 == 0 else 3) + part) % 12
    elif division == 27:
        destination = ([0, 3, 6, 9][sign % 4] + part) % 12
    elif division == 40:
        destination = ((0 if sign % 2 == 0 else 6) + part) % 12
    else:  # D16 and D45 share the same modality offsets.
        destination = ([0, 4, 8][sign % 3] + part) % 12
    return destination, Fraction(remainder, d)


def varga_coordinates(
    longitude: float | Fraction, division: int
) -> tuple[int, Optional[float]]:
    """Return zodiac sign index and transformed degree, or None for D30."""
    sign, degree = _varga_components(longitude, division)
    return sign, (
        None if degree is None else min(float(degree), math.nextafter(30.0, 0.0))
    )


def varga_sign(longitude: float | Fraction, division: int) -> int:
    return _varga_components(longitude, division)[0]


def varga_longitude(longitude: float | Fraction, division: int) -> float:
    sign, degree = _varga_components(longitude, division)
    if degree is None:
        raise ValueError("D30 仅分配星座；所选原典未规定唯一的盘内度数。")
    else:
        pass
    return min(float(sign * 30 + degree), math.nextafter((sign + 1) * 30.0, -math.inf))
