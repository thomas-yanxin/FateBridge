"""Liuren annual runyear (行年) and natal/annual placement."""

from __future__ import annotations

from typing import Any

from fatebridge.core.almanac import get_lunar_context, localize_datetime
from fatebridge.core.metaphysics.common import (
    EARTHLY_BRANCHES,
    SEXAGENARY_INDEX,
    MetaphysicsSeed,
    branch_element_text,
    liuqin_against_day,
    sexagenary_index_for,
    sexagenary_text,
    stem_element_text,
)
from fatebridge.core.metaphysics.ren_calendar import xun_dun_stems
from fatebridge.utils.birth_input import normalize_gender


def natal_year_ganzhi(birth_lunar_year: int) -> str:
    if type(birth_lunar_year) is not int:
        raise ValueError("本命需要有效的出生农历年")
    return sexagenary_text(birth_lunar_year - 4)


def build_year_fate(
    board: dict[str, Any],
    *,
    day_ganzhi: str,
    birth_lunar_year: int,
    runyear_ganzhi: str | None,
    runyear_reason: str | None = None,
) -> dict[str, Any]:
    if day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("年命上神需要有效的占日干支")
    rows = board["twelve_board"]
    if (
        len(rows) != 12
        or {row["earth_branch"] for row in rows} != set(EARTHLY_BRANCHES)
        or {row["sky_branch"] for row in rows} != set(EARTHLY_BRANCHES)
    ):
        raise ValueError("年命上神需要完整且不重复的天地盘")
    by_earth = {row["earth_branch"]: row for row in rows}
    dun = xun_dun_stems(day_ganzhi)
    day_element = stem_element_text(day_ganzhi[0])

    def placement(subject: str | None) -> dict[str, Any]:
        if subject is None:
            return {
                "status": "not_calculated",
                "subject_ganzhi": None,
                "earth_branch": None,
                "sky_branch": None,
                "god": None,
                "upper_dun_stem": None,
                "upper_ganzhi": None,
                "upper_relation": None,
                "upper_xun_kong": None,
                "earth_xun_kong": None,
                "reason": runyear_reason or "行年未计算",
            }
        if subject not in SEXAGENARY_INDEX:
            raise ValueError("年命落盘需要有效干支")
        earth = subject[1]
        row = by_earth[earth]
        sky = row["sky_branch"]
        stem = dun.get(sky)
        return {
            "status": "calculated",
            "subject_ganzhi": subject,
            "earth_branch": earth,
            "sky_branch": sky,
            "god": row["god"],
            "upper_dun_stem": stem,
            "upper_ganzhi": f"{stem}{sky}" if stem else None,
            "upper_relation": liuqin_against_day(day_element, branch_element_text(sky)),
            "upper_xun_kong": sky not in dun,
            "earth_xun_kong": earth not in dun,
            "reason": None,
        }

    return {
        "ruleset_id": "tanyuan_year_fate_v1",
        "source_title": "袁树珊大六壬探原·年命",
        "day_ganzhi": day_ganzhi,
        "guiren_profile": board["meta"]["guiren_profile"],
        "natal": placement(natal_year_ganzhi(birth_lunar_year)),
        "annual": placement(runyear_ganzhi),
    }


def build_liureng_runyear(
    seed: MetaphysicsSeed,
    gender: str,
    birth_year: int,
    *,
    birth_lunar_year: int,
    age_reference_timezone: str | None = None,
) -> dict[str, Any]:
    age_zone = age_reference_timezone or seed.timezone
    analysis_civil = localize_datetime(seed.input_datetime, seed.timezone)
    target_civil = localize_datetime(analysis_civil, age_zone)
    target_lunar = get_lunar_context(target_civil, timezone_name=age_zone)
    if target_lunar is None:
        raise ValueError("行年需要分析日期的农历年")
    target_lunar_year = target_lunar["year"]
    if not isinstance(target_lunar_year, int):
        raise ValueError("行年需要有效的农历年")
    age = target_lunar_year - birth_lunar_year + 1
    if birth_lunar_year not in (birth_year - 1, birth_year) or age < 1:
        raise ValueError("行年分析日期不能早于出生年")
    normalized_gender = normalize_gender(gender)
    basis = {
        "age": age,
        "gender": gender,
        "age_basis": "农历年差加一；正月初一换岁",
        "rule_id": "liuren.runyear_bingyin_renshen",
        "source_section": "大六壬探原·年命",
        "birth_lunar_year": birth_lunar_year,
        "age_calendar": {
            "policy": "one_timezone_lunar_year_age_v1",
            "timezone": age_zone,
            "analysis_civil_datetime": target_civil.isoformat(),
            "birth_lunar_year": birth_lunar_year,
            "analysis_lunar_year": target_lunar_year,
            "year_boundary": "正月初一00:00",
        },
    }
    if normalized_gender == "未知":
        return {
            **basis,
            "ganzhi": None,
            "status": "not_calculated",
            "reason": "未提供男女行年分支，不默认套用男式",
        }
    if normalized_gender == "女":
        start_index = sexagenary_index_for("壬申")
        direction = -1
    else:
        start_index = sexagenary_index_for("丙寅")
        direction = 1
    runyear_ganzhi = sexagenary_text(start_index + direction * (age - 1))
    return {**basis, "ganzhi": runyear_ganzhi, "status": "calculated"}
