"""Lossless TT points, distinct from rounded nominal UTC-boundary labels."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction

_JD_UNIX = Fraction(4881175, 2)
_MICROSECONDS_PER_DAY = 86_400_000_000
_UNIX = datetime(1970, 1, 1, tzinfo=timezone.utc)


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
    def from_utc(
        cls, moment: datetime, *, tai_minus_utc_seconds: int | Fraction
    ) -> TTInstant:
        """Encode an actual UTC datetime under a caller-declared offset.

        This constructor does not validate an offset table or predict leap
        seconds. Python datetime cannot encode second60. Callers must choose
        and disclose their policy; arbitrary defaults are not supplied here.
        """
        if moment.utcoffset() is None:
            raise ValueError("UTC encoding requires a timezone-aware instant")
        if isinstance(tai_minus_utc_seconds, bool) or not isinstance(
            tai_minus_utc_seconds, (int, Fraction)
        ):
            raise TypeError("Atomic offset must be exact integer or Fraction seconds")
        elapsed = moment.astimezone(timezone.utc) - _UNIX
        micros = (
            elapsed.days * _MICROSECONDS_PER_DAY
            + elapsed.seconds * 1_000_000
            + elapsed.microseconds
        )
        return cls(
            _JD_UNIX
            + Fraction(micros, _MICROSECONDS_PER_DAY)
            + (tai_minus_utc_seconds + Fraction(4023, 125)) / 86400
        )

    def as_float(self) -> float:
        """Lossy interoperability only; exact comparisons must use days."""
        return float(self.days)
