"""Shared BaZi timing facade for cross-domain callers (canonical owner: fatebridge.core.bazi.timing)."""

from fatebridge.core.almanac import (
    get_bazi_month_boundaries,
    get_bazi_year,
)
from fatebridge.core.bazi.timing import (
    DEFAULT_DAYUN_PERIODS,
    DayunCalendarOffset,
    DayunStartDetails,
    DayunStartResolution,
    DayunTimeline,
    TimingAnalysis,
    calculate_dayun_sequence,
    dayun_is_forward,
    dayun_wall_year_preimages,
    resolve_dayun_calendar_boundary,
)

__all__ = [
    "DEFAULT_DAYUN_PERIODS",
    "DayunCalendarOffset",
    "DayunStartDetails",
    "DayunStartResolution",
    "DayunTimeline",
    "TimingAnalysis",
    "calculate_dayun_sequence",
    "dayun_is_forward",
    "dayun_wall_year_preimages",
    "get_bazi_month_boundaries",
    "get_bazi_year",
    "resolve_dayun_calendar_boundary",
]
