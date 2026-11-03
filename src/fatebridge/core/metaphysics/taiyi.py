"""Taiyi entry point for source-scoped year/month/day/hour calculations."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .common import MetaphysicsSeed


def build_taiyi_board(
    seed: MetaphysicsSeed,
    gender: str,
    *,
    calculation_mode: str = "year",
    hour_profile: Optional[str] = None,
    month_profile: Optional[str] = None,
    year_profile: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the selected year/month/day/hour frame with explicit source profiles."""
    from .taiyi_year import build_year_board

    if year_profile is not None and calculation_mode != "year":
        raise ValueError("year_profile仅用于year年计")

    if month_profile is not None and calculation_mode != "month":
        raise ValueError("month_profile仅用于month月计")

    if hour_profile is not None and calculation_mode != "hour":
        raise ValueError("hour_profile仅用于hour时计，不能用于年计、月计或日计")
    if calculation_mode == "year":
        return build_year_board(seed, gender, year_profile)
    if calculation_mode == "day":
        from .taiyi_day import build_key_day_board

        return build_key_day_board(seed, gender)
    from .taiyi_periods import build_period_board

    return build_period_board(
        seed, gender, calculation_mode, hour_profile, month_profile
    )
