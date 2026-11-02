"""京本次客法's named reading: a separate course on confirmed 本命支."""

from __future__ import annotations

from typing import Any

from .common import MetaphysicsSeed
from .jinkou_year_fate import SOURCE_SHA256, SOURCE_URL, confirmed_natal_branch


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
        source_url=SOURCE_URL,
        source_sha256=SOURCE_SHA256,
        source_section="卷上·次客法",
        original_pdf_pages=[168, 169],
        basis="京本次客法提出以来人本命或行年上作课；本层采用已确认本命支作另课地分，复用本次占日、占时、月将及昼夜选择。",
        scope="本命另课与原地分主课、行年另课分别计算；本命支来自显式输入或明确出生年干支，不借占年、占日、时支、行年支补造。不改实际历法或自动换将换日；不把派生地分称为观测方位，不认证本命标签换岁边界、全书综合断法、年内应验或现实预测。",
    )


def build_natal_course(
    seed: MetaphysicsSeed,
    liureng_board: dict[str, Any],
    *,
    birth_year_ganzhi: str | None,
    natal_branch: str | None,
    gender: str,
    is_diurnal: bool | None,
) -> dict[str, Any]:
    from .jinkou import build_jinkou_board

    result = natal_course_metadata(birth_year_ganzhi, natal_branch)
    result["course"] = None
    if result["natal_branch"] is not None:
        child = build_jinkou_board(
            seed,
            liureng_board,
            gender=gender,
            di_fen=result["natal_branch"],
            natal_branch=result["natal_branch"],
            natal_branch_source=result["natal_branch_source"],
            is_diurnal_override=is_diurnal,
        )
        child["engine"] = "fatebridge-offline"
        child["overview"]["di_fen_source"] = "natal_branch_derived_course"
        result["course"] = child
    return result


def natal_course_trace(value: dict[str, Any]) -> dict[str, Any]:
    return dict(
        rule_id="jinkou.natal_branch_course",
        source_url=SOURCE_URL,
        source_section="卷上·次客法·本命另课",
        result={k: v for k, v in value.items() if k != "course"},
    )
