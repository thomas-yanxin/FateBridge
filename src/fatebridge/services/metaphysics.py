"""
Chinese metaphysics services for FateBridge.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from fatebridge.core.almanac import (
    GAN,
    get_lunar_context,
    localize_datetime,
)
from fatebridge.core.local_techniques.qimen import (
    build_qimen_snapshot_text,
    build_qimen_with_options,
)
from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.jinkou import build_jinkou_board
from fatebridge.core.metaphysics.jinkou_natal_course import (
    build_natal_course,
    natal_course_trace,
)
from fatebridge.core.metaphysics.jinkou_year_fate import (
    build_jinkou_year_fate,
    confirmed_natal_branch,
)
from fatebridge.core.metaphysics.liureng import (
    build_liureng_board,
    build_liureng_runyear,
)
from fatebridge.core.metaphysics.liureng_emptiness import apply_year_fate_emptiness
from fatebridge.core.metaphysics.liureng_god_yin import add_year_fate_membership
from fatebridge.core.metaphysics.liureng_year_fate import build_year_fate
from fatebridge.core.metaphysics.ren_calendar import (
    require_ren_calendar,
    resolve_runyear_birth_clock,
    resolve_runyear_birth_zone,
)
from fatebridge.core.metaphysics.ren_gods import DEFAULT_GUIREN_PROFILE, GuirenProfile
from fatebridge.core.metaphysics.seed import (
    assemble_metaphysics_seed,
    build_analysis_seed,
)
from fatebridge.core.metaphysics.taiyi import build_taiyi_board
from fatebridge.core.metaphysics.taiyi_clock import civil_clock_resolution
from fatebridge.core.metaphysics.taiyi_shiji import TaiyiShijiProfile
from fatebridge.core.metaphysics.ziwei import (
    build_ziwei_chart,
    build_ziwei_horoscope,
    build_ziwei_rules,
)
from fatebridge.core.ziwei.ziwei_calendar import (
    context_basis,
)
from fatebridge.core.ziwei.ziwei_rulesets import (
    DEFAULT_ZIWEI_DAY_DIVIDE,
    DEFAULT_ZIWEI_PROFILE,
    ZiweiNatalLeapMonthPolicy,
)
from fatebridge.core.ziwei.ziwei_tables import ZiweiBrightnessSource
from fatebridge.core.ziwei.ziwei_time_input import birth_clock_receipt
from fatebridge.services.jinkou_snapshot import (
    build_jinkou_snapshot_text as _build_jinkou_snapshot_text,
)
from fatebridge.services.liureng_snapshot import build_liureng_snapshot_text
from fatebridge.services.snapshot_builders import (
    build_snapshot_export as _build_snapshot_export,
)
from fatebridge.services.taiyi_snapshot import build_taiyi_snapshot_text
from fatebridge.services.ziwei_snapshot import (
    build_ziwei_horoscope_snapshot_text,
    build_ziwei_rules_snapshot_text,
    build_ziwei_snapshot_text,
)
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.civil_clock import (
    format_utc_offset,
)
from fatebridge.utils.civil_time import (
    NominalClockLabel,
    utc_calendar,
    utc_ordering_key,
)
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import (
    create_pillar_dict,
    format_birth_datetime_display,
)
from fatebridge.utils.solar_time import (
    SOLAR_TIME_STRATEGY_APPARENT,
    normalize_birth_time,
)


def _build_person_seed(
    person: PersonInfo, *, birth_utc_offset: str | None = None
) -> MetaphysicsSeed:
    # note (birth clock): Zi Wei and BaZi both include the equation of time at hour boundaries.
    normalized_birth_time = normalize_birth_time(
        person,
        solar_time_strategy=SOLAR_TIME_STRATEGY_APPARENT,
        birth_utc_offset=birth_utc_offset,
    )
    civil = localize_datetime(
        normalized_birth_time.input_datetime, normalized_birth_time.timezone
    )
    return assemble_metaphysics_seed(
        civil=civil,
        clock=NominalClockLabel.from_local_datetime(
            normalized_birth_time.corrected_datetime
        ),
        timezone_name=normalized_birth_time.timezone,
        input_offset_visible=normalized_birth_time.input_datetime.utcoffset()
        is not None,
        longitude=normalized_birth_time.longitude,
        applied_true_solar=normalized_birth_time.applied,
        total_correction_minutes=normalized_birth_time.total_correction_minutes,
        birth_time_normalization=birth_clock_receipt(person, normalized_birth_time),
    )


class AnalysisClockContext(TypedDict):
    input_datetime: str
    corrected_datetime: str
    timezone: str
    longitude: float | None
    time_algorithm: str
    total_correction_minutes: float
    current_jieqi: str
    next_jieqi: str
    lunar_display: str | None


def _analysis_context_payload(seed: MetaphysicsSeed) -> AnalysisClockContext:
    lunar_context = seed.calendar_context.get("lunar_calendar") or {}
    return {
        "input_datetime": seed.input_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "corrected_datetime": seed.clock.isoformat(sep=" ", timespec="seconds"),
        "timezone": seed.timezone,
        "longitude": seed.longitude,
        "time_algorithm": "真太阳时" if seed.applied_true_solar else "直接时间",
        "total_correction_minutes": round(seed.total_correction_minutes, 2),
        "current_jieqi": seed.calendar_context["current_solar_term"]["name"],
        "next_jieqi": seed.calendar_context["next_solar_term"]["name"],
        "lunar_display": lunar_context.get("display"),
    }


@calculation_guard("紫微斗数命盘")
def calculate_ziwei_birth(
    person: PersonInfo,
    *,
    selected_sections: list[str] | None = None,
    render_snapshot: bool = True,
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
    result: dict[str, Any] = {
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
    if render_snapshot or selected_sections:
        snapshot_text = build_ziwei_snapshot_text(seed=seed, ziwei_birth=ziwei_birth)
        snapshot_export = _build_snapshot_export(
            technique="ziwei",
            snapshot_text=snapshot_text,
            selected_sections=selected_sections,
        )
        result.update(snapshot_text=snapshot_text, snapshot_export=snapshot_export)
    return result


@calculation_guard("紫微斗数运限")
def calculate_ziwei_horoscope(
    person: PersonInfo,
    *,
    target_year: int,
    target_month: int,
    target_day: int,
    target_hour: int,
    target_minute: int = 0,
    target_timezone: str = "Asia/Shanghai",
    target_utc_offset: str | None = None,
    birth_utc_offset: str | None = None,
    natal_leap_month_policy: ZiweiNatalLeapMonthPolicy | None = None,
    rule_profile: str = DEFAULT_ZIWEI_PROFILE,
    sihua_source: str = "rule_profile",
    brightness_source: ZiweiBrightnessSource = "rule_profile",
    day_divide: str = DEFAULT_ZIWEI_DAY_DIVIDE,
    nominal_age_basis: str = "birth_civil_timezone",
    selected_sections: list[str] | None = None,
    render_snapshot: bool = True,
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
        analysis_year=target_year,
        analysis_month=target_month,
        analysis_day=target_day,
        analysis_hour=target_hour,
        analysis_minute=target_minute,
        analysis_timezone=target_timezone,
        analysis_utc_offset=target_utc_offset,
        timezone_field="target_timezone",
        utc_offset_field="target_utc_offset",
    )
    horoscope = build_ziwei_horoscope(
        chart=chart,
        gender=person.gender or "未知",
        target_seed=target_seed,
        birth_seed=seed,
        nominal_age_basis=nominal_age_basis,
        day_divide=day_divide,
    )
    result: dict[str, Any] = {
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
        # birth key. Target civil timezone/minute are independent birth inputs.
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
    if render_snapshot or selected_sections:
        snapshot_text = build_ziwei_horoscope_snapshot_text(
            target_seed=target_seed, horoscope=horoscope
        )
        snapshot_export = _build_snapshot_export(
            technique="ziwei_horoscope",
            snapshot_text=snapshot_text,
            selected_sections=selected_sections,
        )
        result.update(snapshot_text=snapshot_text, snapshot_export=snapshot_export)
    return result


@calculation_guard("紫微规则库")
def calculate_ziwei_rules(
    year_stem: str | None = None,
    *,
    selected_sections: list[str] | None = None,
    render_snapshot: bool = True,
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
    result: dict[str, Any] = {
        "analysis_type": "紫微规则库",
        **payload,
    }
    if render_snapshot or selected_sections:
        snapshot_text = build_ziwei_rules_snapshot_text(payload)
        snapshot_export = _build_snapshot_export(
            technique="ziwei_rules",
            snapshot_text=snapshot_text,
            selected_sections=selected_sections,
        )
        result.update(snapshot_text=snapshot_text, snapshot_export=snapshot_export)
    return result


@calculation_guard("大六壬起课")
def calculate_liureng_gods(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_second: int = 0,
    analysis_timezone: str | None = None,
    analysis_utc_offset: str | None = None,
    analysis_longitude: float | None = None,
    gender: str = "未知",
    use_true_solar_time: bool = True,
    true_solar_explicit: bool = True,
    selected_sections: list[str] | None = None,
    is_diurnal: bool | None = None,
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
) -> dict[str, Any]:
    seed = build_analysis_seed(
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
        analysis_second=analysis_second,
        analysis_timezone=analysis_timezone,
        analysis_utc_offset=analysis_utc_offset,
        analysis_longitude=analysis_longitude,
        use_true_solar_time=use_true_solar_time,
        true_solar_explicit=true_solar_explicit,
    )
    seed.calendar_context["ren_calendar_policy"] = require_ren_calendar(
        seed, analysis_utc_offset=analysis_utc_offset
    )
    liureng = build_liureng_board(
        seed,
        gender=gender,
        is_diurnal_override=is_diurnal,
        guiren_profile=guiren_profile,
    )
    liureng["engine"] = "fatebridge-offline"
    snapshot_text = build_liureng_snapshot_text(seed=seed, liureng=liureng)
    snapshot_export = _build_snapshot_export(
        technique="liureng",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "大六壬起课",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "liureng": liureng,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("大六壬行年")
def calculate_liureng_runyear(
    person: PersonInfo,
    *,
    birth_utc_offset: str | None = None,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_second: int = 0,
    analysis_timezone: str | None = None,
    analysis_utc_offset: str | None = None,
    analysis_longitude: float | None = None,
    use_true_solar_time: bool = True,
    true_solar_explicit: bool = True,
    selected_sections: list[str] | None = None,
    is_diurnal: bool | None = None,
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
) -> dict[str, Any]:
    # 大六壬行年以「分析时刻」起课，不依赖出生四柱；
    # 出生民用时刻用于先后核对与出生农历年，不构建出生四柱。
    seed = build_analysis_seed(
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
        analysis_second=analysis_second,
        analysis_timezone=analysis_timezone,
        analysis_utc_offset=analysis_utc_offset,
        analysis_longitude=analysis_longitude,
        use_true_solar_time=use_true_solar_time,
        true_solar_explicit=true_solar_explicit,
    )
    birth_zone, birth_zone_source = resolve_runyear_birth_zone(
        person.birth_timezone, person.birth_place, person.birth_longitude
    )
    birth_moment, birth_clock = resolve_runyear_birth_clock(
        datetime(
            person.birth_year,
            person.birth_month,
            person.birth_day,
            person.birth_hour,
            person.birth_minute,
            person.birth_second or 0,
        ),
        birth_zone,
        birth_utc_offset,
        recorded_offset=person.birth_utc_offset,
    )
    birth_clock.update(birth_zone_source)
    # A same-zone datetime comparison ignores fold and orders wall labels.
    # Birth/analysis chronology must instead compare physical UTC instants.
    analysis_civil = localize_datetime(seed.input_datetime, seed.timezone)
    if utc_ordering_key(analysis_civil) < utc_ordering_key(birth_moment):
        raise ValueError("行年分析日期不能早于出生日期")
    birth_lunar = get_lunar_context(birth_moment, timezone_name=birth_zone)
    if birth_lunar is None:
        raise ValueError("行年需要出生日期的农历年")
    birth_lunar_year = birth_lunar.get("year")
    if not isinstance(birth_lunar_year, int):
        raise ValueError("行年需要出生日期的农历年")
    seed.calendar_context["ren_calendar_policy"] = require_ren_calendar(
        seed, analysis_utc_offset=analysis_utc_offset
    )
    liureng = build_liureng_board(
        seed,
        gender=person.gender or "未知",
        is_diurnal_override=is_diurnal,
        guiren_profile=guiren_profile,
    )
    liureng["engine"] = "fatebridge-offline"
    runyear = build_liureng_runyear(
        seed,
        gender=person.gender or "未知",
        birth_year=person.birth_year,
        birth_lunar_year=birth_lunar_year,
        age_reference_timezone=birth_zone,
    )
    runyear["engine"] = "fatebridge-offline"
    runyear["birth_civil_clock"] = birth_clock
    runyear["year_fate"] = build_year_fate(
        liureng,
        day_ganzhi="".join(seed.pillars["day"]),
        birth_lunar_year=birth_lunar_year,
        runyear_ganzhi=runyear["ganzhi"],
        runyear_reason=runyear.get("reason"),
    )
    add_year_fate_membership(liureng, runyear["year_fate"])
    apply_year_fate_emptiness(
        liureng["emptiness_evidence"],
        natal=runyear["year_fate"]["natal"]["earth_branch"],
        annual=runyear["year_fate"]["annual"]["earth_branch"],
    )
    snapshot_text = build_liureng_snapshot_text(
        seed=seed,
        liureng=liureng,
        runyear=runyear,
    )
    snapshot_export = _build_snapshot_export(
        technique="liureng",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "大六壬行年",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "runyear": runyear,
        "liureng": liureng,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("奇门遁甲")
def calculate_qimen_analysis(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_second: int = 0,
    analysis_timezone: str | None = None,
    analysis_utc_offset: str | None = None,
    analysis_longitude: float | None = None,
    use_true_solar_time: bool = True,
    true_solar_explicit: bool = True,
    qimen_options: dict[str, Any] | None = None,
    selected_sections: list[str] | None = None,
) -> dict[str, Any]:
    seed = build_analysis_seed(
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
        analysis_second=analysis_second,
        analysis_timezone=analysis_timezone,
        analysis_utc_offset=analysis_utc_offset,
        analysis_longitude=analysis_longitude,
        use_true_solar_time=use_true_solar_time,
        true_solar_explicit=true_solar_explicit,
    )
    qimen = build_qimen_with_options(seed, qimen_options)
    qimen["engine"] = "fatebridge-offline"
    if analysis_utc_offset is not None:
        offset = seed.input_datetime.utcoffset()
        assert offset is not None
        resolution = {
            "method": "explicit_input_offset_checked_against_named_zone",
            "timezone": seed.timezone,
            "input_utc_offset": analysis_utc_offset,
            "resolved_utc_offset": format_utc_offset(offset),
            "fold": seed.input_datetime.fold,
            "instant_utc": utc_calendar(seed.input_datetime).isoformat(),
        }
        qimen["calendar_policy"]["civil_clock_resolution"] = resolution
        qimen["rule_trace"].append(
            {
                "rule_id": "civil_clock_resolution",
                "source": "declared UTC offset checked against timezone rules",
                "section": "民用时刻消歧，非原典规则",
                "inputs": {
                    "timezone": seed.timezone,
                    "utc_offset": analysis_utc_offset,
                },
                "outputs": dict(resolution),
                "evidence_paths": ["qimen.calendar_policy.civil_clock_resolution"],
            }
        )
    snapshot_text = build_qimen_snapshot_text(seed=seed, qimen=qimen)
    snapshot_export = _build_snapshot_export(
        technique="qimen",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "奇门遁甲",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "qimen": qimen,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("太乙神数")
def calculate_taiyi_analysis(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_second: int = 0,
    analysis_timezone: str | None = None,
    analysis_utc_offset: str | None = None,
    analysis_longitude: float | None = None,
    gender: str = "未知",
    calculation_mode: str = "year",
    hour_profile: str | None = None,
    month_profile: str | None = None,
    year_profile: str | None = None,
    shiji_profile: TaiyiShijiProfile | None = None,
    use_true_solar_time: bool = False,
    true_solar_explicit: bool = True,
    selected_sections: list[str] | None = None,
) -> dict[str, Any]:
    seed = build_analysis_seed(
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
        analysis_second=analysis_second,
        analysis_timezone=analysis_timezone,
        analysis_utc_offset=analysis_utc_offset,
        analysis_longitude=analysis_longitude,
        use_true_solar_time=use_true_solar_time,
        true_solar_explicit=true_solar_explicit,
    )
    taiyi = build_taiyi_board(
        seed,
        gender=gender,
        calculation_mode=calculation_mode,
        hour_profile=hour_profile,
        month_profile=month_profile,
        year_profile=year_profile,
        shiji_profile=shiji_profile,
    )
    if analysis_utc_offset is not None:
        resolution = civil_clock_resolution(seed, analysis_utc_offset)
        taiyi["calendar_rules"]["civil_clock_resolution"] = resolution
        taiyi["calendar_summary"]["civil_clock_resolution"] = dict(resolution)
    taiyi["engine"] = "fatebridge-offline"
    snapshot_text = build_taiyi_snapshot_text(seed=seed, taiyi=taiyi)
    snapshot_export = _build_snapshot_export(
        technique="taiyi",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "太乙神数",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "taiyi": taiyi,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }


@calculation_guard("金口诀")
def calculate_jinkou_analysis(
    *,
    analysis_year: int,
    analysis_month: int,
    analysis_day: int,
    analysis_hour: int,
    analysis_minute: int = 0,
    analysis_second: int = 0,
    analysis_timezone: str | None = None,
    analysis_utc_offset: str | None = None,
    analysis_longitude: float | None = None,
    gender: str = "未知",
    di_fen: str | None = None,
    natal_branch: str | None = None,
    birth_year_ganzhi: str | None = None,
    year_fate_age: int | None = None,
    use_true_solar_time: bool = True,
    true_solar_explicit: bool = True,
    selected_sections: list[str] | None = None,
    is_diurnal: bool | None = None,
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
) -> dict[str, Any]:
    natal = confirmed_natal_branch(birth_year_ganzhi, natal_branch, year_fate_age)
    seed = build_analysis_seed(
        analysis_year=analysis_year,
        analysis_month=analysis_month,
        analysis_day=analysis_day,
        analysis_hour=analysis_hour,
        analysis_minute=analysis_minute,
        analysis_second=analysis_second,
        analysis_timezone=analysis_timezone,
        analysis_utc_offset=analysis_utc_offset,
        analysis_longitude=analysis_longitude,
        use_true_solar_time=use_true_solar_time,
        true_solar_explicit=true_solar_explicit,
    )
    seed.calendar_context["ren_calendar_policy"] = require_ren_calendar(
        seed, analysis_utc_offset=analysis_utc_offset
    )
    local_liureng = build_liureng_board(
        seed,
        gender=gender,
        is_diurnal_override=is_diurnal,
        guiren_profile=guiren_profile,
    )
    local_liureng["engine"] = "fatebridge-offline"
    liureng = local_liureng
    jinkou = build_jinkou_board(
        seed,
        local_liureng,
        gender=gender,
        di_fen=di_fen,
        natal_branch=natal,
        natal_branch_source=(
            "explicit_natal_branch"
            if natal_branch is not None
            else "explicit_birth_year_ganzhi" if birth_year_ganzhi is not None else None
        ),
        is_diurnal_override=is_diurnal,
    )
    jinkou["natal_course"] = build_natal_course(
        seed,
        local_liureng,
        birth_year_ganzhi=birth_year_ganzhi,
        natal_branch=natal_branch,
        gender=gender,
        is_diurnal=is_diurnal,
    )
    jinkou["year_fate"] = build_jinkou_year_fate(
        seed,
        local_liureng,
        birth_year_ganzhi=birth_year_ganzhi,
        age=year_fate_age,
        gender=gender,
        natal_branch=natal_branch,
        is_diurnal=is_diurnal,
    )
    jinkou["rule_trace"].append(
        {
            "rule_id": "jinkou.birth_xun_year_fate",
            "source_url": jinkou["year_fate"]["source_url"],
            "source_section": jinkou["year_fate"]["source_section"],
            "result": {k: v for k, v in jinkou["year_fate"].items() if k != "course"},
        }
    )
    jinkou["rule_trace"].append(natal_course_trace(jinkou["natal_course"]))
    jinkou["engine"] = "fatebridge-offline"
    snapshot_text = _build_jinkou_snapshot_text(seed=seed, jinkou=jinkou)
    snapshot_export = _build_snapshot_export(
        technique="jinkou",
        snapshot_text=snapshot_text,
        selected_sections=selected_sections,
    )
    return {
        "analysis_type": "金口诀",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "liureng": liureng,
        "jinkou": jinkou,
        "snapshot_text": snapshot_text,
        "snapshot_export": snapshot_export,
    }
