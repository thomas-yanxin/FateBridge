"""Synthetic age offsets for independent civil-calendar policy controls."""

from datetime import datetime
from fractions import Fraction

from fatebridge.core.almanac import SolarTerm, localize_datetime
from fatebridge.core.timing import DayunStartResolution
from fatebridge.utils.civil_time import CivilPoint, ZonedCalendar, utc_calendar
from fatebridge.utils.timezones import parse_timezone_name


def synthetic_dayun_start(
    birth: datetime,
    zone: str,
    elapsed_seconds: float,
    *,
    forward: bool,
) -> DayunStartResolution:
    """Provide a typed offset fixture without solving an astronomical event.

    Only the offset is synthetic. Tests retain their original independent IANA
    inputs and expected instants; this fixture supplies no physical solar claim.
    """
    local = localize_datetime(birth, zone)
    days = Fraction(elapsed_seconds) / 86400
    point = CivilPoint(
        utc_calendar(local).julian_day_exact() + (days if forward else -days)
    )
    term = SolarTerm(
        "synthetic_calendar_offset",
        ZonedCalendar(point.as_calendar(), parse_timezone_name(zone)),
        resolution_provider="synthetic_calendar_policy_control",
        civil_point=point,
    )
    return DayunStartResolution(local, term, forward, "甲", days)
