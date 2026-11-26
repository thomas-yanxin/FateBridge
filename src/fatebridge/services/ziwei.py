"""Zi Wei Dou Shu calculation services."""

from __future__ import annotations

from typing import Any

from fatebridge.core.almanac import GAN
from fatebridge.core.metaphysics.seed import (
    _analysis_context_payload,
    _build_person_seed,
    build_analysis_seed,
)
from fatebridge.core.metaphysics.ziwei import (
    build_ziwei_chart,
    build_ziwei_horoscope,
    build_ziwei_rules,
)
from fatebridge.core.ziwei.ziwei_calendar import context_basis
from fatebridge.core.ziwei.ziwei_rulesets import (
    DEFAULT_ZIWEI_DAY_DIVIDE,
    DEFAULT_ZIWEI_PROFILE,
    ZiweiNatalLeapMonthPolicy,
)
from fatebridge.core.ziwei.ziwei_tables import ZiweiBrightnessSource
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import (
    create_pillar_dict,
    format_birth_datetime_display,
)


@calculation_guard("紫微斗数命盘")
def calculate_ziwei_birth(
    person: PersonInfo,
    *,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    brightness_source: ZiweiBrightnessSource = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
    birth_utc_offset: str | None = None,
    natal_leap_month_policy: ZiweiNatalLeapMonthPolicy | None = None,
) -> dict[str, Any]:
    seed = _build_person_seed(person, birth_utc_offset=birth_utc_offset)
    ziwei_birth = build_ziwei_chart(
        seed,
        person.gender or "未知",
        rule_profile=rule_profile,
        sihua_source=sihua_source,
        brightness_source=brightness_source,
        day_divide=day_divide,
        natal_leap_month_policy=natal_leap_month_policy,
        include_calendar_basis=True,
    )
    ziwei_birth["engine"] = "fatebridge-offline"
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
            **_analysis_context_payload(seed),
            **context_basis(ziwei_birth["calendar_basis"]),
        },
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "ziwei_birth": ziwei_birth,
    }


@calculation_guard("紫微斗数运限")
def calculate_ziwei_horoscope(
    person: PersonInfo,
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_timezone: str = "Asia/Shanghai",
    analysis_utc_offset: str | None = None,
    birth_utc_offset: str | None = None,
    natal_leap_month_policy: ZiweiNatalLeapMonthPolicy | None = None,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    brightness_source: ZiweiBrightnessSource = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
    nominal_age_basis: str = "birth_civil_timezone",
) -> dict[str, Any]:
    seed = _build_person_seed(person, birth_utc_offset=birth_utc_offset)
    chart = build_ziwei_chart(
        seed,
        person.gender or "未知",
        rule_profile=rule_profile,
        sihua_source=sihua_source,
        brightness_source=brightness_source,
        day_divide=day_divide,
        natal_leap_month_policy=natal_leap_month_policy,
        include_calendar_basis=True,
    )
    target_seed = build_analysis_seed(
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
        analysis_timezone=analysis_timezone,
        analysis_utc_offset=analysis_utc_offset,
        timezone_field="analysis_timezone",
        utc_offset_field="analysis_utc_offset",
    )
    horoscope = build_ziwei_horoscope(
        chart=chart,
        gender=person.gender or "未知",
        target_seed=target_seed,
        birth_seed=seed,
        nominal_age_basis=nominal_age_basis,
        day_divide=day_divide,
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
        # Correct the old birth-seed receipt here; preserve it under an explicit
        # birth key. Analysis civil timezone/minute are independent birth inputs.
        "birth_context": {
            **_analysis_context_payload(seed),
            **context_basis(horoscope["calendar_basis"]["birth"]),
            "context_role": "birth",
        },
        "analysis_context": {
            **_analysis_context_payload(target_seed),
            **context_basis(horoscope["calendar_basis"]["target"]),
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
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    brightness_source: ZiweiBrightnessSource = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
) -> dict[str, Any]:
    if year_stem is not None and year_stem not in set(GAN):
        raise ValueError("year_stem 必须是单个天干")
    payload = build_ziwei_rules(
        year_stem,
        rule_profile=rule_profile,
        sihua_source=sihua_source,
        brightness_source=brightness_source,
        day_divide=day_divide,
    )
    payload["engine"] = "fatebridge-offline"
    return {
        "analysis_type": "紫微规则库",
        **payload,
    }
