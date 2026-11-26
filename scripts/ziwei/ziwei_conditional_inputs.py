"""Explicit synthetic clocks for conditional lunar-rule audits.

The 1 January clock supplies an age-ordinal premise only. It is not asserted to
reconstruct the lunar natal placement or establish a historical age boundary.
Public service tests supply the actual birth seed instead.
"""

from datetime import datetime
from pathlib import Path

from fatebridge.core.almanac import localize_datetime
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.utils.civil_time import NominalClockLabel

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/data/ziwei_independent"


def synthetic_birth_clock(year: int) -> MetaphysicsSeed:

    clock = datetime(year, 1, 1)
    return MetaphysicsSeed(
        input_datetime=localize_datetime(clock, "Asia/Shanghai"),
        clock=NominalClockLabel.from_local_datetime(clock),
        timezone="Asia/Shanghai",
        longitude=None,
        applied_true_solar=False,
        total_correction_minutes=0,
        pillars={},
        calendar_context={},
        input_offset_visible=False,
    )


def synthetic_seed(
    year: int, month: int = 1, day: int = 1, hour: str = "子", leap: bool = False
) -> MetaphysicsSeed:
    """Synthetic lunar rule inputs, not claimed historical solar conversions."""

    return MetaphysicsSeed(
        input_datetime=localize_datetime(datetime(year, 1, 1), "Asia/Shanghai"),
        clock=NominalClockLabel.from_local_datetime(datetime(year, 1, 1)),
        timezone="Asia/Shanghai",
        longitude=None,
        applied_true_solar=False,
        total_correction_minutes=0,
        pillars={"day": ("甲", "子"), "hour": ("甲", hour)},
        calendar_context={
            "lunar_calendar": {
                "year": year,
                "month": month,
                "day": day,
                "is_leap_month": leap,
            }
        },
        input_offset_visible=False,
    )
