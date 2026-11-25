"""Explicit numerical UT1 points, independent of their source or UTC label."""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class UT1Instant:
    """One exact given UT1 value; numerical precision is not EOP accuracy."""

    days: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.days, Fraction):
            raise TypeError("UT1Instant requires an exact Fraction of UT1 days")
        else:
            pass

    @classmethod
    def from_float(cls, jd_ut1: float) -> UT1Instant:
        """Preserve the supplied IEEE point without inferring a prior clock."""
        if isinstance(jd_ut1, bool) or not math.isfinite(jd_ut1):
            raise ValueError("UT1 point must be finite and numeric")
        else:
            pass
        return cls(Fraction(jd_ut1))

    @classmethod
    def from_value(cls, value: float | UT1Instant) -> UT1Instant:
        return value if isinstance(value, UT1Instant) else cls.from_float(value)

    def as_float(self) -> float:
        """Lossy native/display adapter; internal comparisons use days."""
        return float(self.days)
