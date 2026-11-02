"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

import re
from datetime import time

CLOCK_POLICY_ID = "numerology_explicit_longitude_clock_v1"


def require_birth_clock(value: object) -> str:
    """Normalize a supplied local clock, never invent midnight for a blank.

    Timezone belongs in the separate zone field. Preserve fractional seconds
    when explicitly supplied rather than assigning precision to missing input.
    """
    if not isinstance(value, str):
        raise ValueError("河洛与参评需要明确的出生时间，不能补默认零点。")
    match = re.fullmatch(
        r"([0-9]{1,2}):([0-9]{1,2})(?::([0-9]{1,2})(\.[0-9]{1,6})?)?", value.strip()
    )
    if match is None:
        raise ValueError(
            "出生时间须为已知的HH:MM或HH:MM:SS；未知时刻不能补零点，时区请单独提供。"
        )
    hour, minute, second = (int(match[i] or 0) for i in (1, 2, 3))
    time(hour, minute, second)  # Reject out-of-range clocks, including 24:00.
    return f"{hour:02d}:{minute:02d}:{second:02d}{match[4] or ''}"
