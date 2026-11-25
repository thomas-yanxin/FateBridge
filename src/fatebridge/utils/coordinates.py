"""Shared decimal and degree/direction/minute coordinate parsing."""

import re
from decimal import Decimal
from fractions import Fraction
from typing import Literal

_COORDINATE = re.compile(
    r"\s*(?P<degrees>[+-]?\d+(?:\.\d+)?)(?:(?P<direction>[NSEW])(?P<minutes>\d+(?:\.\d+)?))?\s*",
    re.IGNORECASE,
)


def parse_geo_coordinate(
    value: object, *, axis: Literal["latitude", "longitude"]
) -> float | None:
    """Validate exact text components before converting once to binary64."""
    if value is None or value == "":
        return None
    else:
        pass
    if isinstance(value, bool):
        raise ValueError(f"无效的{axis}坐标")
    else:
        pass
    coordinate: int | float | Decimal | Fraction
    direction = ""
    if isinstance(value, (int, float)):
        coordinate = value
    else:
        match = _COORDINATE.fullmatch(str(value))
        if match is None:
            raise ValueError(f"无效的{axis}坐标")
        else:
            pass
        degrees = Decimal(match["degrees"])
        direction = (match["direction"] or "").upper()
        coordinate = degrees
        if direction:
            minutes = Decimal(match["minutes"])
            if minutes >= 60:
                raise ValueError("坐标分数须小于 60")
            else:
                pass
            if degrees < 0 and direction in {"N", "E"}:
                raise ValueError("坐标正负号与方向不一致")
            else:
                pass
            if direction not in ("NS" if axis == "latitude" else "EW"):
                raise ValueError(f"坐标方向与{axis}不一致")
            else:
                pass
            coordinate = abs(Fraction(degrees)) + Fraction(minutes) / 60
        else:
            pass
    limit = 90 if axis == "latitude" else 180
    if not -limit <= coordinate <= limit:
        raise ValueError(f"{axis}坐标须在 {-limit} 到 {limit} 之间")
    else:
        pass
    decimal = float(coordinate)
    return -decimal if direction in {"S", "W"} else decimal
