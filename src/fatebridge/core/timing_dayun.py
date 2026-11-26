"""Dayun direction, nominal conversion, and civil boundary rules."""

import math
from calendar import isleap
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import Literal, TypedDict

from dateutil.relativedelta import relativedelta
from dateutil.tz import resolve_imaginary
from pydantic import JsonValue
from typing_extensions import NotRequired

from fatebridge.core.almanac import SolarTerm, localize_datetime
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.civil_time import utc_calendar
from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS
from fatebridge.utils.timezones import require_defined_gap_offsets, validate_local_clock


class DayunStartDetails(TypedDict):
    forward_direction: bool
    year_stem: str
    reference_term: dict[str, JsonValue]
    reference_term_resolution: str
    days_to_boundary: float
    start_age_precise: float
    start_age_unrounded: float
    start_age_rounded: int
    elapsed_seconds: float
    elapsed_scale: Literal["nominal_utc_label_seconds"]
    leap_second_policy: Literal["not_counted"]


class DayunCalendarOffset(TypedDict):
    years: int
    months: int
    days: int
    microseconds: int


@dataclass(frozen=True)
class DayunStartResolution:
    """The selected source point, before its public scalar details adapter."""

    birth: datetime
    target_term: SolarTerm
    forward_direction: bool
    year_stem: str
    nominal_days: Fraction

    def to_details(self) -> DayunStartDetails:
        """Keep float displays; apply the integer policy to the retained span."""
        delta_days = float(self.nominal_days)
        start_age_unrounded = delta_days / 3
        start_age_precise = round(start_age_unrounded, 2)
        return {
            "forward_direction": self.forward_direction,
            "year_stem": self.year_stem,
            "reference_term": self.target_term.as_dict(),
            "reference_term_resolution": self.target_term.resolution_provider,
            "days_to_boundary": round(delta_days, 4),
            "start_age_precise": start_age_precise,
            "start_age_unrounded": start_age_unrounded,
            # note (dayun): Use the retained span because float display can erase a positive remainder.
            "start_age_rounded": max(1, math.ceil(self.nominal_days / 3)),
            "elapsed_seconds": delta_days * 86400,
            "elapsed_scale": "nominal_utc_label_seconds",
            "leap_second_policy": "not_counted",
        }

    def calendar_wall_offset(self) -> tuple[datetime, DayunCalendarOffset]:
        """Add the source span to the civil birth clock after one quantization."""
        # note (dayun): Convert the retained span before the single microsecond quantization.
        nominal_us = round(self.nominal_days * 86400 * 120 * 1_000_000)
        day_us = 86400 * 1_000_000
        years, remainder = divmod(nominal_us, 360 * day_us)
        months, remainder = divmod(remainder, 30 * day_us)
        days, remainder = divmod(remainder, day_us)
        wall_birth = self.birth.replace(tzinfo=None)
        start_wall = wall_birth + relativedelta(
            years=years, months=months, days=days, microseconds=remainder
        )
        offset: DayunCalendarOffset = {
            "years": years,
            "months": months,
            "days": days,
            "microseconds": remainder,
        }
        return start_wall, offset


def dayun_wall_year_preimages(
    boundary_wall: datetime, year_offset: int
) -> tuple[datetime, ...]:
    """Invert decade year addition, retaining both leap-day preimages."""
    if boundary_wall.tzinfo is not None:
        raise ValueError("大运年份逆像需要未附民用时区的钟面标签")
    year = boundary_wall.year - year_offset
    if not 1 <= year <= 9999:
        return ()
    try:
        targets = [boundary_wall.replace(year=year)]
    except ValueError:
        return ()
    if (
        boundary_wall.month == 2
        and boundary_wall.day == 28
        and not isleap(boundary_wall.year)
        and isleap(year)
    ):
        targets.append(boundary_wall.replace(year=year, day=29))
    return tuple(targets)


def resolve_dayun_calendar_boundary(
    birth: datetime, start_wall: datetime, year_offset: int, timezone_name: str
) -> tuple[datetime, bool]:
    """Shared existing year-clipping/fold policy for timelines and inverses."""
    wall = start_wall + relativedelta(years=year_offset)
    local = localize_datetime(wall, timezone_name).replace(fold=0)
    require_defined_gap_offsets(local, clock_label="交运边界")
    resolved = localize_datetime(resolve_imaginary(local), timezone_name)
    birth_point = utc_calendar(birth).julian_day_exact()
    if year_offset == 0 and utc_calendar(resolved).julian_day_exact() < birth_point:
        later = wall.replace(tzinfo=birth.tzinfo, fold=1)
        instant = utc_calendar(later).julian_day_exact()
        roundtrip = localize_datetime(later, timezone_name)
        if roundtrip.replace(tzinfo=None) != wall or instant < birth_point:
            raise ValueError("首运边界不能早于已确认的出生时刻")
        validate_local_clock(roundtrip, allow_ambiguous=True, clock_label="交运边界")
        return roundtrip, True
    validate_local_clock(resolved, allow_ambiguous=True, clock_label="交运边界")
    return resolved, False


class DayunAgeRange(TypedDict):
    start: float
    end: float


class DayunPeriod(TypedDict):
    period: int
    stem: str
    branch: str
    pillar: str
    age_range: DayunAgeRange
    start_at: NotRequired[str]
    end_at: NotRequired[str]


class DayunTimeline(TypedDict):
    method_id: Literal["three_days_one_year_calendar_v1"]
    timezone: str
    birth_at: str
    start_at: str
    start_details: DayunStartDetails
    calendar_offset: DayunCalendarOffset
    boundary_policy: str
    calendar_policy: str
    dst_policy: str
    reference_policy: str
    source: dict[str, str]
    scope: str
    periods: list[DayunPeriod]
    profile_id: NotRequired[str]


def dayun_is_forward(gender: str | None, year_stem: str) -> bool:
    """Derive the Dayun direction from the normalized gender and natal year stem."""
    is_yang_year = HEAVENLY_STEMS.index(year_stem) % 2 == 0
    canonical_gender = normalize_gender(gender)
    if canonical_gender not in ("男", "女"):
        raise ValueError(
            "大运方向需要明确性别（男/女）；请提供 gender，或显式传入 dayun_pillar。"
        )
    return canonical_gender == "男" if is_yang_year else canonical_gender == "女"


def calculate_dayun_sequence(
    month_pillar_stem: str,
    month_pillar_branch: str,
    gender: str | None,
    year_stem: str,
    periods: int = 8,
    start_age: float = 1.0,
) -> list[DayunPeriod]:
    """Generate ordered Dayun pillars and display ages from the natal month pillar."""
    direction = 1 if dayun_is_forward(gender, year_stem) else -1

    month_stem_index = HEAVENLY_STEMS.index(month_pillar_stem)
    month_branch_index = EARTHLY_BRANCHES.index(month_pillar_branch)

    dayun_sequence = []

    for period_index in range(periods):
        current_stem_index = (month_stem_index + direction * (period_index + 1)) % 10
        current_branch_index = (
            month_branch_index + direction * (period_index + 1)
        ) % 12

        dayun_stem = HEAVENLY_STEMS[current_stem_index]
        dayun_branch = EARTHLY_BRANCHES[current_branch_index]

        dayun_info: DayunPeriod = {
            "period": period_index + 1,
            "stem": dayun_stem,
            "branch": dayun_branch,
            "pillar": f"{dayun_stem}{dayun_branch}",
            "age_range": {
                "start": round(start_age + period_index * 10, 2),
                "end": round(start_age + (period_index + 1) * 10, 2),
            },
        }

        dayun_sequence.append(dayun_info)

    return dayun_sequence
