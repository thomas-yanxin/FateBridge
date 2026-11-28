"""BaZi timing engine: Dayun (3天=1年), ChildLimit, 小运, 流年/流月/流日/流时, and full interactions."""

from __future__ import annotations

import math
from calendar import isleap
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from typing import Any, Literal, Mapping, TypedDict

from dateutil.relativedelta import relativedelta
from dateutil.tz import resolve_imaginary
from pydantic import JsonValue
from typing_extensions import NotRequired

from fatebridge.core.almanac import (
    BAZI_MONTH_START_TERMS,
    DEFAULT_TIMEZONE,
    SolarTerm,
    _solar_term_source_year,
    _solar_terms_for_context_year,
    elapsed_days_between,
    get_bazi_month_boundaries,
    get_bazi_month_context,
    get_bazi_year,
    get_day_ganzhi,
    get_solar_term_environment_key,
    get_solar_terms_for_year,
    localize_datetime,
    require_calculated_solar_term,
)
from fatebridge.core.bazi.calendar import (
    BaZiCalendar,
    ZiHourPolicy,
    resolve_bazi_effective_date,
)
from fatebridge.core.bazi.policies import YearBoundaryPolicy
from fatebridge.core.bazi.relations import (
    BRANCH_BREAKS,
    BRANCH_HIDDEN_COMBINATIONS,
    collect_target_branch_relations,
)
from fatebridge.core.bazi.shensha import timing_shensha
from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX
from fatebridge.utils.birth_input import normalize_gender
from fatebridge.utils.civil_time import ZonedCalendar, utc_calendar
from fatebridge.utils.data import (
    BRANCH_COMBINATIONS,
    BRANCH_CONFLICTS,
    BRANCH_HARMS,
    BRANCH_HIDDEN_STEMS,
    BRANCH_SEASONAL_COMBINATIONS,
    BRANCH_SELF_PUNISHMENTS,
    BRANCH_THREE_PUNISHMENTS,
    BRANCH_TRIPLE_COMBINATIONS,
    DESTRUCTION_CYCLE,
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    STEM_COMBINATIONS,
    STEM_ELEMENTS,
    TRIPLE_COMBINATION_PEAK,
    get_nayin,
    get_shishen,
)
from fatebridge.utils.timezones import (
    is_unspecified_local_time,
    require_defined_gap_offsets,
    timezone_transition_candidates,
    validate_local_clock,
)

DEFAULT_DAYUN_PERIODS = 12
_STEM_COMB_SETS = {frozenset((a, b)) for a, b, _ in STEM_COMBINATIONS}
_ORDER = ("year", "month", "day", "hour")


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


class ChildLimitCountdown(TypedDict):
    years: int
    months: int
    days: int
    hours: int
    minutes: int
    display: str
    start_at: str
    start_day_ganzhi: str


@dataclass(frozen=True)
class DayunStartResolution:
    """Selected Jie crossing and nominal 3-days-per-year span."""

    birth: datetime
    target_term: SolarTerm
    forward_direction: bool
    year_stem: str
    nominal_days: Fraction

    def to_details(self) -> DayunStartDetails:
        delta_days = float(self.nominal_days)
        start_age_unrounded = delta_days / 3
        return {
            "forward_direction": self.forward_direction,
            "year_stem": self.year_stem,
            "reference_term": self.target_term.as_dict(),
            "reference_term_resolution": self.target_term.resolution_provider,
            "days_to_boundary": round(delta_days, 4),
            "start_age_precise": round(start_age_unrounded, 2),
            "start_age_unrounded": start_age_unrounded,
            "start_age_rounded": max(1, math.ceil(self.nominal_days / 3)),
            "elapsed_seconds": delta_days * 86400,
            "elapsed_scale": "nominal_utc_label_seconds",
            "leap_second_policy": "not_counted",
        }

    def calendar_wall_offset(self) -> tuple[datetime, DayunCalendarOffset]:
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

    def child_limit_countdown(self, start_at: datetime) -> ChildLimitCountdown:
        _, offset = self.calendar_wall_offset()
        hours, rem = divmod(offset["microseconds"], 3600 * 1_000_000)
        minutes = round(rem / (60 * 1_000_000))
        if minutes == 60:
            hours += 1
            minutes = 0
        display = f"{offset['years']}年{offset['months']}月{offset['days']}日"
        if hours or minutes:
            display += f"{hours}小时{minutes}分"
        return {
            "years": offset["years"],
            "months": offset["months"],
            "days": offset["days"],
            "hours": hours,
            "minutes": minutes,
            "display": display,
            "start_at": start_at.isoformat(),
            "start_day_ganzhi": get_day_ganzhi(
                start_at.year, start_at.month, start_at.day
            ),
        }


def dayun_wall_year_preimages(
    boundary_wall: datetime, year_offset: int
) -> tuple[datetime, ...]:
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
    nayin: str
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
    child_limit: ChildLimitCountdown
    boundary_policy: str
    periods: list[DayunPeriod]


def dayun_is_forward(gender: str | None, year_stem: str) -> bool:
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
    direction = 1 if dayun_is_forward(gender, year_stem) else -1
    month_stem_idx = HEAVENLY_STEMS.index(month_pillar_stem)
    month_branch_idx = EARTHLY_BRANCHES.index(month_pillar_branch)
    dayun_sequence: list[DayunPeriod] = []
    for idx in range(periods):
        stem = HEAVENLY_STEMS[(month_stem_idx + direction * (idx + 1)) % 10]
        branch = EARTHLY_BRANCHES[(month_branch_idx + direction * (idx + 1)) % 12]
        dayun_sequence.append(
            {
                "period": idx + 1,
                "stem": stem,
                "branch": branch,
                "pillar": f"{stem}{branch}",
                "nayin": get_nayin(stem, branch),
                "age_range": {
                    "start": round(start_age + idx * 10, 2),
                    "end": round(start_age + (idx + 1) * 10, 2),
                },
            }
        )
    return dayun_sequence


def calculate_xiaoyun_pillar(
    hour_pillar: tuple[str, str],
    gender: str | None,
    year_stem: str,
    nominal_age: int,
) -> dict[str, Any]:
    """Compute 小运 pillar for a given nominal age (1岁 = 时柱下一/上一柱)."""
    forward = dayun_is_forward(gender, year_stem)
    direction = 1 if forward else -1
    age_step = max(1, int(nominal_age))
    hour_stem_idx = HEAVENLY_STEMS.index(hour_pillar[0])
    hour_branch_idx = EARTHLY_BRANCHES.index(hour_pillar[1])
    stem = HEAVENLY_STEMS[(hour_stem_idx + direction * age_step) % 10]
    branch = EARTHLY_BRANCHES[(hour_branch_idx + direction * age_step) % 12]
    return {
        "nominal_age": age_step,
        "stem": stem,
        "branch": branch,
        "pillar": f"{stem}{branch}",
        "nayin": get_nayin(stem, branch),
        "direction": "顺行" if forward else "逆行",
    }


def calculate_xiaoyun_timeline(
    hour_pillar: tuple[str, str],
    gender: str | None,
    year_stem: str,
    start_age_rounded: int,
    birth_year: int,
) -> list[dict[str, Any]]:
    """Pre-Dayun 小运 sequence from nominal age 1 up to start_age_rounded."""
    count = max(1, start_age_rounded)
    rows: list[dict[str, Any]] = []
    for age in range(1, count + 1):
        entry = calculate_xiaoyun_pillar(hour_pillar, gender, year_stem, age)
        entry["year"] = birth_year + age - 1
        rows.append(entry)
    return rows


@lru_cache(maxsize=2048)
def _calculate_liuyue_cached(
    target_clock: ZonedCalendar,
    timezone_name: str,
    _solar_environment: tuple[Any, ...] = (),
) -> dict[str, Any]:
    local_target_date = target_clock.require_datetime()
    bazi_year = get_bazi_year(local_target_date, timezone_name)
    month_context = get_bazi_month_context(local_target_date, timezone_name)
    liuyue_stem, liuyue_branch = BaZiCalendar.calculate_month_pillar_by_branch(
        bazi_year, str(month_context["branch"])
    )
    stem_element, stem_polarity = STEM_ELEMENTS[liuyue_stem]
    return {
        "year": local_target_date.year,
        "month": local_target_date.month,
        "day": local_target_date.day,
        "analysis_datetime": local_target_date.strftime("%Y-%m-%d %H:%M:%S"),
        "bazi_year": bazi_year,
        "stem": liuyue_stem,
        "branch": liuyue_branch,
        "pillar": f"{liuyue_stem}{liuyue_branch}",
        "element": stem_element.value,
        "polarity": stem_polarity.value,
        "nayin": get_nayin(liuyue_stem, liuyue_branch),
        "solar_term_window": {
            "start_term": month_context["start_term"],
            "next_term": month_context["next_term"],
            "days_since_start": month_context["days_since_start"],
            "days_until_next": month_context["days_until_next"],
        },
    }


@lru_cache(maxsize=4096)
def _calculate_liushi_cached(
    civil_date: date,
    civil_hour: int,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
) -> dict[str, Any]:
    liushi_stem, liushi_branch = BaZiCalendar.calculate_hour_pillar(
        civil_date.year,
        civil_date.month,
        civil_date.day,
        civil_hour,
        zi_hour_policy=zi_hour_policy,
    )
    stem_element, stem_polarity = STEM_ELEMENTS[liushi_stem]
    return {
        "year": civil_date.year,
        "month": civil_date.month,
        "day": civil_date.day,
        "hour": civil_hour,
        "stem": liushi_stem,
        "branch": liushi_branch,
        "pillar": f"{liushi_stem}{liushi_branch}",
        "element": stem_element.value,
        "polarity": stem_polarity.value,
        "nayin": get_nayin(liushi_stem, liushi_branch),
        "shichen": liushi_branch,
    }


@lru_cache(maxsize=4096)
def _calculate_liuri_cached(
    target_clock: ZonedCalendar,
    timezone_name: str,
    zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    _solar_environment: tuple[Any, ...] = (),
) -> dict[str, Any]:
    local_target_date = target_clock.require_datetime()
    liuri_stem, liuri_branch = BaZiCalendar.calculate_day_pillar(
        local_target_date.year,
        local_target_date.month,
        local_target_date.day,
        hour=local_target_date.hour,
        zi_hour_policy=zi_hour_policy,
    )
    effective_year, effective_month, effective_day = resolve_bazi_effective_date(
        local_target_date.year,
        local_target_date.month,
        local_target_date.day,
        local_target_date.hour,
        zi_hour_policy=zi_hour_policy,
    )
    applied_late_zi_rollover = (
        effective_year != local_target_date.year
        or effective_month != local_target_date.month
        or effective_day != local_target_date.day
    )
    stem_element, stem_polarity = STEM_ELEMENTS[liuri_stem]
    month_context = get_bazi_month_context(local_target_date, timezone_name)
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return {
        "year": local_target_date.year,
        "month": local_target_date.month,
        "day": local_target_date.day,
        "analysis_datetime": local_target_date.strftime("%Y-%m-%d %H:%M:%S"),
        "effective_date": f"{effective_year:04d}-{effective_month:02d}-{effective_day:02d}",
        "late_zi_rollover_applied": applied_late_zi_rollover,
        "zi_hour_policy": zi_hour_policy,
        "stem": liuri_stem,
        "branch": liuri_branch,
        "pillar": f"{liuri_stem}{liuri_branch}",
        "element": stem_element.value,
        "polarity": stem_polarity.value,
        "nayin": get_nayin(liuri_stem, liuri_branch),
        "weekday": weekday_names[local_target_date.weekday()],
        "solar_term_window": {
            "start_term": month_context["start_term"],
            "next_term": month_context["next_term"],
            "days_since_start": month_context["days_since_start"],
            "days_until_next": month_context["days_until_next"],
        },
    }


def _format_solar_term_timestamp(term: SolarTerm) -> str:
    return (
        term.calendar.isoformat()
        if term.has_defined_local_clock
        else term.calendar.utc.isoformat()
    )


def _solar_year_window(
    solar_year: int, timezone_name: str = DEFAULT_TIMEZONE
) -> dict[str, str]:
    start_terms = {
        term.name: term for term in get_solar_terms_for_year(solar_year, timezone_name)
    }
    end_terms = {
        term.name: term
        for term in get_solar_terms_for_year(solar_year + 1, timezone_name)
    }
    start_lichun = start_terms["立春"]
    end_lichun = end_terms["立春"]
    require_calculated_solar_term(start_lichun)
    require_calculated_solar_term(end_lichun)
    return {
        "start_lichun": _format_solar_term_timestamp(start_lichun),
        "end_lichun": _format_solar_term_timestamp(end_lichun),
    }


def _copy_timing_info(info: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(info)


class TimingAnalysis:
    """Compute the Dayun timeline, 小运, and annual through hourly BaZi layers."""

    _dayun_wall_year_preimages = staticmethod(dayun_wall_year_preimages)
    _resolve_dayun_calendar_boundary = staticmethod(resolve_dayun_calendar_boundary)
    calculate_dayun_sequence = staticmethod(calculate_dayun_sequence)

    @staticmethod
    def resolve_dayun_start(
        birth_date: datetime,
        gender: str | None,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> DayunStartResolution:
        local_birth_date = localize_datetime(birth_date, timezone_name)
        bazi_year = get_bazi_year(local_birth_date, timezone_name)
        year_stem, _ = BaZiCalendar.calculate_year_pillar(bazi_year)
        forward_direction = dayun_is_forward(gender, year_stem)
        start_term, next_term, _, _ = get_bazi_month_boundaries(
            local_birth_date, timezone_name
        )
        target_term = next_term if forward_direction else start_term
        nominal_days = abs(
            target_term.point.day - utc_calendar(local_birth_date).julian_day_exact()
        )
        return DayunStartResolution(
            local_birth_date, target_term, forward_direction, year_stem, nominal_days
        )

    @staticmethod
    def calculate_dayun_start_details(
        birth_date: datetime,
        gender: str | None,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> DayunStartDetails:
        return TimingAnalysis.resolve_dayun_start(
            birth_date, gender, timezone_name
        ).to_details()

    @staticmethod
    def _dayun_calendar_wall_context(
        birth_date: datetime,
        gender: str | None,
        timezone_name: str,
    ) -> tuple[datetime, DayunStartDetails, datetime, DayunCalendarOffset]:
        resolution = TimingAnalysis.resolve_dayun_start(
            birth_date, gender, timezone_name
        )
        start_wall, offset = resolution.calendar_wall_offset()
        return resolution.birth, resolution.to_details(), start_wall, offset

    @staticmethod
    def calculate_dayun_timeline(
        birth_date: datetime,
        gender: str | None,
        month_pillar: tuple[str, str],
        timezone_name: str = DEFAULT_TIMEZONE,
        periods: int = DEFAULT_DAYUN_PERIODS,
    ) -> dict[str, Any]:
        resolution = TimingAnalysis.resolve_dayun_start(
            birth_date, gender, timezone_name
        )
        return dict(
            TimingAnalysis.build_dayun_timeline(
                resolution, gender, month_pillar, timezone_name, periods
            )
        )

    @staticmethod
    def build_dayun_timeline(
        resolution: DayunStartResolution,
        gender: str | None,
        month_pillar: tuple[str, str],
        timezone_name: str,
        periods: int = DEFAULT_DAYUN_PERIODS,
    ) -> DayunTimeline:
        birth = resolution.birth
        details = resolution.to_details()
        start_wall, calendar_offset = resolution.calendar_wall_offset()

        def civil_boundary(year_offset: int) -> datetime:
            resolved, _ = TimingAnalysis._resolve_dayun_calendar_boundary(
                birth, start_wall, year_offset, timezone_name
            )
            return resolved

        initial_boundary = civil_boundary(0)
        sequence = TimingAnalysis.calculate_dayun_sequence(
            month_pillar[0],
            month_pillar[1],
            gender,
            details["year_stem"],
            periods=periods,
            start_age=details["start_age_unrounded"],
        )
        for index, period in enumerate(sequence):
            period["start_at"] = (
                initial_boundary if index == 0 else civil_boundary(index * 10)
            ).isoformat()
            period["end_at"] = civil_boundary((index + 1) * 10).isoformat()
        return {
            "method_id": "three_days_one_year_calendar_v1",
            "timezone": timezone_name,
            "birth_at": birth.isoformat(),
            "start_at": initial_boundary.isoformat(),
            "start_details": details,
            "calendar_offset": calendar_offset,
            "child_limit": resolution.child_limit_countdown(initial_boundary),
            "boundary_policy": "start_inclusive_end_exclusive",
            "periods": sequence,
        }

    @staticmethod
    def calculate_liunian(
        target_year: int,
        *,
        moment: datetime | None = None,
        timezone_name: str = DEFAULT_TIMEZONE,
        year_boundary_policy: YearBoundaryPolicy = "lichun",
        include_solar_window: bool | None = None,
    ) -> dict[str, Any]:
        if year_boundary_policy == "gregorian":
            resolved_year = (
                localize_datetime(moment, timezone_name).year
                if moment is not None
                else target_year
            )
            boundary_basis = "gregorian_year_integer"
        elif moment is not None:
            resolved_year = get_bazi_year(moment, timezone_name)
            boundary_basis = "lichun_exact_moment"
        else:
            resolved_year = target_year
            boundary_basis = "lichun_solar_year"

        liunian_stem, liunian_branch = BaZiCalendar.calculate_year_pillar(resolved_year)
        stem_element, _ = STEM_ELEMENTS[liunian_stem]
        payload: dict[str, Any] = {
            "year": resolved_year,
            "stem": liunian_stem,
            "branch": liunian_branch,
            "pillar": f"{liunian_stem}{liunian_branch}",
            "element": stem_element.value,
            "nayin": get_nayin(liunian_stem, liunian_branch),
            "year_boundary_policy": year_boundary_policy,
            "year_boundary_basis": boundary_basis,
        }
        if include_solar_window is True or (
            include_solar_window is None and moment is not None
        ):
            payload["solar_year_window"] = _solar_year_window(
                resolved_year, timezone_name
            )
        return payload

    @staticmethod
    def calculate_liuyue(
        target_year: int,
        target_month: int,
        target_day: int = 1,
        timezone_name: str = DEFAULT_TIMEZONE,
        target_date: datetime | None = None,
    ) -> dict[str, Any]:
        local_target_date = localize_datetime(
            target_date or datetime(target_year, target_month, target_day),
            timezone_name,
        )
        return _copy_timing_info(
            _calculate_liuyue_cached(
                ZonedCalendar.from_datetime(local_target_date),
                timezone_name,
                get_solar_term_environment_key(year=local_target_date.year),
            )
        )

    @staticmethod
    def _next_supported_analysis_anchor(
        start_term: SolarTerm,
        timezone_name: str = DEFAULT_TIMEZONE,
        *,
        end_term: SolarTerm | None = None,
    ) -> datetime | None:
        local_moment = localize_datetime(start_term.moment, timezone_name)
        anchor = local_moment.replace(second=0, microsecond=0)
        start_day = start_term.point.day
        end_day = end_term.point.day if end_term is not None else None
        instant = local_moment.astimezone(timezone.utc)
        if end_term is not None and is_unspecified_local_time(local_moment):
            end = end_term.calendar.utc.as_datetime()
            zone = local_moment.tzinfo
            assert zone is not None
            if end is not None:
                cuts = timezone_transition_candidates(zone, instant, end)
                if cuts is not None:
                    reopened = next(
                        (
                            local
                            for cut in cuts
                            if not is_unspecified_local_time(
                                local := cut.astimezone(zone)
                            )
                        ),
                        None,
                    )
                    if reopened is None:
                        return None
                    anchor = reopened.replace(second=0, microsecond=0)
                    if anchor != reopened:
                        anchor += timedelta(minutes=1)
        while True:
            try:
                validate_local_clock(anchor)
            except ValueError:
                anchor += timedelta(minutes=1)
                continue
            anchor_day = utc_calendar(anchor).julian_day_exact()
            if end_day is not None and anchor_day >= end_day:
                return None
            if anchor_day > start_day:
                return anchor
            anchor += timedelta(minutes=1)

    @staticmethod
    def calculate_liuyue_timeline(
        target_year: int,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> list[dict[str, Any]]:
        current_year_terms = [
            term
            for term in get_solar_terms_for_year(target_year, timezone_name)
            if term.name in BAZI_MONTH_START_TERMS
        ]
        next_year_terms = _solar_terms_for_context_year(
            target_year + 1,
            timezone_name,
            _solar_term_source_year(target_year + 1, target_year),
            term_index=0,
        )
        timeline: list[dict[str, Any]] = []
        for index, start_term in enumerate(current_year_terms):
            next_term = (
                current_year_terms[index + 1]
                if index + 1 < len(current_year_terms)
                else next_year_terms[0]
            )
            require_calculated_solar_term(start_term)
            require_calculated_solar_term(next_term)
            start = start_term.as_dict()
            end = next_term.as_dict()
            window: dict[str, str | float] = {
                "days": round(
                    elapsed_days_between(start_term.point, next_term.point), 4
                )
            }
            for key, record in (("start", start), ("end", end)):
                if "datetime" in record:
                    window[key] = record["datetime"]
                else:
                    window[f"{key}_utc"] = record["datetime_utc"]
            item: dict[str, Any] = {
                "order": index + 1,
                "gregorian_window": window,
                "start_term": start,
                "next_term": end,
            }
            anchor = TimingAnalysis._next_supported_analysis_anchor(
                start_term, timezone_name, end_term=next_term
            )
            if anchor is None:
                item["analysis_anchor_status"] = "no_replayable_local_minute_in_window"
            else:
                item["analysis_anchor"] = anchor.strftime("%Y-%m-%d %H:%M:%S")
                liuyue = TimingAnalysis.calculate_liuyue(
                    anchor.year,
                    anchor.month,
                    anchor.day,
                    timezone_name=timezone_name,
                    target_date=anchor,
                )
                liuyue.pop("solar_term_window", None)
                item["liuyue"] = liuyue
            timeline.append(item)
        return timeline

    @staticmethod
    def calculate_liuri(
        target_date: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
        *,
        zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    ) -> dict[str, Any]:
        local_target_date = localize_datetime(target_date, timezone_name)
        return _copy_timing_info(
            _calculate_liuri_cached(
                ZonedCalendar.from_datetime(local_target_date),
                timezone_name,
                zi_hour_policy,
                get_solar_term_environment_key(year=local_target_date.year),
            )
        )

    @staticmethod
    def calculate_liushi(
        target_datetime: datetime,
        timezone_name: str = DEFAULT_TIMEZONE,
        *,
        zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    ) -> dict[str, Any]:
        local_dt = localize_datetime(target_datetime, timezone_name)
        result = _copy_timing_info(
            _calculate_liushi_cached(local_dt.date(), local_dt.hour, zi_hour_policy)
        )
        result["analysis_datetime"] = local_dt.strftime("%Y-%m-%d %H:%M:%S")
        return result

    @staticmethod
    def calculate_jieqi_transition_timeline(
        target_year: int,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> list[dict[str, Any]]:
        terms = tuple(get_solar_terms_for_year(target_year, timezone_name))
        following = _solar_terms_for_context_year(
            target_year + 1,
            timezone_name,
            _solar_term_source_year(target_year + 1, target_year),
            term_index=0,
        )
        timeline: list[dict[str, Any]] = []
        for index, (term, next_term) in enumerate(zip(terms, terms[1:] + following)):
            require_calculated_solar_term(term)
            require_calculated_solar_term(next_term)
            item: dict[str, Any] = {"order": index + 1, "jieqi": term.as_dict()}
            anchor = TimingAnalysis._next_supported_analysis_anchor(
                term, timezone_name, end_term=next_term
            )
            if anchor is None:
                item["analysis_anchor_status"] = "no_replayable_local_minute_in_window"
            else:
                item["analysis_anchor"] = anchor.strftime("%Y-%m-%d %H:%M:%S")
                liuyue = TimingAnalysis.calculate_liuyue(
                    anchor.year,
                    anchor.month,
                    anchor.day,
                    timezone_name=timezone_name,
                    target_date=anchor,
                )
                liuri = TimingAnalysis.calculate_liuri(
                    anchor, timezone_name=timezone_name
                )
                item["liuyue"] = {
                    "pillar": liuyue["pillar"],
                    "stem": liuyue["stem"],
                    "branch": liuyue["branch"],
                }
                item["liuri"] = {
                    "pillar": liuri["pillar"],
                    "stem": liuri["stem"],
                    "branch": liuri["branch"],
                }
            timeline.append(item)
        return timeline

    @staticmethod
    def _collect_branch_relations(
        target_branch: str,
        birth_pillars: dict[str, Any],
        label: str,
        *,
        target_stem: str | None = None,
    ) -> list[dict[str, Any]]:
        return collect_target_branch_relations(
            target_branch, birth_pillars, label, target_stem=target_stem
        )

    @staticmethod
    def analyze_liuyue_detailed(
        birth_pillars: dict[str, Any],
        target_year: int,
        target_month: int,
        day_stem: str | None = None,
        target_day: int = 1,
        timezone_name: str = DEFAULT_TIMEZONE,
        target_date: datetime | None = None,
        liuyue_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if liuyue_info is None:
            liuyue_info = TimingAnalysis.calculate_liuyue(
                target_year,
                target_month,
                target_day=target_day,
                timezone_name=timezone_name,
                target_date=target_date,
            )
        if day_stem is None:
            day_stem = birth_pillars["day"][0]
        stem_shishen = get_shishen(day_stem, liuyue_info["stem"])
        branch_relations = collect_target_branch_relations(
            liuyue_info["branch"],
            birth_pillars,
            "流月",
            target_stem=liuyue_info["stem"],
        )
        return {
            "basic_info": liuyue_info,
            "shishen_analysis": {
                "stem_relation": stem_shishen,
                "hidden_stems": [
                    {"stem": h, "ten_god": get_shishen(day_stem, h)}
                    for h in BRANCH_HIDDEN_STEMS[liuyue_info["branch"]]
                ],
            },
            "branch_relations": branch_relations,
            "shensha": timing_shensha(
                birth_pillars, liuyue_info["stem"], liuyue_info["branch"]
            ),
        }

    @staticmethod
    def analyze_liuri_detailed(
        birth_pillars: dict[str, Any],
        target_date: datetime,
        day_stem: str | None = None,
        timezone_name: str = DEFAULT_TIMEZONE,
        liuri_info: dict[str, Any] | None = None,
        zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    ) -> dict[str, Any]:
        if liuri_info is None:
            liuri_info = TimingAnalysis.calculate_liuri(
                target_date, timezone_name=timezone_name, zi_hour_policy=zi_hour_policy
            )
        if day_stem is None:
            day_stem = birth_pillars["day"][0]
        stem_shishen = get_shishen(day_stem, liuri_info["stem"])
        branch_relations = collect_target_branch_relations(
            liuri_info["branch"],
            birth_pillars,
            "流日",
            target_stem=liuri_info["stem"],
        )
        return {
            "basic_info": liuri_info,
            "shishen_analysis": {
                "stem_relation": stem_shishen,
                "hidden_stems": [
                    {"stem": h, "ten_god": get_shishen(day_stem, h)}
                    for h in BRANCH_HIDDEN_STEMS[liuri_info["branch"]]
                ],
            },
            "branch_relations": branch_relations,
            "shensha": timing_shensha(
                birth_pillars, liuri_info["stem"], liuri_info["branch"]
            ),
        }

    @staticmethod
    def analyze_liushi_detailed(
        birth_pillars: dict[str, Any],
        target_datetime: datetime,
        day_stem: str | None = None,
        timezone_name: str = DEFAULT_TIMEZONE,
        liushi_info: dict[str, Any] | None = None,
        zi_hour_policy: ZiHourPolicy = "day_rollover_at_23",
    ) -> dict[str, Any]:
        if liushi_info is None:
            liushi_info = TimingAnalysis.calculate_liushi(
                target_datetime,
                timezone_name=timezone_name,
                zi_hour_policy=zi_hour_policy,
            )
        if day_stem is None:
            day_stem = birth_pillars["day"][0]
        stem_shishen = get_shishen(day_stem, liushi_info["stem"])
        branch_relations = collect_target_branch_relations(
            liushi_info["branch"],
            birth_pillars,
            "流时",
            target_stem=liushi_info["stem"],
        )
        return {
            "basic_info": liushi_info,
            "shishen_analysis": {
                "stem_relation": stem_shishen,
                "hidden_stems": [
                    {"stem": h, "ten_god": get_shishen(day_stem, h)}
                    for h in BRANCH_HIDDEN_STEMS[liushi_info["branch"]]
                ],
            },
            "branch_relations": branch_relations,
            "shensha": timing_shensha(
                birth_pillars, liushi_info["stem"], liushi_info["branch"]
            ),
        }


def analyze_timing_interactions(
    natal: Mapping[str, tuple[str, str]],
    timing: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    """Full structural interaction matrix across natal + active timing pillars."""
    nodes: list[dict[str, str]] = []
    for name in _ORDER:
        if name not in natal:
            continue
        stem, branch = natal[name]
        nodes.append(
            {
                "id": f"natal.{name}",
                "scope": "natal",
                "layer": name,
                "stem": stem,
                "branch": branch,
                "pillar": stem + branch,
            }
        )
    for layer, pillar in timing.items():
        stem, branch = pillar["stem"], pillar["branch"]
        nodes.append(
            {
                "id": f"timing.{layer}",
                "scope": "timing",
                "layer": layer,
                "stem": stem,
                "branch": branch,
                "pillar": stem + branch,
            }
        )
    if any(node["pillar"] not in SEXAGENARY_INDEX for node in nodes):
        raise ValueError("时运关系需要六十甲子中的完整干支柱")

    events: list[dict[str, Any]] = []

    def emit(kind: str, members: tuple[dict[str, str], ...], **facts: Any) -> None:
        if not any(n["scope"] == "timing" for n in members):
            return
        participants = [n["id"] for n in members]
        events.append(
            {
                "id": kind + ":" + "+".join(participants),
                "rule_id": kind,
                "participants": participants,
                "scope": (
                    "natal_timing"
                    if any(n["scope"] == "natal" for n in members)
                    else "timing_timing"
                ),
                **facts,
            }
        )

    for left, right in combinations(nodes, 2):
        pair = (left, right)
        stems = frozenset((left["stem"], right["stem"]))
        branches = frozenset((left["branch"], right["branch"]))
        if stems in _STEM_COMB_SETS:
            emit("stem_combination", pair)
        for source, target in (pair, pair[::-1]):
            if (
                DESTRUCTION_CYCLE[STEM_ELEMENTS[source["stem"]][0]]
                == STEM_ELEMENTS[target["stem"]][0]
            ):
                emit("stem_overcoming", pair, source=source["id"], target=target["id"])
                if (
                    BRANCH_CONFLICTS[left["branch"]] == right["branch"]
                    and STEM_ELEMENTS[source["stem"]][1]
                    == STEM_ELEMENTS[target["stem"]][1]
                ):
                    emit(
                        "heaven_overcoming_earth_clash",
                        pair,
                        source=source["id"],
                        target=target["id"],
                    )
        if BRANCH_CONFLICTS[left["branch"]] == right["branch"]:
            emit("branch_clash", pair)
        if BRANCH_COMBINATIONS[left["branch"]] == right["branch"]:
            emit("branch_combination", pair)
        if BRANCH_HARMS[left["branch"]] == right["branch"]:
            emit("branch_harm", pair)
        if BRANCH_BREAKS[left["branch"]] == right["branch"]:
            emit("branch_break", pair)
        if left["branch"] != right["branch"] and branches in BRANCH_HIDDEN_COMBINATIONS:
            emit(
                "branch_hidden_combination",
                pair,
                detail=BRANCH_HIDDEN_COMBINATIONS[branches],
            )
        if (
            left["branch"] == right["branch"]
            and left["branch"] in BRANCH_SELF_PUNISHMENTS
        ):
            emit("self_punishment", pair)
        for pgroup in BRANCH_THREE_PUNISHMENTS:
            if len(branches) == 2 and branches <= set(pgroup):
                emit(
                    "branch_punishment" if len(pgroup) == 2 else "partial_punishment",
                    pair,
                    group="".join(pgroup),
                    complete=len(pgroup) == 2,
                )
        for group, bureau in BRANCH_TRIPLE_COMBINATIONS.items():
            if (
                len(branches) == 2
                and branches <= set(group)
                and TRIPLE_COMBINATION_PEAK[group] in branches
            ):
                emit("half_combination", pair, group=group, bureau=bureau)
        if left["pillar"] == right["pillar"]:
            emit("pillar_repeat", pair, traditional_label="伏吟")
            if {left["id"], right["id"]} == {"timing.dayun", "timing.liunian"}:
                emit("suiyun_binglin", pair, traditional_label="岁运并临")

    for group_nodes in combinations(nodes, 3):
        group_branches = {n["branch"] for n in group_nodes}
        for kind, groups in (
            ("triple_combination", BRANCH_TRIPLE_COMBINATIONS),
            ("seasonal_meeting", BRANCH_SEASONAL_COMBINATIONS),
        ):
            for group, bureau in groups.items():
                if group_branches == set(group):
                    emit(kind, group_nodes, group=group, bureau=bureau)
        for pgroup in BRANCH_THREE_PUNISHMENTS:
            if len(pgroup) == 3 and group_branches == set(pgroup):
                emit(
                    "branch_punishment",
                    group_nodes,
                    group="".join(pgroup),
                    complete=True,
                )

    day_stem = natal["day"][0]
    ten_god_context = [
        {
            "node_id": node["id"],
            "pillar": node["pillar"],
            "stem_ten_god": get_shishen(day_stem, node["stem"]),
            "hidden_stems": [
                {"stem": s, "ten_god": get_shishen(day_stem, s), "rank": idx + 1}
                for idx, s in enumerate(BRANCH_HIDDEN_STEMS[node["branch"]])
            ],
            "shensha": timing_shensha(natal, node["stem"], node["branch"]),
        }
        for node in nodes
        if node["scope"] == "timing"
    ]

    return {
        "nodes": nodes,
        "ten_god_context": ten_god_context,
        "relations": events,
    }
