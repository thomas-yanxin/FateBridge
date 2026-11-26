"""Lossless TT points, distinct from rounded nominal UTC-boundary labels."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction

from fatebridge.utils.civil_time import utc_calendar


@dataclass(frozen=True)
class TTInstant:
    """An explicitly exact numerical TT point; precision is not accuracy.

    ``from_float`` preserves the IEEE value, not the unrounded date that may
    have produced it. ``from_parts`` preserves both inputs without adding
    them at a large JD. ``from_utc`` retains the supplied civil microsecond
    and explicit atomic-offset assumption without a float intermediate.
    """

    days: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.days, Fraction):
            raise TypeError("TTInstant requires an exact Fraction of TT days")

    @classmethod
    def from_float(cls, jd_tt: float) -> TTInstant:
        if isinstance(jd_tt, bool) or not math.isfinite(jd_tt):
            raise ValueError("TT point must be finite and numeric")
        return cls(Fraction(jd_tt))

    @classmethod
    def from_parts(cls, day: float, fraction: float) -> TTInstant:
        return cls(cls.from_float(day).days + cls.from_float(fraction).days)

    @classmethod
    def from_value(cls, value: float | TTInstant) -> TTInstant:
        """Normalize a scalar boundary without manufacturing lost precision."""
        return value if isinstance(value, TTInstant) else cls.from_float(value)

    @classmethod
    def from_utc(
        cls, moment: datetime, *, tai_minus_utc_seconds: int | Fraction
    ) -> TTInstant:
        """Encode an aware calendar instant under a caller-declared offset.

        This constructor does not validate an offset table or predict leap
        seconds. Python datetime cannot encode second60. Callers must choose
        and disclose their policy; arbitrary defaults are not supplied here.
        The normalized UTC label may lie beyond datetime's calendar bounds.
        """
        calendar = utc_calendar(moment)
        if isinstance(tai_minus_utc_seconds, bool) or not isinstance(
            tai_minus_utc_seconds, (int, Fraction)
        ):
            raise TypeError("Atomic offset must be exact integer or Fraction seconds")
        return cls(
            calendar.julian_day_exact()
            + (tai_minus_utc_seconds + Fraction(4023, 125)) / 86400
        )

    def as_float(self) -> float:
        """Lossy interoperability only; exact comparisons must use days."""
        return float(self.days)

    def shifted_by(self, days: float | Fraction) -> TTInstant:
        """Retain a supplied local offset before any absolute-JD rounding."""
        return TTInstant(self.days + Fraction(days))

    def as_parts(self) -> tuple[float, float]:
        """A scalar high part and its rounded exact residual for native APIs.

        The Fraction remains the authoritative point. This adapter does not
        claim that two binary64 values can represent every rational exactly.
        """
        high = float(self.days)
        return high, float(self.days - Fraction(high))
