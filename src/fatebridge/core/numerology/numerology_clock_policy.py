"""Shared definitions, independent of the domain entry point."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time

CLOCK_POLICY_ID = "numerology_explicit_longitude_clock_v1"


@dataclass(frozen=True, slots=True, kw_only=True)
class ParsedBirthClock:
    supplied_text: str
    normalized_clock: str
    has_explicit_seconds: bool
    fractional_digits: int


def parse_birth_clock(value: object) -> ParsedBirthClock:
    """Parse a supplied local clock and retain the components actually given."""
    if not isinstance(value, str):
        raise ValueError("河洛与参评需要明确的出生时间，不能补默认零点。")
    else:
        supplied_text = value.strip()
    match = re.fullmatch(
        r"([0-9]{1,2}):([0-9]{1,2})(?::([0-9]{1,2})(\.[0-9]{1,6})?)?", supplied_text
    )
    if match is None:
        raise ValueError(
            "出生时间须为已知的HH:MM或HH:MM:SS；未知时刻不能补零点，时区请单独提供。"
        )
    else:
        hour_text, minute_text, second_text, fraction_text = match.groups()
    hour, minute, second = int(hour_text), int(minute_text), int(second_text or 0)
    time(hour, minute, second)
    return ParsedBirthClock(
        supplied_text=supplied_text,
        normalized_clock=f"{hour:02d}:{minute:02d}:{second:02d}{fraction_text or ''}",
        has_explicit_seconds=second_text is not None,
        fractional_digits=len(fraction_text) - 1 if fraction_text is not None else 0,
    )


def require_birth_clock(value: object) -> str:
    """Return the normalized calculation clock for the shared input policy."""
    return parse_birth_clock(value).normalized_clock
