"""Jin Kou natal branch course and six-Jia xun ordinal year fate."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.jinkou.board import build_jinkou_board
from fatebridge.core.metaphysics.ren_calendar import MonthGeneralMode
from fatebridge.core.metaphysics.ren_diurnal import DiurnalMode
from fatebridge.utils.birth_input import normalize_gender

CYCLE = tuple(
    "甲乙丙丁戊己庚辛壬癸"[i % 10] + "子丑寅卯辰巳午未申酉戌亥"[i % 12]
    for i in range(60)
)
STARTS = {
    "甲子": ("丙寅", "壬申"),
    "甲戌": ("丙子", "壬午"),
    "甲申": ("丙戌", "壬辰"),
    "甲午": ("丙申", "壬寅"),
    "甲辰": ("丙午", "壬子"),
    "甲寅": ("丙辰", "壬戌"),
}


def confirmed_natal_branch(
    birth_year_ganzhi: str | None, natal_branch: str | None, age: int | None
) -> str | None:
    if birth_year_ganzhi is not None and birth_year_ganzhi not in CYCLE:
        raise ValueError("birth_year_ganzhi 必须是六十甲子中的完整出生年干支")
    if age is not None and (type(age) is not int or not 1 <= age <= 150):
        raise ValueError("year_fate_age 必须是明确提供的1至150的一岁起算岁序整数")
    if birth_year_ganzhi is not None:
        branch = birth_year_ganzhi[1]
        if natal_branch is not None and natal_branch != branch:
            raise ValueError("natal_branch 与明确出生年干支的年支冲突")
        return branch
    return natal_branch


def ordinal_year_fate(
    *, birth_year_ganzhi: str | None, age: int | None, gender: str | None
) -> dict[str, Any]:
    confirmed_natal_branch(birth_year_ganzhi, None, age)
    sex = normalize_gender(gender)
    missing = [
        name
        for name, absent in (
            ("birth_year_ganzhi", birth_year_ganzhi is None),
            ("year_fate_age", age is None),
            ("gender", sex not in ("男", "女")),
        )
        if absent
    ]
    xun = (
        CYCLE[CYCLE.index(birth_year_ganzhi) // 10 * 10]
        if birth_year_ganzhi is not None
        else None
    )
    start = (
        STARTS[xun][0 if sex == "男" else 1]
        if xun is not None and sex in ("男", "女")
        else None
    )
    direction = "顺" if sex == "男" else "逆" if sex == "女" else None
    result = (
        CYCLE[(CYCLE.index(start) + (age - 1) * (1 if sex == "男" else -1)) % 60]
        if not missing and start is not None and age is not None
        else None
    )
    return dict(
        method_id="jingben_birth_xun_year_fate_v1",
        status="missing_inputs" if missing else "calculated",
        birth_year_ganzhi=birth_year_ganzhi,
        birth_xun=xun,
        gender=sex,
        age_ordinal=age,
        age_basis="explicit_one_based_ordinal",
        course_basis="annual_branch_as_ground_reading",
        course_ground_is_observed=False,
        start_ganzhi=start,
        direction=direction,
        ganzhi=result,
        branch=result[1] if result else None,
        missing_inputs=missing,
        age_boundary_classically_verified=False,
        birth_year_calendar_boundary_verified=False,
        comprehensive_year_fate_adjudicated=False,
        source_section="推行年法 / 論人行年吉凶",
        relation_adjudication="unresolved_course_stem_reference",
    )


def natal_course_metadata(
    birth_year_ganzhi: str | None, natal_branch: str | None
) -> dict[str, Any]:
    if natal_branch is not None and (
        not isinstance(natal_branch, str)
        or len(natal_branch) != 1
        or natal_branch not in "子丑寅卯辰巳午未申酉戌亥"
    ):
        raise ValueError("本命另课需要明确且合法的本命支")
    natal = confirmed_natal_branch(birth_year_ganzhi, natal_branch, None)
    return dict(
        method_id="jingben_natal_branch_course_v1",
        status="calculated" if natal is not None else "missing_inputs",
        birth_year_ganzhi=birth_year_ganzhi,
        natal_branch=natal,
        natal_branch_source=(
            "explicit_natal_branch"
            if natal_branch is not None
            else (
                "explicit_birth_year_ganzhi"
                if birth_year_ganzhi is not None
                else "missing"
            )
        ),
        missing_inputs=(
            [] if natal is not None else ["natal_branch_or_birth_year_ganzhi"]
        ),
        course_basis="natal_branch_as_ground_reading",
        course_ground_is_observed=False,
        birth_year_calendar_boundary_verified=False,
        comprehensive_judgement=None,
        source_section="卷上·次客法",
    )


def build_natal_course(
    seed: MetaphysicsSeed,
    liureng_or_month_general: dict[str, Any] | str | None = None,
    *,
    birth_year_ganzhi: str | None,
    natal_branch: str | None,
    gender: str,
    is_diurnal: bool | None,
    diurnal_mode: DiurnalMode = "clock",
    month_general_mode: MonthGeneralMode = "solar_term",
    month_general_override: str | None = None,
    latitude: float | None = None,
) -> dict[str, Any]:
    result = natal_course_metadata(birth_year_ganzhi, natal_branch)
    result["course"] = None
    if result["natal_branch"] is not None:
        child = build_jinkou_board(
            seed,
            liureng_or_month_general,
            gender=gender,
            di_fen=result["natal_branch"],
            natal_branch=result["natal_branch"],
            natal_branch_source=result["natal_branch_source"],
            is_diurnal_override=is_diurnal,
            diurnal_mode=diurnal_mode,
            month_general_mode=month_general_mode,
            month_general_override=month_general_override,
            latitude=latitude,
            _is_child_course=True,
        )
        child["engine"] = "fatebridge-offline"
        child["overview"]["di_fen_source"] = "natal_branch_derived_course"
        result["course"] = child
    return result


def build_jinkou_year_fate(
    seed: MetaphysicsSeed,
    liureng_or_month_general: dict[str, Any] | str | None = None,
    *,
    birth_year_ganzhi: str | None,
    age: int | None,
    gender: str | None,
    natal_branch: str | None,
    is_diurnal: bool | None,
    diurnal_mode: DiurnalMode = "clock",
    month_general_mode: MonthGeneralMode = "solar_term",
    month_general_override: str | None = None,
    latitude: float | None = None,
) -> dict[str, Any]:
    natal = confirmed_natal_branch(birth_year_ganzhi, natal_branch, age)
    result = ordinal_year_fate(
        birth_year_ganzhi=birth_year_ganzhi, age=age, gender=gender
    )
    result["natal_branch"] = natal
    result["natal_branch_source"] = (
        "explicit_natal_branch"
        if natal_branch is not None
        else (
            "explicit_birth_year_ganzhi" if birth_year_ganzhi is not None else "missing"
        )
    )
    result["course"] = None
    if result["status"] == "calculated":
        result["course"] = build_jinkou_board(
            seed,
            liureng_or_month_general,
            gender=result["gender"],
            di_fen=result["branch"],
            natal_branch=natal,
            natal_branch_source=(
                result["natal_branch_source"] if natal is not None else None
            ),
            is_diurnal_override=is_diurnal,
            diurnal_mode=diurnal_mode,
            month_general_mode=month_general_mode,
            month_general_override=month_general_override,
            latitude=latitude,
            _is_child_course=True,
        )
        result["course"]["engine"] = "fatebridge-offline"
        result["course"]["overview"]["di_fen_source"] = "annual_branch_derived_course"
    return result


def natal_course_trace(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": "jinkou.natal_branch_course",
        "source_section": "卷上·次客法·本命另课",
        "result": {k: v for k, v in value.items() if k != "course"},
    }
