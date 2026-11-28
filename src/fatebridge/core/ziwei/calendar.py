"""Lightweight lunar-calendar, civil clock, and age-ordinal resolution for Ziwei."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from dateutil import tz

from fatebridge.core.almanac import (
    LUNAR_DAY_NAMES,
    LUNAR_MONTH_NAMES,
    fast_lunar_dict,
    get_bazi_month_context,
    get_bazi_year,
    localize_datetime,
)
from fatebridge.core.bazi.calendar import LATE_ZI_HOUR, BaZiCalendar
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.ziwei.tables import (
    DEFAULT_ZIWEI_AGE_DIVIDE,
    ZiweiAgeDivide,
    ZiweiDayDivide,
    ZiweiYearDivide,
    validate_age_divide,
    validate_day_divide,
    validate_year_divide,
)
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.civil_clock import format_utc_offset, resolve_civil_clock
from fatebridge.utils.civil_time import NominalClockLabel, ZonedCalendar, utc_calendar
from fatebridge.utils.data import year_ganzhi
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_APPARENT,
    NormalizedBirthTime,
    calculate_solar_time_adjustment,
    normalize_birth_time,
)
from fatebridge.utils.timezones import (
    is_unspecified_local_time,
    parse_timezone_name,
    timezone_rules_metadata,
    validate_local_clock,
)


def lunar_year_ganzhi(lunar_year: int) -> tuple[str, str]:
    """Derive the stem and branch of a lunar year (正月初一 boundary)."""
    return year_ganzhi(lunar_year)


def lunar_display_from_dict(lunar: dict[str, Any]) -> str:
    leap = "闰" if lunar.get("is_leap_month") else ""
    return f"{leap}{LUNAR_MONTH_NAMES[int(lunar['month'])]}{LUNAR_DAY_NAMES[int(lunar['day'])]}"


def _minute_sensitivity(
    normalized: NormalizedBirthTime, birth_second: int | None
) -> dict[str, Any]:
    if birth_second is not None:
        return {
            "method_id": "ziwei_input_minute_endpoint_sensitivity_v1",
            "clock_stage": "after_normalization_before_day_divide",
            "birth_seconds_supplied": True,
            "base_second": birth_second,
        }
    start = normalized.corrected_datetime.replace(tzinfo=None)
    civil = normalized.input_datetime
    zone = parse_timezone_name(normalized.timezone)
    elapsed = timedelta(seconds=59, microseconds=999999)
    last = (civil.replace(tzinfo=zone).astimezone(timezone.utc) + elapsed).astimezone(
        zone
    )
    last_wall = last.replace(tzinfo=None)
    requested_wall = civil.replace(tzinfo=None) + elapsed
    has_endpoint = last_wall == requested_wall and not is_unspecified_local_time(last)
    placement = [start]
    seconds: list[int | float] = [0]
    if has_endpoint:
        if normalized.applied:
            assert normalized.longitude is not None
            adjustment = calculate_solar_time_adjustment(
                last,
                normalized.timezone,
                normalized.longitude,
                strategy=normalized.solar_time_strategy or SOLAR_TIME_STRATEGY_APPARENT,
            )
            last_wall += timedelta(minutes=adjustment["total_correction_minutes"])
        placement.append(last_wall)
        seconds.append(59.999999)
    branches = "子丑寅卯辰巳午未申酉戌亥"
    hours = [branches[((label.hour + 1) // 2) % 12] for label in placement]
    return {
        "method_id": "ziwei_input_minute_endpoint_sensitivity_v1",
        "clock_stage": "after_normalization_before_day_divide",
        "birth_seconds_supplied": False,
        "base_second": 0,
        "endpoint_seconds": seconds,
        "endpoint_placement_datetimes": [
            label.isoformat(sep=" ") for label in placement
        ],
        "endpoint_hour_branches": hours,
        "crosses_hour_branch": hours[0] != hours[1] if has_endpoint else None,
        "crosses_placement_date": (
            start.date() != placement[1].date() if has_endpoint else None
        ),
    }


def birth_clock_receipt(
    person: PersonInfo, normalized: NormalizedBirthTime
) -> dict[str, Any]:
    result = normalized.as_dict(include_timezone_resolution=True)
    requested = bool(person.use_true_solar_time)
    assumed_zone = normalized.timezone_source in {
        "default_timezone",
        "longitude_standard_meridian_assumption",
        None,
    }
    coarse = normalized.applied and normalized.resolution_level == "province"
    if requested and not normalized.applied:
        status = "solar_unavailable"
    elif assumed_zone:
        status = "timezone_assumed"
    elif coarse:
        status = "province_longitude"
    else:
        status = "solar_applied" if normalized.applied else "civil_clock_selected"
    if not normalized.applied:
        for key in (
            "longitude_correction_minutes",
            "equation_of_time_minutes",
            "daylight_saving_minutes",
        ):
            result[key] = None
    result.update(
        method_id="ziwei_birth_clock_receipt_v1",
        status=status,
        requested=requested,
        explicitly_requested=bool(requested and person.true_solar_explicit),
        components_computed=normalized.applied,
        timezone_assumed=assumed_zone,
        applied_delta_seconds=round(
            (
                normalized.corrected_datetime.replace(tzinfo=None)
                - normalized.input_datetime.replace(tzinfo=None)
            ).total_seconds(),
            6,
        ),
        minute_sensitivity=_minute_sensitivity(normalized, person.birth_second),
    )
    return result


def build_ziwei_person_seed(
    person: PersonInfo, *, birth_utc_offset: str | None = None
) -> MetaphysicsSeed:
    """Resolve birth clock + lunar/day/hour pillars without solar-term ephemeris."""
    normalized = normalize_birth_time(
        person,
        solar_time_strategy=SOLAR_TIME_STRATEGY_APPARENT,
        birth_utc_offset=birth_utc_offset,
    )
    civil = localize_datetime(normalized.input_datetime, normalized.timezone)
    clock = NominalClockLabel.from_local_datetime(normalized.corrected_datetime)
    y, m, d = clock.date_parts
    hour = clock.time_parts[0]
    lunar = fast_lunar_dict(date(y, m, d))
    lunar["display"] = lunar_display_from_dict(lunar)
    day_pillar = BaZiCalendar.calculate_day_pillar(y, m, d, hour=hour)
    hour_pillar = BaZiCalendar.calculate_hour_pillar(y, m, d, hour)
    year_pillar = lunar_year_ganzhi(int(lunar["year"]))
    return MetaphysicsSeed(
        input_datetime=civil,
        clock=clock,
        timezone=normalized.timezone,
        longitude=normalized.longitude,
        applied_true_solar=normalized.applied,
        total_correction_minutes=normalized.total_correction_minutes,
        pillars={
            "year": year_pillar,
            "month": ("甲", "寅"),
            "day": day_pillar,
            "hour": hour_pillar,
        },
        calendar_context={"lunar_calendar": lunar},
        input_offset_visible=normalized.input_datetime.utcoffset() is not None,
        birth_time_normalization=birth_clock_receipt(person, normalized),
    )


def build_ziwei_analysis_seed(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_timezone: str | None = None,
    analysis_utc_offset: str | None = None,
) -> MetaphysicsSeed:
    """Resolve target clock + lunar/day/hour pillars without solar-term ephemeris."""
    timezone_name = analysis_timezone or DEFAULT_BIRTH_TIMEZONE
    civil = resolve_civil_clock(
        datetime(
            analysis_year,
            analysis_month,
            analysis_day,
            analysis_hour,
            analysis_minute,
            0,
        ),
        timezone_name,
        analysis_utc_offset,
        offset_field="analysis_utc_offset",
        timezone_field="analysis_timezone",
    )
    clock = NominalClockLabel.from_local_datetime(civil)
    y, m, d = clock.date_parts
    hour = clock.time_parts[0]
    lunar = fast_lunar_dict(date(y, m, d))
    lunar["display"] = lunar_display_from_dict(lunar)
    day_pillar = BaZiCalendar.calculate_day_pillar(y, m, d, hour=hour)
    hour_pillar = BaZiCalendar.calculate_hour_pillar(y, m, d, hour)
    year_pillar = lunar_year_ganzhi(int(lunar["year"]))
    return MetaphysicsSeed(
        input_datetime=civil,
        clock=clock,
        timezone=timezone_name,
        longitude=None,
        applied_true_solar=False,
        total_correction_minutes=0.0,
        pillars={
            "year": year_pillar,
            "month": ("甲", "寅"),
            "day": day_pillar,
            "hour": hour_pillar,
        },
        calendar_context={"lunar_calendar": lunar},
        input_offset_visible=analysis_utc_offset is not None,
    )


def ziwei_analysis_context_payload(seed: MetaphysicsSeed) -> dict[str, Any]:
    lunar_context = seed.calendar_context.get("lunar_calendar") or {}
    return {
        "input_datetime": seed.input_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "corrected_datetime": seed.clock.isoformat(sep=" ", timespec="seconds"),
        "timezone": seed.timezone,
        "longitude": seed.longitude,
        "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        "total_correction_minutes": round(seed.total_correction_minutes, 2),
        "lunar_display": lunar_context.get("display"),
    }


class ZiweiClockState:
    __slots__ = (
        "placement_label",
        "lunar",
        "lunar_year",
        "lunar_month",
        "lunar_day",
        "is_leap_month",
        "hour_branch",
        "day_stem",
        "day_branch",
        "hour_stem",
        "is_late_zi",
        "year_stem",
        "year_branch",
    )

    def __init__(
        self,
        *,
        placement_label: NominalClockLabel,
        lunar: dict[str, Any],
        lunar_year: int,
        lunar_month: int,
        lunar_day: int,
        is_leap_month: bool,
        hour_branch: str,
        day_stem: str,
        day_branch: str,
        hour_stem: str,
        is_late_zi: bool,
        year_stem: str,
        year_branch: str,
    ) -> None:
        self.placement_label = placement_label
        self.lunar = lunar
        self.lunar_year = lunar_year
        self.lunar_month = lunar_month
        self.lunar_day = lunar_day
        self.is_leap_month = is_leap_month
        self.hour_branch = hour_branch
        self.day_stem = day_stem
        self.day_branch = day_branch
        self.hour_stem = hour_stem
        self.is_late_zi = is_late_zi
        self.year_stem = year_stem
        self.year_branch = year_branch


def resolve_ziwei_clock_state(
    seed: MetaphysicsSeed,
    day_divide: ZiweiDayDivide,
    *,
    technique: str,
    year_divide: ZiweiYearDivide = "normal",
) -> ZiweiClockState:
    """Resolve placement clock, lunar date, day/hour pillars, and year pillar."""
    resolved_year_divide = validate_year_divide(year_divide)
    placement_label = seed.clock
    year, month, day = seed.clock.date_parts
    hour = seed.clock.time_parts[0]
    is_late_zi = hour >= LATE_ZI_HOUR
    rollover = is_late_zi and day_divide == "forward"
    if rollover:
        placement_label = NominalClockLabel(seed.clock.ordinal + 1, 0)
        py, pm, pd = placement_label.date_parts
        lunar = fast_lunar_dict(date(py, pm, pd))
    else:
        cached = seed.calendar_context.get("lunar_calendar")
        if cached is not None:
            if cached.get("year") is None:
                raise ValueError(f"{technique}需要完整农历年月日，无法起盘：农历年缺失")
            if cached.get("month") is None or cached.get("day") is None:
                raise ValueError(f"{technique}需要农历月日，无法起盘")
            lunar = dict(cached)
        else:
            lunar = fast_lunar_dict(date(year, month, day))

    lunar_year = lunar.get("year")
    if not isinstance(lunar_year, int):
        raise ValueError(f"{technique}需要完整农历年月日，无法起盘：农历年缺失")
    lunar_month = int(lunar["month"])
    lunar_day = int(lunar["day"])

    if is_late_zi or not seed.pillars:
        day_stem, day_branch = BaZiCalendar.calculate_day_pillar(
            year, month, day, hour=hour, apply_late_zi_rollover=rollover
        )
        hour_stem, hour_branch = BaZiCalendar.calculate_hour_pillar(
            year, month, day, hour, apply_late_zi_rollover=rollover
        )
    else:
        day_stem, day_branch = seed.pillars["day"]
        hour_stem, hour_branch = seed.pillars["hour"]

    if resolved_year_divide == "exact":
        bazi_year = get_bazi_year(seed.input_datetime, seed.timezone)
        year_stem, year_branch = lunar_year_ganzhi(bazi_year)
    else:
        year_stem, year_branch = lunar_year_ganzhi(lunar_year)

    return ZiweiClockState(
        placement_label=placement_label,
        lunar=lunar,
        lunar_year=lunar_year,
        lunar_month=lunar_month,
        lunar_day=lunar_day,
        is_leap_month=bool(lunar.get("is_leap_month")),
        hour_branch=hour_branch,
        day_stem=day_stem,
        day_branch=day_branch,
        hour_stem=hour_stem,
        is_late_zi=is_late_zi,
        year_stem=year_stem,
        year_branch=year_branch,
    )


def resolve_exact_month_pillar(
    civil_datetime: datetime, timezone_name: str, *, year_divide: ZiweiYearDivide
) -> tuple[str, str]:
    """Compute solar-term month pillar when horoscope_divide == 'exact'."""
    bazi_year = get_bazi_year(civil_datetime, timezone_name)
    month_ctx = get_bazi_month_context(civil_datetime, timezone_name)
    return BaZiCalendar.calculate_month_pillar_by_branch(
        bazi_year, str(month_ctx["branch"])
    )


def _date_fields(lunar: dict[str, Any] | None) -> dict[str, Any] | None:
    if not lunar:
        return None
    return {key: lunar[key] for key in ("year", "month", "day", "is_leap_month")}


def calendar_basis(
    seed: MetaphysicsSeed,
    *,
    placement_label: NominalClockLabel,
    placement_context: dict[str, Any],
    day_divide: ZiweiDayDivide,
) -> dict[str, Any]:
    """Build compact, non-redundant calendar receipt for a Ziwei clock."""
    civil_ordinal = seed.input_datetime.toordinal()
    if civil_ordinal == placement_label.ordinal:
        civil_context = placement_context
    elif civil_ordinal == seed.clock.ordinal and seed.calendar_context.get(
        "lunar_calendar"
    ):
        civil_context = seed.calendar_context["lunar_calendar"]
    else:
        civil_context = fast_lunar_dict(seed.input_datetime.date())

    instant = utc_calendar(seed.input_datetime)
    reference = ZonedCalendar(instant, parse_timezone_name("+08:00"))
    ry, rm, rd, hour, minute, second, microsecond = reference.local_parts
    reference_label = NominalClockLabel(
        reference.local_ordinal,
        ((hour * 60 + minute) * 60 + second) * 1000000 + microsecond,
    )
    if reference_label.ordinal == civil_ordinal:
        reference_context = civil_context
    elif reference_label.ordinal == placement_label.ordinal:
        reference_context = placement_context
    else:
        reference_context = fast_lunar_dict(date(ry, rm, rd))

    result: dict[str, Any] = {
        "method_id": "ziwei_calendar_basis_v2",
        "placement_clock": "apparent_solar" if seed.applied_true_solar else "civil",
        "placement_datetime": placement_label.isoformat(sep=" ", timespec="seconds"),
        "civil_datetime": seed.input_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "civil_instant_utc": instant.isoformat(),
        "apparent_solar_datetime": (
            seed.clock.isoformat(sep=" ") if seed.applied_true_solar else None
        ),
        "timezone": seed.timezone,
        "day_divide": day_divide,
        "late_zi_rollover_applied": placement_label.ordinal != seed.clock.ordinal,
        "date_shift_days": placement_label.ordinal - civil_ordinal,
        "placement_lunar_date": _date_fields(placement_context),
        "civil_date_lunar_date": _date_fields(civil_context),
        "reference_datetime_utc_plus_08": reference_label.isoformat(
            sep=" ", timespec="seconds"
        ),
        "reference_lunar_date": _date_fields(reference_context),
        "day_boundary": (
            "23:00_in_selected_clock"
            if day_divide == "forward"
            else "00:00_in_selected_clock"
        ),
        "time_input": (
            dict(seed.birth_time_normalization)
            if seed.birth_time_normalization is not None
            else None
        ),
        "civil_clock": None,
    }
    if seed.input_offset_visible:
        civil_instant = seed.input_datetime
        offset = civil_instant.utcoffset()
        assert offset is not None
        result["civil_clock"] = {
            "method_id": "ziwei_explicit_civil_offset_v1",
            "selection": "explicit_offset_matching_named_zone",
            "timezone": seed.timezone,
            "resolved_utc_offset": format_utc_offset(offset),
            "wall_datetime": civil_instant.replace(tzinfo=None).isoformat(sep=" "),
            "was_ambiguous": tz.datetime_ambiguous(civil_instant),
            "fold": civil_instant.fold,
            "instant_utc": instant.isoformat(),
            "timezone_rules": timezone_rules_metadata(seed.timezone),
        }
    return result


def placement_lunar_display(basis: dict[str, Any]) -> str:
    return lunar_display_from_dict(basis["placement_lunar_date"])


def context_basis(basis: dict[str, Any]) -> dict[str, Any]:
    boundary = "23:00" if basis["day_divide"] == "forward" else "midnight"
    result: dict[str, Any] = {
        "lunar_date_basis": f"{basis['placement_clock']}_date_label_at_{boundary}",
        "lunar_display": placement_lunar_display(basis),
        "calendar_date_shift_days": basis["date_shift_days"],
    }
    if basis.get("time_input"):
        result["time_input_status"] = basis["time_input"]["status"]
        sensitivity = basis["time_input"].get("minute_sensitivity", {})
        if sensitivity.get("crosses_hour_branch") or sensitivity.get(
            "crosses_placement_date"
        ):
            result["time_input_minute_sensitive"] = True
    if basis.get("civil_clock"):
        result["civil_utc_offset"] = basis["civil_clock"]["resolved_utc_offset"]
        result["civil_instant_utc"] = basis["civil_clock"]["instant_utc"]
    return result


def _effective_age_date(dt: datetime, day_divide: ZiweiDayDivide) -> date:
    if day_divide == "forward" and dt.hour >= LATE_ZI_HOUR:
        return dt.date() + timedelta(days=1)
    return dt.date()


def nominal_age_calendar(
    *,
    birth_seed: MetaphysicsSeed | None,
    target_seed: MetaphysicsSeed,
    birth_placement_year: int,
    basis: str = "birth_civil_timezone",
    day_divide: ZiweiDayDivide = "current",
    age_divide: ZiweiAgeDivide = DEFAULT_ZIWEI_AGE_DIVIDE,
) -> dict[str, Any]:
    """Compute nominal age (虚岁) aligned with day_divide rollover and age_divide."""
    if basis != "birth_civil_timezone":
        raise ValueError("未知紫微岁序口径：" + basis)
    if birth_seed is None:
        raise ValueError("同区岁序需要实际出生时钟；不能仅从给定农历条件盘推断岁序")
    resolved_day_divide = validate_day_divide(day_divide)
    resolved_age_divide = validate_age_divide(age_divide)

    birth_instant = utc_calendar(birth_seed.input_datetime)
    target_instant = utc_calendar(target_seed.input_datetime)
    if target_instant.elapsed_since(birth_instant) < timedelta(0):
        raise ValueError("紫微运限目标时刻早于出生时刻")

    zone = parse_timezone_name(birth_seed.timezone)
    birth = ZonedCalendar(birth_instant, zone).require_datetime()
    target = ZonedCalendar(target_instant, zone).require_datetime()
    validate_local_clock(target, allow_ambiguous=True, clock_label="紫微岁序目标钟时")

    birth_lunar = fast_lunar_dict(_effective_age_date(birth, resolved_day_divide))
    target_lunar = fast_lunar_dict(_effective_age_date(target, resolved_day_divide))

    year_diff = int(target_lunar["year"]) - int(birth_lunar["year"])
    if resolved_age_divide == "birthday":
        after_or_on_bday = (
            int(target_lunar["month"]),
            int(bool(target_lunar["is_leap_month"])),
            int(target_lunar["day"]),
        ) >= (
            int(birth_lunar["month"]),
            int(bool(birth_lunar["is_leap_month"])),
            int(birth_lunar["day"]),
        )
        age = year_diff + (1 if after_or_on_bday else 0)
    else:
        age = year_diff + 1

    if age < 1:
        raise ValueError("同区农历岁序小于1；保留边界失败，不能强制钳为1")

    target_civil_date = _effective_age_date(
        target_seed.input_datetime, resolved_day_divide
    )
    target_civil_lunar = (
        target_lunar
        if target_civil_date == _effective_age_date(target, resolved_day_divide)
        else fast_lunar_dict(target_civil_date)
    )

    return {
        "method_id": (
            "ziwei_nominal_age_birthday_v1"
            if resolved_age_divide == "birthday"
            else "ziwei_nominal_age_birth_civil_v2"
        ),
        "basis": basis,
        "age_divide": resolved_age_divide,
        "day_divide": resolved_day_divide,
        "rule": (
            "lunar_birthday_increment_in_birth_timezone"
            if resolved_age_divide == "birthday"
            else "target_lunar_year_minus_birth_lunar_year_plus_one_with_day_divide"
        ),
        "timezone": birth_seed.timezone,
        "birth_datetime": birth.isoformat(sep=" "),
        "target_datetime": target.isoformat(sep=" "),
        "birth_instant_utc": birth_instant.isoformat(),
        "target_instant_utc": target_instant.isoformat(),
        "birth_lunar_date": birth_lunar,
        "target_lunar_date": target_lunar,
        "birth_lunar_year": birth_lunar["year"],
        "target_lunar_year": target_lunar["year"],
        "birth_placement_lunar_year": birth_placement_year,
        "target_civil_lunar_year": target_civil_lunar["year"],
        "nominal_age": age,
        "day_boundary": (
            "23:00_in_birth_civil_timezone"
            if resolved_day_divide == "forward"
            else "00:00_in_birth_civil_timezone"
        ),
    }
