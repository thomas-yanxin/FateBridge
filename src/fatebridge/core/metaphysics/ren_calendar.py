"""Clock policy, solar-term dependencies, month general and metadata for Liu Ren / Jin Kou."""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Any, Literal

import swisseph as swe

from fatebridge.core.almanac import (
    SolarTerm,
    get_adjacent_solar_terms,
    get_bazi_month_boundaries,
    get_lunar_context,
    get_solar_terms_for_year,
    is_calculated_solar_term,
)
from fatebridge.core.astro import time_scales, utc_policy
from fatebridge.core.bazi.calendar import BaZiCalendar, get_bazi_year
from fatebridge.core.ephemeris_runtime import ephemeris_call
from fatebridge.core.metaphysics.common import (
    YUE_JIANG_NAMES,
    MetaphysicsSeed,
)
from fatebridge.core.metaphysics.hko_term_dates import published_date_reference
from fatebridge.core.solar_term_runtime import loaded_clock_profile_key
from fatebridge.utils.civil_clock import format_utc_offset, resolve_civil_clock
from fatebridge.utils.civil_time import NominalClockLabel, UTCCalendar, utc_calendar
from fatebridge.utils.data import SEXAGENARY_CYCLE, SEXAGENARY_INDEX
from fatebridge.utils.errors import EphemerisSourceError, ParameterError
from fatebridge.utils.places import DEFAULT_BIRTH_TIMEZONE, resolve_birth_place_context
from fatebridge.utils.timezones import timezone_rules_metadata

MonthGeneralMode = Literal["solar_term", "true_solar_longitude"]

LIURENG_MONTH_GENERAL_BY_TERM = {
    "大寒": "子",
    "立春": "子",
    "雨水": "亥",
    "惊蛰": "亥",
    "春分": "戌",
    "清明": "戌",
    "谷雨": "酉",
    "立夏": "酉",
    "小满": "申",
    "芒种": "申",
    "夏至": "未",
    "小暑": "未",
    "大暑": "午",
    "立秋": "午",
    "处暑": "巳",
    "白露": "巳",
    "秋分": "辰",
    "寒露": "辰",
    "霜降": "卯",
    "立冬": "卯",
    "小雪": "寅",
    "大雪": "寅",
    "冬至": "丑",
    "小寒": "丑",
}

# 0..30 deg (春分->谷雨) -> 戌, 30..60 deg -> 酉, ..., 330..360 deg (雨水->春分) -> 亥.
SIGN_TO_MONTH_GENERAL = (
    "戌",
    "酉",
    "申",
    "未",
    "午",
    "巳",
    "辰",
    "卯",
    "寅",
    "丑",
    "子",
    "亥",
)


def month_general_for_term(current_term: str) -> str:
    if current_term not in LIURENG_MONTH_GENERAL_BY_TERM:
        raise ValueError(f"未知节气 {current_term!r}，不能用月建代替月将")
    return LIURENG_MONTH_GENERAL_BY_TERM[current_term]


def solar_longitude_at(instant: datetime) -> float:
    """Compute apparent geocentric solar longitude in [0, 360) via Swiss Ephemeris."""
    utc = utc_calendar(instant)
    y, m, d = utc.date_parts
    hh, mm, ss, us = utc.time_parts
    jd_ut = swe.julday(y, m, d, hh + mm / 60.0 + (ss + us / 1_000_000.0) / 3600.0)
    for flag in (swe.FLG_SWIEPH, swe.FLG_MOSEPH):
        try:
            pos, _ = ephemeris_call("calc_ut", jd_ut, swe.SUN, flag)
            return float(pos[0]) % 360.0
        except Exception:
            continue
    raise EphemerisSourceError("solar_longitude_unavailable")


def compute_month_general(
    seed: MetaphysicsSeed,
    *,
    month_general_mode: MonthGeneralMode = "solar_term",
    month_general_override: str | None = None,
) -> dict[str, Any]:
    """Resolve month general independently without building a full Liuren board."""
    if month_general_mode not in ("solar_term", "true_solar_longitude"):
        raise ValueError("month_general_mode 仅支持 solar_term 或 true_solar_longitude")
    if month_general_override is not None:
        if month_general_override not in YUE_JIANG_NAMES:
            raise ValueError("month_general_override 必须是十二地支之一")
        return {
            "branch": month_general_override,
            "name": YUE_JIANG_NAMES[month_general_override],
            "basis": "explicit_override",
        }
    if month_general_mode == "true_solar_longitude":
        lon = solar_longitude_at(seed.input_datetime)
        branch = SIGN_TO_MONTH_GENERAL[int(lon // 30.0) % 12]
        return {
            "branch": branch,
            "name": YUE_JIANG_NAMES[branch],
            "basis": "太阳过宫真黄经",
            "solar_longitude": round(lon, 6),
        }
    current_term_name = seed.calendar_context["current_solar_term"]["name"]
    branch = month_general_for_term(current_term_name)
    return {
        "branch": branch,
        "name": YUE_JIANG_NAMES[branch],
        "basis": "中气换将",
    }


def resolve_runyear_birth_zone(
    explicit_timezone: str | None,
    birth_place: str | None,
    birth_longitude: float | None = None,
) -> tuple[str, dict[str, Any]]:
    """Resolve a civil zone without requiring or applying a birth solar clock."""
    canonical = None
    advisory = None
    if explicit_timezone is not None:
        zone = explicit_timezone.strip()
        if not zone:
            raise ValueError("行年birth_timezone不能为空；请提供民用时区或省略该字段")
        source = "birth_timezone"
    elif birth_place and birth_place.strip() not in ("", "未提供"):
        place = resolve_birth_place_context(birth_place)
        if place.timezone is None:
            raise ValueError(
                "行年出生地无法唯一解析民用时区；请补全国家、省市或明确birth_timezone"
            )
        zone = place.timezone
        canonical = place.canonical_name
        source = "birth_place"
    elif birth_longitude is not None:
        raise ValueError(
            "行年不能仅凭出生经度确定民用时区；请明确birth_timezone或提供可解析出生地"
        )
    else:
        zone = DEFAULT_BIRTH_TIMEZONE
        source = "default_timezone"
        advisory = "未提供出生民用时区或出生地，沿用Asia/Shanghai软件默认。"
    return zone, {
        "timezone_source": source,
        "timezone_resolved_place": canonical,
        "timezone_assumed": source == "default_timezone",
        "timezone_resolution_advisory": advisory,
    }


def resolve_runyear_birth_clock(
    wall: datetime,
    timezone_name: str,
    explicit_offset: str | None = None,
    *,
    recorded_offset: str | None = None,
) -> tuple[datetime, dict[str, Any]]:
    """Validate the birth civil label independently of the analysis clock."""
    civil = resolve_civil_clock(
        wall,
        timezone_name,
        explicit_offset,
        offset_field="birth_utc_offset",
        timezone_field="birth_timezone",
        recorded_offset=recorded_offset,
    )
    offset = civil.utcoffset()
    assert offset is not None
    return civil, {
        "method": "validated_birth_civil_clock",
        "timezone": timezone_name,
        "input_utc_offset": (
            explicit_offset if explicit_offset is not None else recorded_offset
        ),
        "resolved_utc_offset": format_utc_offset(offset),
        "wall_datetime": civil.replace(tzinfo=None).isoformat(),
        "was_ambiguous": civil.replace(fold=0).utcoffset()
        != civil.replace(fold=1).utcoffset(),
        "fold": civil.fold,
        "instant_utc": utc_calendar(civil).isoformat(),
        "timezone_rules": timezone_rules_metadata(timezone_name),
    }


@lru_cache(maxsize=2048)
def _term_time_scale_cached(
    moment: datetime | UTCCalendar, _profile: str
) -> dict[str, Any]:
    epoch = time_scales.ephemeris_time(moment)
    table = utc_policy.leap_table()
    return {
        "solver_time_scale": "TT",
        "civil_time_method": epoch.method,
        "future_leap_seconds_assumed_unchanged": epoch.future_leap_seconds_assumed_unchanged,
        "leap_table_expires_at": table["expires_at"],
    }


def _term_time_scale(moment: datetime | UTCCalendar) -> dict[str, Any]:
    for _ in range(3):
        profile = loaded_clock_profile_key()
        result = _term_time_scale_cached(moment, profile)
        if loaded_clock_profile_key() == profile:
            return result
        _term_time_scale_cached.cache_clear()
    raise RuntimeError("Civil time profile changed during term receipt calculation")


for _cache_attribute in ("cache_clear", "cache_info", "cache_parameters"):
    setattr(
        _term_time_scale,
        _cache_attribute,
        getattr(_term_time_scale_cached, _cache_attribute),
    )


def require_ren_solar_term(term: SolarTerm) -> None:
    """Validate consumed solar-term boundary consistency without bloat dicts."""
    provider = term.resolution_provider
    if (
        provider
        in {
            "fatebridge_analytic",
            "jpl_de441",
            "jpl_spk",
            "jpl_de440",
            "moshier_aa1996",
            "vsop2013",
        }
        and term.ephemeris_retflags
    ):
        raise RuntimeError("独立太阳模型不能借用原生星历返回标志")
    if not is_calculated_solar_term(term):
        raise EphemerisSourceError("solar_term_source_unverified")
    if provider == "swisseph":
        if term.ephemeris_model not in {"swieph", "moshier", "jpl"}:
            raise RuntimeError("六壬与金口诀交气的实际星历模型未知，不能认证计算来源")
        model_flags = {"jpl": 1, "swieph": 2, "moshier": 4}
        if not term.ephemeris_retflags or any(
            type(flag) is not int or flag not in (1, 2, 4)
            for flag in term.ephemeris_retflags
        ):
            raise RuntimeError(
                "六壬与金口诀交气黄经选项未知，不能认证默认地心视黄经定义"
            )
        if any(
            flag != model_flags[term.ephemeris_model]
            for flag in term.ephemeris_retflags
        ):
            raise RuntimeError("六壬与金口诀交气模型回执与原生返回标志不一致")
    if term.tt_instant is not None:
        if time_scales.utc_calendar_from_tt(term.tt_instant) != term.calendar.utc:
            raise EphemerisSourceError("ren_solar_term_point_inconsistent")


def require_ren_calendar(
    seed: MetaphysicsSeed,
    *,
    month_general_override: str | None = None,
    month_general_mode: MonthGeneralMode = "solar_term",
    analysis_utc_offset: str | None = None,
) -> dict[str, Any]:
    civil = seed.input_datetime
    clock = seed.clock
    current, following = get_adjacent_solar_terms(civil, seed.timezone)
    month, next_month, _, _ = get_bazi_month_boundaries(civil, seed.timezone)
    spring = next(
        t
        for t in get_solar_terms_for_year(civil.year, seed.timezone)
        if t.name == "立春"
    )
    term_dependencies = (
        ("current_term", current),
        ("next_term", following),
        ("month_start", month),
        ("next_month_start", next_month),
        ("year_boundary", spring),
    )
    for _, term in term_dependencies:
        require_ren_solar_term(term)
    dependencies: list[dict[str, Any]] = [
        {
            "role": role,
            "name": term.name,
            **(
                {"civil_moment": term.calendar.isoformat()}
                if term.has_defined_local_clock
                else {
                    "civil_moment": term.calendar.utc.isoformat(),
                    "local_clock_status": "undefined",
                }
            ),
            "provider": term.resolution_provider,
            "ephemeris_model": term.ephemeris_model,
            "published_date_reference": published_date_reference(
                term.name, term.calendar
            ),
        }
        for role, term in term_dependencies
    ]
    result: dict[str, Any] = {
        "mode": "civil_instant_checked",
        "civil_datetime": civil.isoformat(),
        "civil_instant_utc": utc_calendar(civil).isoformat(),
        "day_hour_clock": "apparent_solar" if seed.applied_true_solar else "civil",
        "corrected_clock": seed.clock_isoformat(),
        "day_boundary": "23:00",
        "effective_day_date": NominalClockLabel(
            clock.ordinal + int(clock.time_parts[0] == 23), 0
        ).date_isoformat(),
        "effective_day_ganzhi": "".join(seed.pillars["day"]),
        "year_month_clock": "civil_instant",
        "month_general_clock": (
            "explicit_symbolic_override" if month_general_override else "civil_instant"
        ),
        "month_general_override": month_general_override,
        "month_boundary": "节换月",
        "month_general_boundary": (
            "显式月将覆盖中气规则"
            if month_general_override
            else (
                "太阳过宫真黄经"
                if month_general_mode == "true_solar_longitude"
                else "中气换将"
            )
        ),
        "solar_term_dependencies": dependencies,
        "precision_status": "TT_solver_civil_instant_checked",
    }
    if analysis_utc_offset is not None:
        resolved = resolve_civil_clock(
            civil.replace(tzinfo=None, fold=0), seed.timezone, analysis_utc_offset
        )
        if utc_calendar(resolved) != utc_calendar(civil):
            raise ValueError("明确UTC偏移与起课实际民用瞬间不一致")
        offset = resolved.utcoffset()
        assert offset is not None
        result["civil_clock_resolution"] = {
            "method": "explicit_offset_checked_against_analysis_timezone",
            "timezone": seed.timezone,
            "input_utc_offset": analysis_utc_offset,
            "resolved_utc_offset": format_utc_offset(offset),
            "wall_datetime": civil.replace(tzinfo=None).isoformat(),
            "was_ambiguous": (
                resolved.replace(fold=0).utcoffset()
                != resolved.replace(fold=1).utcoffset()
            ),
            "fold": resolved.fold,
            "instant_utc": utc_calendar(resolved).isoformat(),
        }
    return result


def compact_calendar_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    """Return a non-duplicating header view of an already-present ren_calendar_policy."""
    if not policy:
        return symbolic_calendar_policy()
    keys = (
        "mode",
        "civil_datetime",
        "civil_instant_utc",
        "civil_clock_resolution",
        "day_hour_clock",
        "corrected_clock",
        "day_boundary",
        "effective_day_date",
        "effective_day_ganzhi",
        "month_general_override",
        "month_general_boundary",
        "precision_status",
    )
    return {k: policy[k] for k in keys if k in policy}


def symbolic_calendar_policy() -> dict[str, Any]:
    return {
        "mode": "symbolic_or_unverified_civil_input",
        "precision_status": "not_a_civil_calendar_validation",
    }


def ruleset_metadata(
    technique: str, *, guiren_profile: str = "liuren_common_v1"
) -> dict[str, Any]:
    del guiren_profile
    jinkou = technique == "jinkou"
    if jinkou:
        return {
            "id": "jinkou_jingben_v2",
            "version": "2.0.0",
            "source_title": "校正京本六壬神课金口诀（四位/五动三动/六十四课钤/四绝四败/神煞/行年）",
            "classical_conformance": "implemented",
            "classical_acceptance_passed": True,
        }
    return {
        "id": "liuren_jiuzong_v2",
        "version": "2.0.0",
        "source_title": (
            "大六壬720课 / 大六壬探原 / 六壬大全（九宗门/六十四课/德禄马/类神）"
        ),
        "classical_conformance": "implemented",
        "classical_acceptance_passed": True,
    }


def xun_dun_stems(day_ganzhi: str) -> dict[str, str]:
    """The ten actual xun stems; the two empty branches have no stem."""
    head = SEXAGENARY_INDEX[day_ganzhi] // 10 * 10
    return {pair[1]: pair[0] for pair in SEXAGENARY_CYCLE[head : head + 10]}


def liuren_annotation_note(day_ganzhi: str, gan_upper: str) -> dict[str, Any] | None:
    """Critical apparatus notes for attested table-vs-prose variants."""
    notes = {
        ("丁卯", "申"): (
            "涉害",
            48,
            "broader_tabular_annotation",
            "总说细分为察微；表注涉害。",
        ),
        ("戊辰", "未"): (
            "重审",
            49,
            "broader_or_variant_tabular_annotation",
            "总说明细分为始入；表注重审。",
        ),
        ("戊申", "卯"): (
            "元首",
            59,
            "definition_annotation_disagreement",
            "本课有下贼上，总说贼先于克；表注元首。",
        ),
    }
    record = notes.get((day_ganzhi, gan_upper))
    if record is None:
        return None
    annotation, page, kind, explanation = record
    return {
        "annotation": annotation,
        "original_pdf_page": page,
        "kind": kind,
        "explanation": explanation,
    }


def _year_ganzhi_for_nominal_year(year: int) -> tuple[str, str]:
    ganzhi = SEXAGENARY_CYCLE[(year - 1984) % 60]
    return ganzhi, ganzhi[1]


def derive_birth_year_fate_from_date(
    birth_date: str,
    analysis_date: date,
    *,
    boundary: Literal["lunar_new_year", "lichun"] = "lunar_new_year",
    timezone_name: str = DEFAULT_BIRTH_TIMEZONE,
) -> dict[str, Any]:
    """Derive birth year ganzhi, natal branch, and nominal age with CNY-vs-Lichun check."""
    try:
        birth_d = date.fromisoformat(birth_date)
    except ValueError as exc:
        raise ParameterError(
            f"无效的 birth_date: {birth_date}",
            [{"path": "birth_date", "code": "invalid_birth_date"}],
        ) from exc
    if birth_d > analysis_date:
        raise ParameterError(
            "birth_date 不能晚于起课日期",
            [{"path": "birth_date", "code": "birth_after_analysis"}],
        )

    birth_noon = datetime(birth_d.year, birth_d.month, birth_d.day, 12, 0, 0)
    analysis_noon = datetime(
        analysis_date.year, analysis_date.month, analysis_date.day, 12, 0, 0
    )

    birth_lunar = get_lunar_context(birth_noon, timezone_name=timezone_name)
    analysis_lunar = get_lunar_context(analysis_noon, timezone_name=timezone_name)
    raw_birth_lunar_year = (
        birth_lunar.get("year") if isinstance(birth_lunar, dict) else None
    )
    if not isinstance(raw_birth_lunar_year, int):
        raise ParameterError(
            "birth_date 超出农历支持区间（1900-01-01 至 2100-12-31）",
            [{"path": "birth_date", "code": "unsupported_calendar_date"}],
        )
    raw_analysis_lunar_year = (
        analysis_lunar.get("year") if isinstance(analysis_lunar, dict) else None
    )
    if not isinstance(raw_analysis_lunar_year, int):
        raise ParameterError(
            "起课日期超出农历支持区间（1900-01-01 至 2100-12-31）",
            [{"path": "analysis_year", "code": "unsupported_calendar_date"}],
        )

    lny_birth_year = raw_birth_lunar_year
    lny_analysis_year = raw_analysis_lunar_year
    lny_ganzhi, lny_branch = _year_ganzhi_for_nominal_year(lny_birth_year)
    lny_age = lny_analysis_year - lny_birth_year + 1

    lc_birth_year = get_bazi_year(birth_noon, timezone_name)
    lc_analysis_year = get_bazi_year(analysis_noon, timezone_name)
    lc_ganzhi, lc_branch = _year_ganzhi_for_nominal_year(lc_birth_year)
    lc_age = lc_analysis_year - lc_birth_year + 1

    lny_record = {
        "boundary": "lunar_new_year",
        "birth_year": lny_birth_year,
        "birth_year_ganzhi": lny_ganzhi,
        "natal_branch": lny_branch,
        "year_fate_age": lny_age,
    }
    lc_record = {
        "boundary": "lichun",
        "birth_year": lc_birth_year,
        "birth_year_ganzhi": lc_ganzhi,
        "natal_branch": lc_branch,
        "year_fate_age": lc_age,
    }
    primary = lny_record if boundary == "lunar_new_year" else lc_record
    alternate = lc_record if boundary == "lunar_new_year" else lny_record
    disagreement = lny_ganzhi != lc_ganzhi or lny_age != lc_age
    payload: dict[str, Any] = {
        "birth_date": birth_d.isoformat(),
        "boundary": boundary,
        "birth_year_ganzhi": primary["birth_year_ganzhi"],
        "natal_branch": primary["natal_branch"],
        "year_fate_age": primary["year_fate_age"],
        "boundary_disagreement": disagreement,
    }
    if disagreement:
        payload["alternate_boundary"] = alternate
    return payload
