"""SanShi (Liuren, Qimen, Taiyi) and Jinkou calculation services."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fatebridge.core.almanac import get_lunar_context, localize_datetime
from fatebridge.core.metaphysics.jinkou import (
    build_jinkou_board,
    build_jinkou_year_fate,
    build_natal_course,
    confirmed_natal_branch,
    natal_course_trace,
)
from fatebridge.core.metaphysics.liureng import (
    ShehaiMethod,
    add_year_fate_membership,
    apply_year_fate_emptiness,
    build_liureng_board,
    build_liureng_runyear,
    build_year_fate,
)
from fatebridge.core.metaphysics.ren_calendar import (
    MonthGeneralMode,
    require_ren_calendar,
    resolve_runyear_birth_clock,
    resolve_runyear_birth_zone,
)
from fatebridge.core.metaphysics.ren_diurnal import DiurnalMode
from fatebridge.core.metaphysics.ren_gods import DEFAULT_GUIREN_PROFILE, GuirenProfile
from fatebridge.core.metaphysics.seed import (
    _analysis_context_payload,
    build_analysis_seed,
)
from fatebridge.core.metaphysics.taiyi import (
    DEFAULT_TABLE_POLICY,
    TaiyiDayProfile,
    TaiyiShijiProfile,
    TaiyiTablePolicy,
    build_taiyi_board,
    civil_clock_resolution,
)
from fatebridge.core.qimen import build_qimen_with_options
from fatebridge.utils.birth_input import PersonInfo
from fatebridge.utils.civil_clock import format_utc_offset
from fatebridge.utils.civil_time import utc_calendar, utc_ordering_key
from fatebridge.utils.errors import calculation_guard
from fatebridge.utils.formatting import create_pillar_dict


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
    analysis_latitude: float | None = None,
    gender: str = "未知",
    use_true_solar_time: bool = True,
    true_solar_explicit: bool = True,
    is_diurnal: bool | None = None,
    diurnal_mode: DiurnalMode = "clock",
    month_general_mode: MonthGeneralMode = "solar_term",
    shehai_method: ShehaiMethod = "depth_first",
    harm_include_terminal: bool = False,
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
        seed,
        month_general_mode=month_general_mode,
        analysis_utc_offset=analysis_utc_offset,
    )
    liureng = build_liureng_board(
        seed,
        gender=gender,
        is_diurnal_override=is_diurnal,
        guiren_profile=guiren_profile,
        shehai_method=shehai_method,
        harm_include_terminal=harm_include_terminal,
        diurnal_mode=diurnal_mode,
        month_general_mode=month_general_mode,
        latitude=analysis_latitude,
    )
    liureng["engine"] = "fatebridge-offline"
    return {
        "analysis_type": "大六壬起课",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "liureng": liureng,
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
    analysis_latitude: float | None = None,
    use_true_solar_time: bool = False,
    true_solar_explicit: bool = False,
    is_diurnal: bool | None = None,
    diurnal_mode: DiurnalMode = "clock",
    month_general_mode: MonthGeneralMode = "solar_term",
    shehai_method: ShehaiMethod = "depth_first",
    harm_include_terminal: bool = False,
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
        seed,
        month_general_mode=month_general_mode,
        analysis_utc_offset=analysis_utc_offset,
    )
    liureng = build_liureng_board(
        seed,
        gender=person.gender or "未知",
        is_diurnal_override=is_diurnal,
        guiren_profile=guiren_profile,
        shehai_method=shehai_method,
        harm_include_terminal=harm_include_terminal,
        diurnal_mode=diurnal_mode,
        month_general_mode=month_general_mode,
        latitude=analysis_latitude,
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
    return {
        "analysis_type": "大六壬行年",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "runyear": runyear,
        "liureng": liureng,
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
    return {
        "analysis_type": "奇门遁甲",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "qimen": qimen,
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
    day_profile: TaiyiDayProfile | None = None,
    shiji_profile: TaiyiShijiProfile | None = None,
    table_policy: TaiyiTablePolicy = DEFAULT_TABLE_POLICY,
    use_true_solar_time: bool = False,
    true_solar_explicit: bool = True,
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
        day_profile=day_profile,
        shiji_profile=shiji_profile,
        table_policy=table_policy,
    )
    if analysis_utc_offset is not None:
        resolution = civil_clock_resolution(seed, analysis_utc_offset)
        taiyi["calendar_rules"]["civil_clock_resolution"] = resolution
        taiyi["calendar_summary"]["civil_clock_resolution"] = dict(resolution)
    taiyi["engine"] = "fatebridge-offline"
    return {
        "analysis_type": "太乙神数",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "taiyi": taiyi,
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
    analysis_latitude: float | None = None,
    gender: str = "未知",
    di_fen: str | None = None,
    natal_branch: str | None = None,
    birth_year_ganzhi: str | None = None,
    year_fate_age: int | None = None,
    use_true_solar_time: bool = True,
    true_solar_explicit: bool = True,
    is_diurnal: bool | None = None,
    diurnal_mode: DiurnalMode = "clock",
    month_general_mode: MonthGeneralMode = "solar_term",
    guiren_profile: GuirenProfile = DEFAULT_GUIREN_PROFILE,
) -> dict[str, Any]:
    del guiren_profile
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
        seed,
        month_general_mode=month_general_mode,
        analysis_utc_offset=analysis_utc_offset,
    )
    jinkou = build_jinkou_board(
        seed,
        None,
        gender=gender,
        di_fen=di_fen,
        natal_branch=natal,
        natal_branch_source=(
            "explicit_natal_branch"
            if natal_branch is not None
            else "explicit_birth_year_ganzhi" if birth_year_ganzhi is not None else None
        ),
        is_diurnal_override=is_diurnal,
        diurnal_mode=diurnal_mode,
        month_general_mode=month_general_mode,
        latitude=analysis_latitude,
    )
    jinkou["natal_course"] = build_natal_course(
        seed,
        None,
        birth_year_ganzhi=birth_year_ganzhi,
        natal_branch=natal_branch,
        gender=gender,
        is_diurnal=is_diurnal,
        diurnal_mode=diurnal_mode,
        month_general_mode=month_general_mode,
        latitude=analysis_latitude,
    )
    jinkou["year_fate"] = build_jinkou_year_fate(
        seed,
        None,
        birth_year_ganzhi=birth_year_ganzhi,
        age=year_fate_age,
        gender=gender,
        natal_branch=natal_branch,
        is_diurnal=is_diurnal,
        diurnal_mode=diurnal_mode,
        month_general_mode=month_general_mode,
        latitude=analysis_latitude,
    )
    jinkou["rule_trace"].append(
        {
            "rule_id": "jinkou.birth_xun_year_fate",
            "source_section": jinkou["year_fate"]["source_section"],
            "result": {k: v for k, v in jinkou["year_fate"].items() if k != "course"},
        }
    )
    jinkou["rule_trace"].append(natal_course_trace(jinkou["natal_course"]))
    jinkou["engine"] = "fatebridge-offline"
    return {
        "analysis_type": "金口诀",
        "analysis_context": _analysis_context_payload(seed),
        "four_pillars": create_pillar_dict(seed.pillars),
        "calendar_context": seed.calendar_context,
        "jinkou": jinkou,
    }
