"""Actual civil-clock selection receipt; no new calendar or divination rule."""

from __future__ import annotations

from typing import Any

from dateutil import tz

from fatebridge.core.almanac import localize_datetime
from fatebridge.utils.civil_clock import format_utc_offset, utc_instant
from fatebridge.utils.timezones import timezone_rules_metadata, validate_local_clock

from .common import MetaphysicsSeed


def validate_seed_civil_clock(seed: MetaphysicsSeed) -> None:
    """A selected aware instant can repeat; a nonexistent wall label cannot.

    Public seed builders validate bare clocks or resolve explicit offsets first.
    Keep the bare-clock guard for direct domain callers too. Reapplying its fold
    rejection to an already selected aware instant would discard that selection.
    """
    # Check an aware source label before zone conversion can normalize a fake
    # gap label into a different, valid wall time. Fixed-offset instants exist.
    if seed.input_datetime.utcoffset() is not None and not tz.datetime_exists(
        seed.input_datetime
    ):
        validate_local_clock(seed.input_datetime)
    local = localize_datetime(seed.input_datetime, seed.timezone)
    if seed.input_datetime.utcoffset() is None or not tz.datetime_exists(local):
        validate_local_clock(local)


def civil_clock_resolution(
    seed: MetaphysicsSeed, declared_offset: str
) -> dict[str, Any]:
    """Read the instant already validated by the shared seed builder once."""
    offset = seed.input_datetime.utcoffset()
    if offset is None:
        raise ValueError("太乙偏移回执须使用已消歧的民用实际时刻")
    return {
        "method": "explicit_input_offset_checked_against_named_zone",
        "timezone": seed.timezone,
        "wall_datetime": seed.input_datetime.replace(tzinfo=None).isoformat(),
        "input_utc_offset": declared_offset,
        "resolved_utc_offset": format_utc_offset(offset),
        "fold": seed.input_datetime.fold,
        "instant_utc": utc_instant(seed.input_datetime).isoformat(),
        "timezone_rules": timezone_rules_metadata(seed.timezone),
        "scope": "以运行环境时区规则核对明确偏移，保留命名时区与民用实际瞬间。回拨两次钟时不猜选；这不是原典历法或古代钟制认证。",
    }
