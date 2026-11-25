"""Taiyi entry point for source-scoped year/month/day/hour calculations."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.taiyi_day import build_key_day_board
from fatebridge.core.metaphysics.taiyi_periods import build_period_board
from fatebridge.core.metaphysics.taiyi_year import build_year_board


def build_taiyi_board(
    seed: MetaphysicsSeed,
    gender: str,
    *,
    calculation_mode: str = "year",
    hour_profile: str | None = None,
    month_profile: str | None = None,
    year_profile: str | None = None,
    shiji_profile: str | None = None,
) -> dict[str, Any]:
    """Build the selected year/month/day/hour frame with explicit source profiles."""

    if year_profile is not None and calculation_mode != "year":
        raise ValueError("year_profile仅用于year年计")

    if month_profile is not None and calculation_mode != "month":
        raise ValueError("month_profile仅用于month月计")

    if hour_profile is not None and calculation_mode != "hour":
        raise ValueError("hour_profile仅用于hour时计，不能用于年计、月计或日计")
    if calculation_mode == "year":
        return build_year_board(seed, gender, year_profile, shiji_profile=shiji_profile)
    if calculation_mode == "day":
        return build_key_day_board(seed, gender, shiji_profile=shiji_profile)

    return build_period_board(
        seed,
        gender,
        calculation_mode,
        hour_profile,
        month_profile,
        shiji_profile=shiji_profile,
    )
