"""Independent calendar arithmetic for testing serialized timing evidence."""

from datetime import datetime, timedelta, timezone
from fractions import Fraction

from fatebridge.utils.civil_time import CivilPointRecord


def seconds_from_boundary(moment: datetime, point: CivilPointRecord) -> Fraction:
    epoch = datetime(1, 1, 1, tzinfo=timezone.utc)
    microseconds = (moment - epoch) // timedelta(microseconds=1)
    event_day = Fraction(int(point["numerator"]), int(point["denominator"]))
    return (
        Fraction(microseconds, 1_000_000) - (event_day - Fraction(3442851, 2)) * 86400
    )
