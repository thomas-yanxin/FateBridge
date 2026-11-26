"""Consolidated Taiyi calendars & entry points: year, month, day, hour, minute & fate."""

from __future__ import annotations

import json
from bisect import bisect_right
from copy import deepcopy
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

from pydantic import TypeAdapter
from typing_extensions import NotRequired

from fatebridge.core.almanac import (
    SolarTerm,
    _solar_terms_for_context_year,
    elapsed_seconds_between,
    get_day_ganzhi,
    get_lunar_context,
    get_solar_terms_for_year,
    is_calculated_solar_term,
    localize_datetime,
    lunar_supported_range_message,
)
from fatebridge.core.ephemeris_runtime import swe
from fatebridge.core.metaphysics.common import SEXAGENARY_INDEX, MetaphysicsSeed
from fatebridge.core.metaphysics.ren_calendar import compute_month_general
from fatebridge.core.metaphysics.taiyi.core import (
    BRANCHES,
    DEFAULT_TABLE_POLICY,
    TaiyiTablePolicy,
    assemble_board,
    attach_gate_board,
    attach_long_cycles,
    calendar_summary,
    compute_taiyi_fate_palaces,
    cyclic_core,
    key_ten_jing,
)
from fatebridge.core.solar_model_policy import solar_context_input_years
from fatebridge.utils.civil_clock import format_utc_offset
from fatebridge.utils.civil_time import (
    NominalClockLabel,
    ZonedCalendar,
    gregorian_date_parts,
    utc_calendar,
)
from fatebridge.utils.solar_time import calculate_equation_of_time_minutes
from fatebridge.utils.timezones import timezone_rules_metadata, validate_local_clock

TaiyiYearProfile = Literal[
    "jinjing_year_lunar_civil_v1",
    "jinjing_year_historical_table_v1",
    "jinjing_year_qiliang_table_v1",
]
DEFAULT_YEAR_PROFILE = "jinjing_year_lunar_civil_v1"
HISTORICAL_YEAR_PROFILE = "jinjing_year_historical_table_v1"
QILIANG_YEAR_PROFILE = "jinjing_year_qiliang_table_v1"
HISTORICAL_YEAR_PROFILES = {HISTORICAL_YEAR_PROFILE, QILIANG_YEAR_PROFILE}
YEAR_PROFILES = {DEFAULT_YEAR_PROFILE, *HISTORICAL_YEAR_PROFILES}

TaiyiMonthProfile = Literal["jinjing_month_jie_360_v1", "key_month_tianzheng_jie_v1"]
DEFAULT_MONTH_PROFILE = "jinjing_month_jie_360_v1"
KEY_MONTH_PROFILE = "key_month_tianzheng_jie_v1"
MONTH_PROFILES = {DEFAULT_MONTH_PROFILE, KEY_MONTH_PROFILE}

TaiyiDayProfile = Literal["jinjing_day_v1", "key_day_winter_jiazi_v1"]
DEFAULT_DAY_PROFILE: TaiyiDayProfile = "jinjing_day_v1"
KEY_DAY_PROFILE: TaiyiDayProfile = "key_day_winter_jiazi_v1"
DAY_PROFILES = {DEFAULT_DAY_PROFILE, KEY_DAY_PROFILE}

TaiyiHourProfile = Literal["jinjing_hour_solstice_v1", "key_hour_winter_jiazi_v1"]
DEFAULT_HOUR_PROFILE = "jinjing_hour_solstice_v1"
KEY_HOUR_PROFILE = "key_hour_winter_jiazi_v1"
HOUR_PROFILES = {DEFAULT_HOUR_PROFILE, KEY_HOUR_PROFILE}

YEAR_RULESET_ID = "jinjing_year_core_v1"
STEMS = "甲乙丙丁戊己庚辛壬癸"

JIE_ORDER = (
    "大雪",
    "小寒",
    "立春",
    "惊蛰",
    "清明",
    "立夏",
    "芒种",
    "小暑",
    "立秋",
    "白露",
    "寒露",
    "立冬",
)

SOLAR_ANCHOR_SCOPE = "记录本次实际采用的节气对象；resolution_provider是接口来源，ephemeris_model才是实际轨道模型。"


class CivilClockResolution(TypedDict):
    method: str
    timezone: str
    wall_datetime: str
    input_utc_offset: str
    resolved_utc_offset: str
    fold: int
    instant_utc: str
    timezone_rules: dict[str, str]


class PeriodFrame(TypedDict):
    accumulation: int
    yin: bool
    ruler_branch: str
    anchor: SolarTerm
    cycle_year: NotRequired[int]
    month_offset: NotRequired[int]
    month_origin: NotRequired[dict[str, Any]]
    anchor_clock: NotRequired[NominalClockLabel]
    target_clock: NotRequired[NominalClockLabel]
    hour_origin: NotRequired[dict[str, Any]]
    winter_anchor: NotRequired[SolarTerm]
    ke_index: NotRequired[int]


def validate_seed_civil_clock(seed: MetaphysicsSeed) -> None:
    validate_local_clock(seed.input_datetime, allow_ambiguous=seed.input_offset_visible)


def civil_clock_resolution(
    seed: MetaphysicsSeed, declared_offset: str
) -> CivilClockResolution:
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
        "instant_utc": utc_calendar(seed.input_datetime).isoformat(),
        "timezone_rules": timezone_rules_metadata(seed.timezone),
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
        utc = calendar.utc
        return NominalClockLabel(utc.ordinal, utc.microseconds_of_day).shifted(
            timedelta(
                minutes=4 * seed.longitude + calculate_equation_of_time_minutes(utc)
            )
        )
    zone = seed.input_datetime.tzinfo
    assert zone is not None
    local = ZonedCalendar(calendar.utc, zone)
    _, _, _, hour, minute, second, microsecond = local.local_parts
    return NominalClockLabel(
        local.local_ordinal,
        ((hour * 60 + minute) * 60 + second) * 1000000 + microsecond,
    )


def double_hour_slot(clock: NominalClockLabel) -> int:
    """23:00 starts 子, without rounding away boundary microseconds."""
    return clock.ordinal * 12 + (clock.microseconds_of_day + 3600_000000) // 7200_000000


def double_hour_ke_slot(clock: NominalClockLabel) -> tuple[int, int]:
    """Return (double_hour_slot, ke_in_hour 0..7 where 1 ke = 15 minutes from 23:00)."""
    total_micros = (
        clock.ordinal * 86400_000000 + clock.microseconds_of_day + 3600_000000
    )
    hour_slot, rem = divmod(total_micros, 7200_000000)
    return hour_slot, rem // 900_000000


def previous_solar_term(instant: datetime, names: tuple[str, ...]) -> SolarTerm:
    instant_day = utc_calendar(instant).julian_day_exact()
    context_year = instant.year
    low, high = solar_context_input_years(context_year)
    candidates: list[SolarTerm] = []
    for year in range(max(1, context_year - 1), min(9999, context_year + 1) + 1):
        terms = (
            _solar_terms_for_context_year(year, "UTC", context_year)
            if low <= context_year <= high and not low <= year <= high
            else get_solar_terms_for_year(year, "UTC")
        )
        candidates.extend(
            term
            for term in terms
            if term.name in names and term.point.day <= instant_day
        )
    if not candidates:
        raise ValueError("无法取得起盘之前的太乙节气锚点")
    term = max(candidates, key=lambda t: t.point.day)
    if not is_calculated_solar_term(term):
        raise ValueError("太乙月/日/时计要求天文节气实刻")
    return term


def julian_to_proleptic_gregorian(year: int, month: int, day: int) -> date:
    if (
        any(type(n) is not int for n in (year, month, day))
        or not 1 <= year <= 9999
        or not 1 <= month <= 12
        or not 1 <= day <= 31
    ):
        raise ValueError("须明确给出有效的正整数儒略历年月日")
    if swe is None:
        raise ValueError("儒略历转换需要 Swiss Ephemeris 的日历算术接口")
    julian_day_at_noon = swe.julday(year, month, day, 12.0, swe.JUL_CAL)
    if swe.revjul(julian_day_at_noon, swe.JUL_CAL)[:3] != (year, month, day):
        raise ValueError("无效儒略历日期，不能自动进位")
    gy, gm, gd = swe.revjul(julian_day_at_noon, swe.GREG_CAL)[:3]
    return date(gy, gm, gd)


@lru_cache(maxsize=2)
def historical_month_table(
    profile: str = HISTORICAL_YEAR_PROFILE,
) -> tuple[dict[str, Any], tuple[date, ...]]:
    if profile not in HISTORICAL_YEAR_PROFILES:
        raise ValueError("year_profile须明确选择已发布历史年计配置")
    filename = (
        "taiyi-qiliang-year-months-v1.json"
        if profile == QILIANG_YEAR_PROFILE
        else "taiyi-historical-year-months-v1.json"
    )
    path = Path(__file__).resolve().parents[3] / "data/classical" / filename
    data = json.loads(path.read_bytes())
    rows = data["months"]
    dates = tuple(
        julian_to_proleptic_gregorian(*map(int, row["julian_start"].split("-")))
        for row in rows
    )
    if any((b - a).days not in (29, 30) for a, b in zip(dates, dates[1:])):
        raise ValueError("历史月首表不是连续大小月")
    return data, dates


def historical_year_context(
    civil_date: date, *, profile: str = HISTORICAL_YEAR_PROFILE
) -> dict[str, Any]:
    data, dates = historical_month_table(profile)
    if not dates[0] <= civil_date < dates[-1]:
        raise ValueError(
            f"所选太乙历史历表仅覆盖推算公历{dates[0].isoformat()}至{dates[-1].isoformat()}之前"
        )
    i = bisect_right(dates, civil_date) - 1
    row = data["months"][i]
    day = (civil_date - dates[i]).days + 1
    year = row["year"]
    return {
        "year": year,
        "month": row["month"],
        "day": day,
        "is_leap_month": row["is_leap_month"],
        "display": f"{year}年{'闰' if row['is_leap_month'] else ''}{row['month']}月{day}日（{row['reign_label']}）",
        "julian_month_start": row["julian_start"],
        "gregorian_month_start": dates[i].isoformat(),
    }


def civil_lunar_evidence(lunar: dict[str, Any], civil_date: date) -> dict[str, Any]:
    source = lunar.get("conversion_source")
    return {
        "civil_date": civil_date.isoformat(),
        **{key: lunar[key] for key in ("year", "month", "day", "is_leap_month")},
        "display": f"{lunar['year']}年{lunar['display']}",
        "clock_basis": "civil_date_before_true_solar_correction",
        "provider": "shared_offline_lunar_calendar",
        "conversion_source": deepcopy(source),
    }


def jinjing_month_origin(cycle_year: int, month_offset: int) -> dict[str, Any]:
    counted_year = cycle_year + 1
    annual = 1937281 + counted_year - 724
    accumulation = (annual - 1) * 12 + month_offset + 1
    return {
        "profile": DEFAULT_MONTH_PROFILE,
        "cycle_year": cycle_year,
        "counted_year": counted_year,
        "annual_accumulation": annual,
        "month_offset": month_offset,
        "month_number_from_daxue": month_offset + 1,
        "accumulation": accumulation,
        "counter_unit": "twelve_jie_months",
    }


def key_month_origin(cycle_year: int, month_offset: int) -> dict[str, Any]:
    nominal_year = cycle_year + int(month_offset >= 2)
    nominal_month = (month_offset + 10) % 12 + 1
    annual = 10155478 + nominal_year - 1561
    full = (annual - 1) * 12 + 2 + nominal_month
    shortcut_completed = nominal_year - 1504
    shortcut = shortcut_completed * 12 + 2 + nominal_month
    return {
        "cycle_year": cycle_year,
        "nominal_year": nominal_year,
        "nominal_month": nominal_month,
        "source_epoch_year": 1561,
        "source_epoch_accumulation": 10155478,
        "annual_accumulation": annual,
        "accumulation": full,
        "shortcut_count": shortcut,
        "shared_cycle_lcm": 720,
    }


def key_day_origin(
    winter_clock: NominalClockLabel, target_clock: NominalClockLabel
) -> dict[str, Any]:
    winter_ganzhi = get_day_ganzhi(*winter_clock.date_parts)
    origin_ordinal = winter_clock.ordinal - SEXAGENARY_INDEX[winter_ganzhi]
    if origin_ordinal < 1:
        raise ValueError("冬至前甲子超出可表达日历范围")
    origin = NominalClockLabel(origin_ordinal, 0)
    count = target_clock.ordinal - origin_ordinal + 1
    if count < 1:
        raise ValueError("日计日期早于冬至前甲子")
    return {
        "winter_clock": winter_clock.isoformat(),
        "winter_day_ganzhi": winter_ganzhi,
        "origin_effective_date": origin.date_isoformat(),
        "target_effective_date": target_clock.date_isoformat(),
        "target_day_ganzhi": get_day_ganzhi(*target_clock.date_parts),
        "accumulation": count,
        "day_boundary": "00:00_selected_clock_modern_convention",
        "same_day_jiazi_included": True,
        "alternative_strict_previous_count": (
            count + 60 if winter_ganzhi == "甲子" else None
        ),
    }


def jinjing_day_origin(target_clock: NominalClockLabel) -> dict[str, Any]:
    """Native continuous JinJing sexagenary day count (甲子日 ≡ 1 mod 60, invariant mod 720)."""
    # Proleptic Gregorian ordinal 46 = 0001-02-15 is 甲子 (index 0 in 60-cycle).
    # Adding 720 preserves modulo 60 (ganzhi), modulo 72 (ju), and modulo 240 (gates).
    count = target_clock.ordinal - 46 + 721
    ganzhi = get_day_ganzhi(*target_clock.date_parts)
    return {
        "target_effective_date": target_clock.date_isoformat(),
        "target_day_ganzhi": ganzhi,
        "accumulation": count,
        "day_boundary": "00:00_selected_clock_sexagenary_continuous",
        "cycle_60_position": (count - 1) % 60 + 1,
    }


def key_hour_origin(
    winter_clock: NominalClockLabel, target_clock: NominalClockLabel
) -> dict[str, Any]:
    winter_ordinal = double_hour_slot(winter_clock) // 12
    winter_day = NominalClockLabel(winter_ordinal, 0)
    winter_ganzhi = get_day_ganzhi(*winter_day.date_parts)
    origin_ordinal = winter_ordinal - SEXAGENARY_INDEX[winter_ganzhi]
    if origin_ordinal < 2:
        raise ValueError("冬至前甲子锚点超出可表达日期")
    origin_day = NominalClockLabel(origin_ordinal, 0)
    origin_clock = origin_day.shifted(timedelta(hours=-1))
    target_slot = double_hour_slot(target_clock)
    day_number = target_slot // 12 - origin_ordinal + 1
    branch_index = target_slot % 12
    if day_number < 1:
        raise ValueError("时计所求日期早于冬至前甲子锚点")
    accumulation = (day_number - 1) * 12 + branch_index + 1
    effective_day = NominalClockLabel(target_slot // 12, 0)
    return {
        "winter_clock": winter_clock.isoformat(),
        "winter_effective_date": winter_day.date_isoformat(),
        "winter_day_ganzhi": winter_ganzhi,
        "origin_effective_date": origin_day.date_isoformat(),
        "origin_day_ganzhi": "甲子",
        "origin_clock": origin_clock.isoformat(),
        "target_effective_date": effective_day.date_isoformat(),
        "target_day_ganzhi": get_day_ganzhi(*effective_day.date_parts),
        "day_number": day_number,
        "hour_number": branch_index + 1,
        "accumulation": accumulation,
        "gate_cycle_counter": (accumulation - 1) % 120 + 1,
        "day_boundary": "23:00_Zi_initial_modern_convention",
    }


def winter_origin_selection(
    origin: dict[str, Any], winter: dict[str, Any], clock_basis: str
) -> dict[str, Any]:
    return {
        "policy_id": "latest_elapsed_winter_solstice_instant_modern_v1",
        "selection_switch_basis": "winter_solstice_instant",
        "selected_winter_utc": winter["datetime_with_offset"],
        "count_origin_date": origin["origin_effective_date"],
        "count_origin_clock": origin.get(
            "origin_clock", origin["origin_effective_date"] + "T00:00:00"
        ),
        "clock_basis": clock_basis,
    }


@lru_cache(maxsize=1)
def _historical_date_records() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[3]
        / "data/classical/taiyi-key-historical-dates-v1.json"
    )
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def source_date_reference(
    civil_date: date,
    mode: str,
    accumulation: int,
    day_ganzhi: str,
    hour_branch: str | None = None,
) -> dict[str, Any] | None:
    data = _historical_date_records()
    target_iso = civil_date.isoformat()
    matches = [
        r
        for r in data["records"]
        if r.get("mode") == mode and r.get("gregorian_date") == target_iso
    ]
    if not matches:
        return None
    row = matches[0]
    return {
        "case_id": row["id"],
        "source_date": row["chinese_date"],
        "normalized_gregorian_date": row["gregorian_date"],
        "source_day_ganzhi": row["day_ganzhi"],
        "actual_day_ganzhi": day_ganzhi,
        "source_accumulation": row["expected_accumulation"],
        "actual_accumulation": accumulation,
        "day_ganzhi_matches": day_ganzhi == row["day_ganzhi"],
        "counter_matches": accumulation == row["expected_accumulation"],
        "source_hour_branch": row.get("source_hour_branch"),
        "actual_hour_branch": hour_branch,
    }


def yearly_core(
    year: int,
    *,
    shiji_profile: str | None = None,
    table_policy: TaiyiTablePolicy = DEFAULT_TABLE_POLICY,
) -> dict[str, Any]:
    if type(year) is not int or year < 1:
        raise ValueError("年计需要正整数公元年份")
    accumulation = 1937281 + year - 724
    core = cyclic_core(
        accumulation, shiji_profile=shiji_profile, table_policy=table_policy
    )
    core.update(
        kook_year=("理天", "理地", "理人")[(accumulation - 1) % 3],
        suijun=BRANCHES[(year - 4) % 12],
        heshen=BRANCHES[(1 - (year - 4)) % 12],
    )
    return core


def build_year_board(
    seed: MetaphysicsSeed,
    gender: str,
    year_profile: str | None = None,
    *,
    shiji_profile: str | None = None,
    table_policy: TaiyiTablePolicy = DEFAULT_TABLE_POLICY,
) -> dict[str, Any]:
    if year_profile is not None and (
        not isinstance(year_profile, str) or year_profile not in YEAR_PROFILES
    ):
        raise ValueError("year_profile须明确选择已发布年计配置")
    instant = localize_datetime(seed.input_datetime, seed.timezone)
    historical = (
        historical_year_context(instant.date(), profile=year_profile)
        if year_profile is not None and year_profile in HISTORICAL_YEAR_PROFILES
        else None
    )
    lunar = (
        historical
        if historical
        else get_lunar_context(seed.input_datetime, timezone_name=seed.timezone)
    )
    if lunar is None:
        raise ValueError("太乙年计需要农历年，" + lunar_supported_range_message())
    year = lunar["year"]
    if not isinstance(year, int):
        raise ValueError("太乙年计农历年份必须是整数")
    core = yearly_core(year, shiji_profile=shiji_profile, table_policy=table_policy)
    board = assemble_board(core, calculation_mode="year")
    board.update(
        style_label="太乙金镜式经·年计",
        accumulation_label=f"年计积年数：{core['accumulation']}",
        rotation="顺布",
        life_method="年计",
        calendar_rules={
            "year": year,
            "year_boundary": (
                "historical_printed_lunar_new_year_civil_date"
                if historical
                else "lunar_new_year_civil_date"
            ),
            "year_boundary_status": "implemented",
            "year_ganzhi": STEMS[(year - 4) % 10] + core["suijun"],
            "civil_datetime": instant.isoformat(),
            "timezone": seed.timezone,
            "solar_correction_affects_year": False,
            **(
                {"year_profile": year_profile, "historical_calendar": historical}
                if historical
                else {}
            ),
        },
        ruleset={
            "id": YEAR_RULESET_ID,
            "version": "2.0.0",
            "author": "FateBridge contributors",
            "classical_author": "唐·王希明",
            "source_title": "太乙金镜式经（四库全书本）",
            "time_granularity": "year",
            "classical_conformance": "implemented",
            "classical_acceptance_passed": True,
        },
        interpretation_scope={
            "calculation": "年计太乙、二目、计神、主客算、四将及三门五将",
            "gender_used": False,
        },
    )
    if not historical:
        board["calendar_rules"]["civil_lunar_calendar"] = civil_lunar_evidence(
            lunar, instant.date()
        )
    board["calendar_summary"] = calendar_summary(board)
    attach_long_cycles(board, year)
    attach_gate_board(board, "year", year)
    return board


def build_day_board(
    seed: MetaphysicsSeed,
    gender: str,
    day_profile: str | None = None,
    *,
    shiji_profile: str | None = None,
    table_policy: TaiyiTablePolicy = DEFAULT_TABLE_POLICY,
) -> dict[str, Any]:
    profile = DEFAULT_DAY_PROFILE if day_profile is None else day_profile
    if profile not in DAY_PROFILES:
        raise ValueError("day_profile须选择jinjing_day_v1或key_day_winter_jiazi_v1")
    instant = localize_datetime(seed.input_datetime, seed.timezone)
    validate_seed_civil_clock(seed)
    anchor = previous_solar_term(instant, ("冬至", "夏至"))
    winter = previous_solar_term(instant, ("冬至",))
    target_clock = nominal_clock_label(instant, seed)
    yin = anchor.name == "夏至"

    if profile == KEY_DAY_PROFILE:
        origin = key_day_origin(
            nominal_clock_label(winter.calendar, seed), target_clock
        )
        origin.update(
            winter_anchor_utc=winter.calendar.utc.isoformat(),
            winter_anchor_provider=winter.resolution_provider,
        )
        source_title = "太乙金钥匙续集·日计"
        classical_author = "太乙金钥匙续集"
        style_label = "太乙金钥匙·日计"
    else:
        origin = jinjing_day_origin(target_clock)
        source_title = "太乙金镜式经·日计"
        classical_author = "唐·王希明"
        style_label = "太乙金镜式经·日计"

    count = origin["accumulation"]
    ruler = origin["target_day_ganzhi"][1]
    core = cyclic_core(
        count, yin=yin, shiji_profile=shiji_profile, table_policy=table_policy
    )
    core.update(
        ruler_branch=ruler,
        ruler_label="日支",
        heshen=BRANCHES[(1 - BRANCHES.index(ruler)) % 12],
    )
    board = assemble_board(core, calculation_mode="day")
    clock_basis = (
        "local_apparent_solar" if seed.applied_true_solar else "civil_wall_clock"
    )
    board.update(
        style_label=style_label,
        accumulation_label=f"日计积日：{count}",
        rotation="逆布" if yin else "顺布",
        life_method="日计",
        solar_anchors={
            "boundary": anchor.as_dict(),
            **(
                {"winter_origin": winter.as_dict()}
                if profile == KEY_DAY_PROFILE
                else {}
            ),
        },
        solar_anchor_scope=SOLAR_ANCHOR_SCOPE,
        calendar_rules={
            "input_calendar": "proleptic_gregorian",
            "calculation_mode": "day",
            "day_profile": profile,
            "day_origin": origin,
            "civil_datetime": instant.isoformat(),
            "timezone": seed.timezone,
            "anchor_name": anchor.name,
            "anchor_utc": anchor.calendar.utc.isoformat(),
            "anchor_provider": anchor.resolution_provider,
            "counter": count,
            "palace_day_number": (count - 1) % 3 + 1,
            "clock_basis": clock_basis,
            "target_clock": target_clock.isoformat(),
        },
        ruleset={
            "id": profile,
            "version": "2.0.0",
            "author": "FateBridge contributors",
            "classical_author": classical_author,
            "source_title": source_title,
            "time_granularity": "selected_clock_day",
            "classical_conformance": "implemented",
            "classical_acceptance_passed": True,
        },
        interpretation_scope={
            "calculation": "日计阴阳局、二目、计神、主客算及四将、三门五将",
            "gender_used": False,
        },
        long_cycles={
            "status": "not_computed_for_selected_mode",
            "time_granularity": "year",
        },
        long_cycle_summary={"status": "not_computed_for_selected_mode"},
        extra_palace_marks=[],
    )
    if profile == KEY_DAY_PROFILE:
        board["ten_jing"] = key_ten_jing(count, yin)
        board["winter_origin_selection"] = winter_origin_selection(
            origin, board["solar_anchors"]["winter_origin"], clock_basis
        )
    attach_gate_board(board, "day")
    board["calendar_summary"] = calendar_summary(board)
    return board


def period_frame(
    seed: MetaphysicsSeed,
    mode: str,
    hour_profile: str | None = None,
    month_profile: str | None = None,
) -> PeriodFrame:
    if month_profile is not None and (
        mode != "month" or month_profile not in MONTH_PROFILES
    ):
        raise ValueError("month_profile仅用于month，须选择已发布月计配置")
    if hour_profile is not None and (
        mode != "hour" or hour_profile not in HOUR_PROFILES
    ):
        raise ValueError("hour_profile仅用于hour，须选择已发布时计配置")
    instant = localize_datetime(seed.input_datetime, seed.timezone)
    validate_seed_civil_clock(seed)

    if mode == "month":
        term = previous_solar_term(instant, JIE_ORDER)
        month_offset = JIE_ORDER.index(term.name)
        cycle_year = (
            term.calendar.utc.date_parts[0]
            if term.name == "大雪"
            else term.calendar.utc.date_parts[0] - int(term.name == "小寒")
        )
        if term.name not in ("大雪", "小寒"):
            cycle_year -= 1
        origin = (
            key_month_origin(cycle_year, month_offset)
            if month_profile == KEY_MONTH_PROFILE
            else jinjing_month_origin(cycle_year, month_offset)
        )
        return {
            "accumulation": origin["accumulation"],
            "yin": False,
            "ruler_branch": BRANCHES[month_offset],
            "anchor": term,
            "cycle_year": cycle_year,
            "month_offset": month_offset,
            "month_origin": origin,
        }

    term = previous_solar_term(instant, ("冬至", "夏至"))
    anchor_clock = nominal_clock_label(term.calendar, seed)
    target_clock = nominal_clock_label(instant, seed)
    if mode == "hour" and hour_profile == KEY_HOUR_PROFILE:
        winter = previous_solar_term(instant, ("冬至",))
        origin = key_hour_origin(
            nominal_clock_label(winter.calendar, seed), target_clock
        )
        origin.update(
            winter_anchor_utc=winter.calendar.utc.isoformat(),
            winter_anchor_provider=winter.resolution_provider,
        )
        return {
            "accumulation": origin["accumulation"],
            "yin": term.name == "夏至",
            "ruler_branch": BRANCHES[double_hour_slot(target_clock) % 12],
            "anchor": term,
            "anchor_clock": anchor_clock,
            "target_clock": target_clock,
            "hour_origin": origin,
            "winter_anchor": winter,
        }

    hour_slot, ke_in_hour = double_hour_ke_slot(target_clock)
    hour_accum = hour_slot - double_hour_slot(anchor_clock) + 1
    if hour_accum < 1:
        raise ValueError("太乙时/分计的时钟序列早于所选至点")
    if mode == "hour":
        return {
            "accumulation": hour_accum,
            "yin": term.name == "夏至",
            "ruler_branch": BRANCHES[hour_slot % 12],
            "anchor": term,
            "anchor_clock": anchor_clock,
            "target_clock": target_clock,
        }
    if mode == "minute":
        minute_accum = (hour_accum - 1) * 8 + ke_in_hour + 1
        return {
            "accumulation": minute_accum,
            "yin": term.name == "夏至",
            "ruler_branch": BRANCHES[hour_slot % 12],
            "anchor": term,
            "anchor_clock": anchor_clock,
            "target_clock": target_clock,
            "ke_index": ke_in_hour + 1,
        }
    raise ValueError("period_frame仅支持month/hour/minute")


def build_period_board(
    seed: MetaphysicsSeed,
    gender: str,
    mode: str,
    hour_profile: str | None = None,
    month_profile: str | None = None,
    *,
    shiji_profile: str | None = None,
    table_policy: TaiyiTablePolicy = DEFAULT_TABLE_POLICY,
) -> dict[str, Any]:
    instant = localize_datetime(seed.input_datetime, seed.timezone)
    frame = period_frame(seed, mode, hour_profile, month_profile)
    is_key_month = mode == "month" and month_profile == KEY_MONTH_PROFILE
    is_key_hour = mode == "hour" and hour_profile == KEY_HOUR_PROFILE
    clock_basis = (
        "local_apparent_solar" if seed.applied_true_solar else "civil_wall_clock"
    )
    core = cyclic_core(
        frame["accumulation"],
        yin=frame["yin"],
        shiji_profile=shiji_profile,
        table_policy=table_policy,
    )
    ruler = frame["ruler_branch"]
    core["ruler_branch"] = ruler
    core["ruler_label"] = (
        "月建" if mode == "month" else ("时支（刻家）" if mode == "minute" else "时支")
    )
    he_anchor = (
        seed.pillars["day"][1]
        if mode in {"hour", "minute"} and not is_key_hour
        else ruler
    )
    core["heshen"] = BRANCHES[(1 - BRANCHES.index(he_anchor)) % 12]
    board = assemble_board(core, calculation_mode=mode)
    term = frame["anchor"]

    if mode == "month":
        profile = KEY_MONTH_PROFILE if is_key_month else DEFAULT_MONTH_PROFILE
        label = "月计"
        granularity = "solar_month"
    elif mode == "minute":
        profile = "taiyi_ke_minute_v1"
        label = "刻家太乙（分计）"
        granularity = "quarter_hour"
    else:
        profile = KEY_HOUR_PROFILE if is_key_hour else DEFAULT_HOUR_PROFILE
        label = "时计"
        granularity = "double_hour"

    calendar: dict[str, Any] = {
        "calculation_mode": mode,
        "civil_datetime": instant.isoformat(),
        "timezone": seed.timezone,
        "anchor_name": term.name,
        "anchor_utc": term.calendar.utc.isoformat(),
        "anchor_provider": term.resolution_provider,
        "counter": frame["accumulation"],
        "seconds_from_anchor": elapsed_seconds_between(term.point, instant),
    }
    if mode == "month":
        calendar.update(
            month_profile=profile,
            cycle_year=frame["cycle_year"],
            month_offset=frame["month_offset"],
            month_origin=frame["month_origin"],
            clock_basis="astronomical_jie_instant",
        )
    elif mode == "minute":
        calendar.update(
            minute_profile=profile,
            clock_basis=clock_basis,
            anchor_clock=frame["anchor_clock"].isoformat(),
            target_clock=frame["target_clock"].isoformat(),
            ke_index=frame["ke_index"],
            ke_per_hour=8,
        )
    else:
        calendar.update(
            hour_profile=profile,
            clock_basis=clock_basis,
            anchor_clock=frame["anchor_clock"].isoformat(),
            target_clock=frame["target_clock"].isoformat(),
            **({"hour_origin": frame["hour_origin"]} if is_key_hour else {}),
        )

    board.update(
        style_label=f"太乙·{label}",
        accumulation_label=f"{label}积数：{frame['accumulation']}",
        rotation="逆布" if frame["yin"] else "顺布",
        life_method=label,
        solar_anchors={
            "boundary": term.as_dict(),
            **(
                {"winter_origin": frame["winter_anchor"].as_dict()}
                if "winter_anchor" in frame
                else {}
            ),
        },
        solar_anchor_scope=SOLAR_ANCHOR_SCOPE,
        calendar_rules=calendar,
        ruleset={
            "id": profile,
            "version": "2.0.0",
            "author": "FateBridge contributors",
            "classical_author": (
                "太乙金钥匙续集" if (is_key_month or is_key_hour) else "唐·王希明"
            ),
            "source_title": (
                "太乙金钥匙续集" if (is_key_month or is_key_hour) else "太乙金镜式经"
            ),
            "time_granularity": granularity,
            "classical_conformance": "implemented",
            "classical_acceptance_passed": True,
        },
        interpretation_scope={
            "calculation": f"{label}太乙阴阳局及三门五将",
            "gender_used": False,
        },
        long_cycles={
            "status": "not_computed_for_selected_mode",
            "time_granularity": "year",
        },
        long_cycle_summary={"status": "not_computed_for_selected_mode"},
        extra_palace_marks=[],
    )
    if is_key_hour:
        board["winter_origin_selection"] = winter_origin_selection(
            frame["hour_origin"], board["solar_anchors"]["winter_origin"], clock_basis
        )
    attach_gate_board(board, mode)
    board["calendar_summary"] = calendar_summary(board)
    return board


def build_fate_board(
    seed: MetaphysicsSeed,
    gender: str,
    *,
    shiji_profile: str | None = None,
    table_policy: TaiyiTablePolicy = DEFAULT_TABLE_POLICY,
) -> dict[str, Any]:
    """Build《太乙命法》board with annual base, 十二命宫, 命/身宫, and 天将/十六神."""
    board = build_year_board(
        seed, gender, shiji_profile=shiji_profile, table_policy=table_policy
    )
    instant = localize_datetime(seed.input_datetime, seed.timezone)
    general_info = compute_month_general(seed)
    fate_palaces = compute_taiyi_fate_palaces(
        month_general=general_info["branch"],
        birth_hour_branch=seed.pillars["hour"][1],
        lunar_year=board["calendar_rules"]["year"],
        gender=gender,
    )
    board["style_label"] = "太乙命法·先天十二宫"
    board["life_method"] = f"太乙命法（{gender}）"
    board["fate_palaces"] = fate_palaces
    board["calendar_rules"]["calculation_mode"] = "fate"
    board["calendar_summary"] = calendar_summary(board)
    board["interpretation_scope"] = {
        "calculation": "太乙命法出生盘（年计定局、十二命宫、身命宫与十六神）",
        "gender_used": True,
    }
    board["ruleset"].update(id="taiyi_mingfa_v1", time_granularity="year")
    board["long_cycles"]["ruleset"]["classical_acceptance_passed"] = True
    return board


def build_taiyi_board(
    seed: MetaphysicsSeed,
    gender: str,
    *,
    calculation_mode: str = "year",
    hour_profile: str | None = None,
    month_profile: str | None = None,
    year_profile: str | None = None,
    day_profile: str | None = None,
    shiji_profile: str | None = None,
    table_policy: TaiyiTablePolicy = DEFAULT_TABLE_POLICY,
) -> dict[str, Any]:
    """Build Taiyi board for year, month, day, hour, minute, or fate."""
    if year_profile is not None and calculation_mode != "year":
        raise ValueError("year_profile仅用于year年计")
    if month_profile is not None and calculation_mode != "month":
        raise ValueError("month_profile仅用于month月计")
    if day_profile is not None and calculation_mode != "day":
        raise ValueError("day_profile仅用于day日计")
    if hour_profile is not None and calculation_mode != "hour":
        raise ValueError("hour_profile仅用于hour时计")

    if calculation_mode == "year":
        return build_year_board(
            seed,
            gender,
            year_profile,
            shiji_profile=shiji_profile,
            table_policy=table_policy,
        )
    if calculation_mode == "day":
        return build_day_board(
            seed,
            gender,
            day_profile,
            shiji_profile=shiji_profile,
            table_policy=table_policy,
        )
    if calculation_mode == "fate":
        return build_fate_board(
            seed, gender, shiji_profile=shiji_profile, table_policy=table_policy
        )
    if calculation_mode in {"month", "hour", "minute"}:
        return build_period_board(
            seed,
            gender,
            calculation_mode,
            hour_profile,
            month_profile,
            shiji_profile=shiji_profile,
            table_policy=table_policy,
        )
    raise ValueError("Taiyi calculation_mode仅支持year/month/day/hour/minute/fate")
