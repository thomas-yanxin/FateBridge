"""Shared decimal and degree/direction/minute coordinate parsing."""

import math
import re
from typing import Any, Literal, Optional

_COORDINATE = re.compile(
    r"\s*(?P<degrees>[+-]?\d+(?:\.\d+)?)(?:(?P<direction>[NSEW])(?P<minutes>\d+(?:\.\d+)?))?\s*",
    re.IGNORECASE,
)


def parse_geo_coordinate(
    value: Any, *, axis: Literal["latitude", "longitude"]
) -> Optional[float]:
    """Return None only for absent values; reject malformed or out-of-range input."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"无效的{axis}坐标")
    direction = ""
    if isinstance(value, (int, float)):
        decimal = float(value)
    else:
        match = _COORDINATE.fullmatch(str(value))
        if match is None:
            raise ValueError(f"无效的{axis}坐标")
        degrees = float(match["degrees"])
        direction = (match["direction"] or "").upper()
        minutes = float(match["minutes"] or "0")
        if minutes >= 60:
            raise ValueError("坐标分数须小于 60")
        if direction:
            decimal = abs(degrees) + minutes / 60
            if direction in {"S", "W"}:
                decimal = -decimal
            if degrees < 0 and direction in {"N", "E"}:
                raise ValueError("坐标正负号与方向不一致")
        else:
            decimal = degrees
    limit = 90 if axis == "latitude" else 180
    if direction and direction not in ("NS" if axis == "latitude" else "EW"):
        raise ValueError(f"坐标方向与{axis}不一致")
    if not math.isfinite(decimal) or not -limit <= decimal <= limit:
        raise ValueError(f"{axis}坐标须在 {-limit} 到 {limit} 之间")
    return decimal
