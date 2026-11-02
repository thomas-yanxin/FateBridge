"""京本六甲旬起行年 and a separate course on its branch.

The caller supplies the birth-year ganzhi and one-based ordinal. No birth
date, age boundary or favourable outcome is inferred from the analysis time.
"""

from __future__ import annotations

from typing import Any

from ...utils.birth_input import normalize_gender
from .common import MetaphysicsSeed

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
SOURCE_URL = "https://upload.wikimedia.org/wikipedia/commons/e/e1/CNTS-00047981961_1_六壬神課金口訣.pdf"
SOURCE_SHA256 = "dfa4b039f30100eb75a8fe21904256bc4e47c04538c8602d08aec9e7f7646364"


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
        source_url=SOURCE_URL,
        source_sha256=SOURCE_SHA256,
        source_section="推行年法 / 論人行年吉凶",
        original_pdf_pages=[170, 171, 172, 173],
        relation_adjudication="unresolved_course_stem_reference",
        relation_note="通常五子元法在行年支起课，人元与行年干同阴阳，不能五合；原页己亥行年见甲人元的课干所指仍未裁定，不据此判喜用。",
        scope="按明确出生年干支所属旬及指定一岁起算岁序计算行年；另课采用行年支作地分的所选释读，不是已观测来人方位。未核验指定岁序是否为占时实际年龄，不推断生日、岁首、综合喜用或现实结果。",
    )


def build_jinkou_year_fate(
    seed: MetaphysicsSeed,
    liureng_board: dict[str, Any],
    *,
    birth_year_ganzhi: str | None,
    age: int | None,
    gender: str | None,
    natal_branch: str | None,
    is_diurnal: bool | None,
) -> dict[str, Any]:
    from .jinkou import build_jinkou_board

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
            liureng_board,
            gender=result["gender"],
            di_fen=result["branch"],
            natal_branch=natal,
            natal_branch_source=(
                result["natal_branch_source"] if natal is not None else None
            ),
            is_diurnal_override=is_diurnal,
        )
        result["course"]["engine"] = "fatebridge-offline"
        result["course"]["overview"]["di_fen_source"] = "annual_branch_derived_course"
    return result
