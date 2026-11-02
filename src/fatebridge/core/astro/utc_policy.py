"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any, Dict, cast


@lru_cache(maxsize=1)
def leap_table() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(
            files("fatebridge.data")
            .joinpath("knowledge/western-leap-seconds.json")
            .read_text(encoding="utf-8")
        ),
    )


def default_delta_t_flag(julian_day_ut1: float, swieph_flag: int) -> int:
    """One default TT policy for physical clocks and rotation adapters.

    Before1960 the civil forward path delegates to Swiss's historical UT1
    convention, which uses -1. Atomic/drifting UTC is handled explicitly from
    1960, with the existing SWIEPH model used for the modeled UT1 relation.
    A selected C04 source supplies its own TT and does not use this policy.
    """
    return -1 if julian_day_ut1 < 2436934.5 else swieph_flag
