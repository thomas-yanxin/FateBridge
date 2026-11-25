"""Shared response text, pillar representation and JSON formatting."""

import json
from datetime import datetime

from pydantic import JsonValue

from fatebridge.utils.civil_time import NominalClockLabel


def format_birth_datetime_display(
    birth_datetime: datetime | NominalClockLabel,
    include_minutes: bool = False,
    *,
    include_seconds: bool = False,
) -> str:
    """Format birth datetime for user-facing API responses."""
    label = (
        NominalClockLabel.from_local_datetime(birth_datetime)
        if isinstance(birth_datetime, datetime)
        else birth_datetime
    )
    year, month, day = label.date_parts
    hour, minute, second, microsecond = label.time_parts
    display = f"{year:04d}年{month:02d}月{day:02d}日 {hour:02d}时"
    if include_minutes or include_seconds:
        display += f"{minute:02d}分"
    if include_seconds:
        fraction = f".{microsecond:06d}" if microsecond else ""
        display += f"{second:02d}{fraction}秒"
    return display


def format_clock_datetime(
    moment: datetime, *, include_seconds: bool | None = None
) -> str:
    """Retain computed subminute values without changing old whole-minute labels."""
    if include_seconds is False:
        return moment.strftime("%Y-%m-%d %H:%M")
    timespec = (
        "microseconds"
        if moment.microsecond
        else "seconds" if include_seconds or moment.second else "minutes"
    )
    return moment.isoformat(sep=" ", timespec=timespec)


def create_pillar_dict(
    pillars: dict[str, tuple[str, str]],
) -> dict[str, dict[str, str]]:
    """Name the stem and branch of each of the four pillars."""
    return {
        "year": {"stem": pillars["year"][0], "branch": pillars["year"][1]},
        "month": {"stem": pillars["month"][0], "branch": pillars["month"][1]},
        "day": {"stem": pillars["day"][0], "branch": pillars["day"][1]},
        "hour": {"stem": pillars["hour"][0], "branch": pillars["hour"][1]},
    }


def format_json_response(
    data: JsonValue,
    *,
    compact: bool = True,
) -> str:
    """Serialize JSON with Unicode text and the chosen spacing."""
    if compact:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(data, ensure_ascii=False, indent=2)
