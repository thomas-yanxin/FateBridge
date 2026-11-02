"""探原's 类神之阴: compose the sky lookup, except for the noble pair."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from ...utils.data import EARTHLY_BRANCHES
from .common import (
    GUI_REN_SEQUENCE,
    SEXAGENARY_INDEX,
    branch_element_text,
    kongwang_for_ganzhi,
)
from .liureng_seasonal import MONTH_PARTITION, POWERS
from .ren_gods import GuirenProfile, noble_start

RULE_ID = "liuren.tanyuan_god_yin"


def role_presence(
    in_lesson: bool,
    in_transmission: bool,
    in_natal: bool | None,
    in_annual: bool | None,
) -> bool | None:
    facts = [in_lesson, in_transmission, in_natal, in_annual]
    if any(v is True for v in facts):
        return True
    return None if any(v is None for v in facts) else False


def god_yin_spirits(
    *,
    day_ganzhi: str,
    month_branch: str,
    is_diurnal: bool,
    guiren_profile: GuirenProfile,
    sky_by_earth: dict[str, str],
    god_by_sky: dict[str, str],
    lesson_uppers: list[str],
    transmission_branches: list[str],
    year_fate_uppers: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    branches = set(EARTHLY_BRANCHES)
    if day_ganzhi not in SEXAGENARY_INDEX or month_branch not in branches:
        raise ValueError("类神阴神需要有效占日与月建")
    if type(is_diurnal) is not bool:
        raise ValueError("类神阴神需要已声明的昼夜策略")
    if set(sky_by_earth) != branches or set(sky_by_earth.values()) != branches:
        raise ValueError("类神阴神需要完整的一一对应天地盘")
    if set(god_by_sky) != branches or set(god_by_sky.values()) != set(GUI_REN_SEQUENCE):
        raise ValueError("类神阴神需要完整且不重复的十二天将")
    if (
        len(lesson_uppers) != 4
        or len(transmission_branches) != 3
        or any(v not in branches for v in lesson_uppers + transmission_branches)
    ):
        raise ValueError("类神阴神需要同课四课与三传")
    upper_roles = year_fate_uppers or {"natal": None, "annual": None}
    if set(upper_roles) != {"natal", "annual"} or any(
        v is not None and v not in branches for v in upper_roles.values()
    ):
        raise ValueError("年命上神须明确提供，缺项保留未知")
    noble = noble_start(day_ganzhi[0], is_diurnal, guiren_profile)
    other_noble = noble_start(day_ganzhi[0], not is_diurnal, guiren_profile)
    if god_by_sky[noble] != "贵人":
        raise ValueError("阴神所用贵人表与本课实际天将盘不一致")
    by_god = {god: sky for sky, god in god_by_sky.items()}
    earth_by_sky = {sky: earth for earth, sky in sky_by_earth.items()}
    empty = kongwang_for_ganzhi(day_ganzhi)[:2]
    powers = POWERS[MONTH_PARTITION[month_branch]]
    positions = ("initial", "middle", "final")
    rows = []
    for god in GUI_REN_SEQUENCE:
        riding = by_god[god]
        # 天乙 is the explicit exception. Do not compose its current riding
        # branch or apply the ordinary rule to an intrinsic god-house branch.
        yin = other_noble if god == "贵人" else sky_by_earth[riding]
        lesson_indices = [i for i, upper in enumerate(lesson_uppers, 1) if upper == yin]
        trans_positions = [
            p for p, upper in zip(positions, transmission_branches) if upper == yin
        ]
        natal = None if upper_roles["natal"] is None else yin == upper_roles["natal"]
        annual = None if upper_roles["annual"] is None else yin == upper_roles["annual"]
        power = powers[branch_element_text(yin)]
        rows.append(
            dict(
                god=god,
                riding_branch=riding,
                riding_earth_branch=earth_by_sky[riding],
                yin_branch=yin,
                yin_earth_branch=earth_by_sky[yin],
                derivation=(
                    "opposite_noble_start"
                    if god == "贵人"
                    else "upper_of_riding_branch"
                ),
                lesson_indices=lesson_indices,
                transmission_positions=trans_positions,
                in_natal_upper=natal,
                in_annual_upper=annual,
                appears_in_roles=role_presence(
                    bool(lesson_indices), bool(trans_positions), natal, annual
                ),
                yin_branch_xun_kong=yin in empty,
                nominal_seasonal_power=power,
                nominal_wang_xiang=power in ("旺", "相"),
                effective_emptiness=None,
                ri_chen_de_he_sheng_adjudicated=None,
                comprehensive_eligibility=None,
            )
        )
    return dict(
        ruleset_id="tanyuan_category_spirit_yin_v1",
        source_title="大六壬探原·论阴神〔类神之阴〕",
        source_url=TANYUAN_SOURCE,
        source_sha256=TANYUAN_SCAN_SHA256,
        original_pdf_pages=[87, 88],
        day_ganzhi=day_ganzhi,
        month_branch=month_branch,
        is_diurnal=is_diurnal,
        guiren_profile=guiren_profile,
        sky_by_earth=dict(sky_by_earth),
        god_by_sky=dict(god_by_sky),
        lesson_uppers=list(lesson_uppers),
        transmission_branches=list(transmission_branches),
        year_fate_uppers=dict(upper_roles),
        seasonal_profile="declared_seasonal_month_branches_v1",
        rows=rows,
        complete_classical_conformance=False,
        scope="按探原类神之阴查法：十一天将取实际所乘支之上神，天乙贵人取所选表的异时贵人支。探原甲日未、甲夜丑的原例适用于探原贵人配置；通行表仍按已声明表互取，不偷换整书配置。四课三传及已知年命上神的出现位置分别列明，缺年命保留未知；本支旬空与当前季月整月五态只列条件。日辰德合相生、角色例外后的有效空亡与类神综合可用性未裁，不据阴神位置给出现实吉凶或应期。",
    )


def god_yin_trace(value: dict[str, Any]) -> dict[str, Any]:
    return dict(
        rule_id=RULE_ID,
        source_url=value["source_url"],
        source_section=value["source_title"],
        result=value,
    )


def add_year_fate_membership(board: dict[str, Any], year_fate: dict[str, Any]) -> None:
    previous = board["god_yin"]
    inputs = {
        key: previous[key]
        for key in (
            "day_ganzhi",
            "month_branch",
            "is_diurnal",
            "guiren_profile",
            "sky_by_earth",
            "god_by_sky",
            "lesson_uppers",
            "transmission_branches",
        )
    }
    inputs["year_fate_uppers"] = {
        role: year_fate[role]["sky_branch"] for role in ("natal", "annual")
    }
    value = god_yin_spirits(**inputs)
    board["god_yin"] = value
    board["rule_trace"] = [
        god_yin_trace(value) if row["rule_id"] == RULE_ID else row
        for row in board["rule_trace"]
    ]
