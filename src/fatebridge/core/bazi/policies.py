"""Pure BaZi policy type aliases (zero heavy dependencies)."""

from __future__ import annotations

from typing import Literal

ZiHourPolicy = Literal[
    "day_rollover_at_23",
    "night_zi_same_day_next_hour_stem",
    "night_zi_same_day_same_hour_stem",
]

ChangshengSchool = Literal[
    "fire_earth_same_palace",
    "water_earth_same_palace",
    "five_element_same_stage",
]

DutyProfile = Literal["sanming", "yuanhai", "6tail", "ditian"]

YearBoundaryPolicy = Literal["lichun", "gregorian"]
