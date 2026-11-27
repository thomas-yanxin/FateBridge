"""Zi Wei Dou Shu calculation services."""

from __future__ import annotations

from typing import Any

from fatebridge.core.almanac import GAN
from fatebridge.core.execution_context import current_datetime
from fatebridge.core.ziwei.calendar import (
    build_ziwei_analysis_seed,
    build_ziwei_person_seed,
    context_basis,
    ziwei_analysis_context_payload,
)
from fatebridge.core.ziwei.chart import (
    build_ziwei_chart,
    build_ziwei_horoscope,
    build_ziwei_rules,
)
from fatebridge.core.ziwei.tables import (
    DEFAULT_ZIWEI_AGE_DIVIDE,
    DEFAULT_ZIWEI_ASTRO_TYPE,
    DEFAULT_ZIWEI_DAY_DIVIDE,
    DEFAULT_ZIWEI_HOROSCOPE_DIVIDE,
    DEFAULT_ZIWEI_PROFILE,
    DEFAULT_ZIWEI_SCHOOL,
    DEFAULT_ZIWEI_YEAR_DIVIDE,
    ZiweiBrightnessSource,
    ZiweiNatalLeapMonthPolicy,
)
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import format_birth_datetime_display
from fatebridge.utils.timezones import parse_timezone_name


def _resolve_ziwei_analysis_clock(
    *,
    analysis_year: int | None,
    analysis_month: int | None,
    analysis_day: int | None,
    analysis_hour: int | None,
    analysis_minute: int | None,
    analysis_timezone: str,
) -> tuple[tuple[int, int, int, int, int], dict[str, Any]]:
    fields = (
        "analysis_year",
        "analysis_month",
        "analysis_day",
        "analysis_hour",
        "analysis_minute",
    )
    supplied = {
        "analysis_year": analysis_year,
        "analysis_month": analysis_month,
        "analysis_day": analysis_day,
        "analysis_hour": analysis_hour,
        "analysis_minute": analysis_minute,
    }
    provided = [name for name in fields if supplied[name] is not None]
    if not provided:
        zone = parse_timezone_name(analysis_timezone)
        now = current_datetime(zone, analysis_timezone)
        return (now.year, now.month, now.day, now.hour, now.minute), {
            "basis": "implicit_execution_clock",
            "provided_fields": [],
            "defaulted_from_clock": list(fields),
            "fixed_defaults": {},
        }

    finest_idx = max(
        idx for idx, name in enumerate(fields) if supplied[name] is not None
    )
    defaulted = [
        fields[idx] for idx in range(finest_idx) if supplied[fields[idx]] is None
    ]
    clock_values: tuple[int | None, int | None, int | None, int | None, int | None]
    if defaulted:
        clock_now = current_datetime(
            parse_timezone_name(analysis_timezone), analysis_timezone
        )
        clock_values = (
            clock_now.year,
            clock_now.month,
            clock_now.day,
            clock_now.hour,
            clock_now.minute,
        )
    else:
        clock_values = (None, None, None, None, None)
    fixed: dict[str, int] = {}
    resolved: list[int] = []
    for name, clock_val in zip(fields, clock_values):
        val = supplied[name]
        if val is None:
            if name in defaulted:
                assert clock_val is not None
                val = clock_val
            else:
                val = 1 if name in ("analysis_month", "analysis_day") else 0
                fixed[name] = val
        resolved.append(val)
    basis = (
        "declared_partial_components" if len(provided) < 5 else "explicit_components"
    )
    return (
        (resolved[0], resolved[1], resolved[2], resolved[3], resolved[4]),
        {
            "basis": basis,
            "provided_fields": provided,
            "defaulted_from_clock": defaulted,
            "fixed_defaults": fixed,
        },
    )


@calculation_guard("紫微斗数命盘")
def calculate_ziwei_birth(
    person: PersonInfo,
    *,
    school: str = DEFAULT_ZIWEI_SCHOOL,
    astro_type: str = DEFAULT_ZIWEI_ASTRO_TYPE,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    brightness_source: ZiweiBrightnessSource = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
    year_divide: str = DEFAULT_ZIWEI_YEAR_DIVIDE,
    birth_utc_offset: str | None = None,
    natal_leap_month_policy: ZiweiNatalLeapMonthPolicy | None = None,
) -> dict[str, Any]:
    seed = build_ziwei_person_seed(person, birth_utc_offset=birth_utc_offset)
    ziwei_birth = build_ziwei_chart(
        seed,
        person.gender or "未知",
        school=school,
        astro_type=astro_type,
        rule_profile=rule_profile,
        sihua_source=sihua_source,
        brightness_source=brightness_source,
        day_divide=day_divide,
        year_divide=year_divide,
        natal_leap_month_policy=natal_leap_month_policy,
        include_calendar_basis=True,
    )
    return {
        "analysis_type": "紫微斗数命盘",
        "person_info": {
            "name": person.name or "未提供",
            "birth_datetime": format_birth_datetime_display(
                seed.input_datetime, include_minutes=True
            ),
            "normalized_birth_datetime": format_birth_datetime_display(
                seed.clock, include_minutes=True
            ),
            "gender": person.gender or "未知",
            "birth_place": person.birth_place or "未提供",
            "birth_timezone": seed.timezone,
            "birth_longitude": seed.longitude,
            "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        },
        "analysis_context": {
            **ziwei_analysis_context_payload(seed),
            **context_basis(ziwei_birth["calendar_basis"]),
        },
        "ziwei_birth": ziwei_birth,
    }


@calculation_guard("紫微斗数运限")
def calculate_ziwei_horoscope(
    person: PersonInfo,
    *,
    analysis_year: int | None = None,
    analysis_month: int | None = None,
    analysis_day: int | None = None,
    analysis_hour: int | None = None,
    analysis_minute: int | None = None,
    analysis_timezone: str = "Asia/Shanghai",
    analysis_utc_offset: str | None = None,
    birth_utc_offset: str | None = None,
    school: str = DEFAULT_ZIWEI_SCHOOL,
    astro_type: str = DEFAULT_ZIWEI_ASTRO_TYPE,
    natal_leap_month_policy: ZiweiNatalLeapMonthPolicy | None = None,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    brightness_source: ZiweiBrightnessSource = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
    year_divide: str = DEFAULT_ZIWEI_YEAR_DIVIDE,
    horoscope_divide: str = DEFAULT_ZIWEI_HOROSCOPE_DIVIDE,
    age_divide: str = DEFAULT_ZIWEI_AGE_DIVIDE,
    nominal_age_basis: str = "birth_civil_timezone",
    include_decadal_list: bool = False,
    include_yearly_list: bool = False,
    include_monthly_list: bool = False,
) -> dict[str, Any]:
    (
        resolved_year,
        resolved_month,
        resolved_day,
        resolved_hour,
        resolved_minute,
    ), clock_meta = _resolve_ziwei_analysis_clock(
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
        analysis_timezone=analysis_timezone,
    )
    seed = build_ziwei_person_seed(person, birth_utc_offset=birth_utc_offset)
    chart = build_ziwei_chart(
        seed,
        person.gender or "未知",
        school=school,
        astro_type=astro_type,
        rule_profile=rule_profile,
        sihua_source=sihua_source,
        brightness_source=brightness_source,
        day_divide=day_divide,
        year_divide=year_divide,
        natal_leap_month_policy=natal_leap_month_policy,
        include_calendar_basis=True,
    )
    target_seed = build_ziwei_analysis_seed(
        analysis_year=resolved_year,
        analysis_month=resolved_month,
        analysis_day=resolved_day,
        analysis_hour=resolved_hour,
        analysis_minute=resolved_minute,
        analysis_timezone=analysis_timezone,
        analysis_utc_offset=analysis_utc_offset,
    )
    horoscope = build_ziwei_horoscope(
        chart=chart,
        gender=person.gender or "未知",
        target_seed=target_seed,
        birth_seed=seed,
        nominal_age_basis=nominal_age_basis,
        day_divide=day_divide,
        horoscope_divide=horoscope_divide,
        age_divide=age_divide,
        include_decadal_list=include_decadal_list,
        include_yearly_list=include_yearly_list,
        include_monthly_list=include_monthly_list,
    )
    return {
        "analysis_type": "紫微斗数运限",
        "person_info": {
            "name": person.name or "未提供",
            "birth_datetime": format_birth_datetime_display(
                seed.input_datetime, include_minutes=True
            ),
            "normalized_birth_datetime": format_birth_datetime_display(
                seed.clock, include_minutes=True
            ),
            "gender": person.gender or "未知",
            "birth_place": person.birth_place or "未提供",
            "birth_timezone": seed.timezone,
            "birth_longitude": seed.longitude,
            "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        },
        "birth_context": {
            **ziwei_analysis_context_payload(seed),
            **context_basis(horoscope["calendar_basis"]["birth"]),
            "context_role": "birth",
        },
        "analysis_context": {
            **ziwei_analysis_context_payload(target_seed),
            **context_basis(horoscope["calendar_basis"]["target"]),
            **clock_meta,
            "context_role": "target",
            "analysis_datetime": target_seed.clock.isoformat(
                sep=" ", timespec="seconds"
            ),
            "analysis_year": target_seed.clock.date_parts[0],
            "analysis_month": target_seed.clock.date_parts[1],
            "analysis_day": target_seed.clock.date_parts[2],
            "analysis_hour": target_seed.clock.time_parts[0],
            "analysis_minute": target_seed.clock.time_parts[1],
        },
        "ziwei_horoscope": horoscope,
    }


@calculation_guard("紫微规则库")
def calculate_ziwei_rules(
    year_stem: str | None = None,
    *,
    school: str = DEFAULT_ZIWEI_SCHOOL,
    astro_type: str = DEFAULT_ZIWEI_ASTRO_TYPE,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    brightness_source: ZiweiBrightnessSource = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
    year_divide: str = DEFAULT_ZIWEI_YEAR_DIVIDE,
) -> dict[str, Any]:
    if year_stem is not None and year_stem not in set(GAN):
        raise ValueError("year_stem 必须是单个天干")
    payload = build_ziwei_rules(
        year_stem,
        school=school,
        astro_type=astro_type,
        rule_profile=rule_profile,
        sihua_source=sihua_source,
        brightness_source=brightness_source,
        day_divide=day_divide,
        year_divide=year_divide,
    )
    payload["engine"] = "fatebridge-offline"
    return {
        "analysis_type": "紫微规则库",
        **payload,
    }
