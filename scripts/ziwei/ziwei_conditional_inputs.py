"""Explicit synthetic clocks for conditional lunar-rule audits.

The 1 January clock supplies an age-ordinal premise only. It is not asserted to
reconstruct the lunar natal placement or establish a historical age boundary.
Public service tests supply the actual birth seed instead.
"""

from datetime import datetime

from fatebridge.core.metaphysics.common import MetaphysicsSeed


def synthetic_birth_clock(year: int) -> MetaphysicsSeed:
    clock = datetime(year, 1, 1)
    return MetaphysicsSeed(
        input_datetime=clock,
        corrected_datetime=clock,
        timezone="Asia/Shanghai",
        longitude=None,
        applied_true_solar=False,
        total_correction_minutes=0,
        pillars={},
        calendar_context={},
    )
