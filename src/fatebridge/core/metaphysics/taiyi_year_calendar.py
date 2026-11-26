"""Compatibility facade for taiyi historical year profiles."""

from fatebridge.core.metaphysics.taiyi.calendars import (
    DEFAULT_YEAR_PROFILE,
    HISTORICAL_YEAR_PROFILE,
    HISTORICAL_YEAR_PROFILES,
    QILIANG_YEAR_PROFILE,
    YEAR_PROFILES,
    TaiyiYearProfile,
    historical_month_table,
    historical_year_context,
)

__all__ = [
    "DEFAULT_YEAR_PROFILE",
    "HISTORICAL_YEAR_PROFILE",
    "HISTORICAL_YEAR_PROFILES",
    "QILIANG_YEAR_PROFILE",
    "TaiyiYearProfile",
    "YEAR_PROFILES",
    "historical_month_table",
    "historical_year_context",
]
