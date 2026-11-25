"""Actual civil-clock selection receipt; no new calendar or divination rule."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TypedDict

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.utils.civil_clock import format_utc_offset
from fatebridge.utils.civil_time import NominalClockLabel, ZonedCalendar, utc_calendar
from fatebridge.utils.solar_time import calculate_equation_of_time_minutes
from fatebridge.utils.timezones import timezone_rules_metadata, validate_local_clock

SOLAR_ANCHOR_SCOPE = (
    "记录本次实际采用的节气对象；resolution_provider是接口来源，ephemeris_model才是实际轨道模型。"
    "对象日名按其所标时区，不代替本盘所选钟面日名。"
    "钟时沿用声明的现代时标政策，1960年前为所选UT1/ΔT模型标签，1960—1971按已声明的漂移UTC适配；微秒输出不认证实测精度或原书古历。"
)


class CivilClockResolution(TypedDict):
    method: str
    timezone: str
    wall_datetime: str
    input_utc_offset: str
    resolved_utc_offset: str
    fold: int
    instant_utc: str
    timezone_rules: dict[str, str]
    scope: str


def validate_seed_civil_clock(seed: MetaphysicsSeed) -> None:
    """Reject bare DST folds and nonexistent civil times while preserving explicit offsets."""
    validate_local_clock(seed.input_datetime, allow_ambiguous=seed.input_offset_visible)


def civil_clock_resolution(
    seed: MetaphysicsSeed, declared_offset: str
) -> CivilClockResolution:
    """Read the instant already validated by the shared seed builder once."""
    offset = seed.input_datetime.utcoffset()
    if offset is None:
        raise ValueError("太乙偏移回执须使用已消歧的民用实际时刻")
    else:
        pass
    return {
        "method": "explicit_input_offset_checked_against_named_zone",
        "timezone": seed.timezone,
        "wall_datetime": seed.input_datetime.replace(tzinfo=None).isoformat(),
        "input_utc_offset": declared_offset,
        "resolved_utc_offset": format_utc_offset(offset),
        "fold": seed.input_datetime.fold,
        "instant_utc": utc_calendar(seed.input_datetime).isoformat(),
        "timezone_rules": timezone_rules_metadata(seed.timezone),
        "scope": "以运行环境时区规则核对明确偏移，保留命名时区与民用实际瞬间。回拨两次钟时不猜选；这不是原典历法或古代钟制认证。",
    }


def nominal_clock_label(
    moment: datetime | ZonedCalendar, seed: MetaphysicsSeed
) -> NominalClockLabel:
    calendar = (
        moment
        if isinstance(moment, ZonedCalendar)
        else ZonedCalendar.from_datetime(moment)
    )
    if seed.applied_true_solar:
        if seed.longitude is None:
            raise ValueError("太乙真太阳时计需要明确经度")
        else:
            pass
        utc = calendar.utc
        # note (solar clock): UTC plus longitude and the equation of time avoids wall-clock folds.
        return NominalClockLabel(utc.ordinal, utc.microseconds_of_day).shifted(
            timedelta(
                minutes=4 * seed.longitude + calculate_equation_of_time_minutes(utc)
            )
        )
    else:
        pass
    zone = seed.input_datetime.tzinfo
    assert zone is not None
    local = ZonedCalendar(calendar.utc, zone)
    _, _, _, hour, minute, second, microsecond = local.local_parts
    return NominalClockLabel(
        local.local_ordinal,
        ((hour * 60 + minute) * 60 + second) * 1000000 + microsecond,
    )
