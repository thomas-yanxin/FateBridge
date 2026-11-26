"""Host calendar choice is separate from birth timezone and mansion method."""

from __future__ import annotations

from typing import Literal

SukuyoCalendarBasis = Literal[
    "chinese_hko_utc08",
    "japanese_hutime_1002_1_utc09",
    "japanese_naoj_historical_utc09",
]
DEFAULT_CALENDAR_BASIS = "chinese_hko_utc08"
JAPANESE_CALENDAR_BASIS = "japanese_hutime_1002_1_utc09"
HISTORICAL_CALENDAR_BASIS = "japanese_naoj_historical_utc09"
JAPANESE_CALENDAR_BASES = frozenset(
    {JAPANESE_CALENDAR_BASIS, HISTORICAL_CALENDAR_BASIS}
)
