"""Seven Jingben calendar targets; inherent branch matches are structural facts."""

from __future__ import annotations

from typing import Any

from .common import SEXAGENARY_INDEX
from .jinkou_sources import SCAN_SHA256, SCAN_URL

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
MONTHS = "寅卯辰巳午未申酉戌亥子丑"
POSITIONS = ("贵神", "将神", "地分")
MONTH_TARGETS = {
    "tianxi": "戌亥子丑寅卯辰巳午未申酉",
    "tianma": "午申戌子寅辰午申戌子寅辰",
    "yima": "申巳寅亥申巳寅亥申巳寅亥",
    "sangche": "酉酉酉子子子卯卯卯午午午",
}
TIANSHE_TARGETS = ("戊寅", "甲午", "戊申", "甲子")
SCOPE = (
    "仅所选七项历法目标及三位本支匹配；月序采用节换月月建寅至丑的当前输入约定，"
    "不认证原书月序必为节月或农历月。此处春夏秋冬各含三个月序，与辰未戌丑整月土旺的五态分组各自独立。"
    "京本驿马条明载申子辰月在寅，本层按月支，不借大六壬日支驿马或月将支。"
    "匹配贵神固有支、将神本支及地分本支，不以贵神落地盘位置替换其固有支。"
    "天赦仅核对占日完整干支；其余仅列本支相同事实，不裁综合用神、吉凶效力、期限或现实结果。"
    "天德、月德、月合等混合干支目标的取位与本章其余条目仍须继续核对，未称完整神煞体系。"
)


def calendar_targets(
    *, year_branch: str | None = None, month_branch: str | None = None
) -> dict[str, str]:
    """Return only targets whose calendar anchor was actually supplied."""
    result = {}
    if month_branch is not None:
        if month_branch not in MONTHS or len(month_branch) != 1:
            raise ValueError("京本神煞月建支无效")
        index = MONTHS.index(month_branch)
        result.update({k: values[index] for k, values in MONTH_TARGETS.items()})
        result["tianshe"] = TIANSHE_TARGETS[index // 3]
    if year_branch is not None:
        if year_branch not in BRANCHES or len(year_branch) != 1:
            raise ValueError("京本神煞年支无效")
        index = BRANCHES.index(year_branch)
        result["sangmen"] = BRANCHES[(index + 2) % 12]
        result["diaoke"] = BRANCHES[(index - 2) % 12]
    return result


def branch_stars(
    *,
    year_branch: str,
    month_branch: str,
    day_ganzhi: str,
    input_branches: dict[str, str],
) -> dict[str, Any]:
    if (
        not isinstance(year_branch, str)
        or not isinstance(month_branch, str)
        or not isinstance(day_ganzhi, str)
        or not isinstance(input_branches, dict)
        or year_branch not in BRANCHES
        or len(year_branch) != 1
        or month_branch not in MONTHS
        or len(month_branch) != 1
        or day_ganzhi not in SEXAGENARY_INDEX
        or set(input_branches) != set(POSITIONS)
        or any(
            not isinstance(b, str) or len(b) != 1 or b not in BRANCHES
            for b in input_branches.values()
        )
    ):
        raise ValueError("京本神煞需要明确年支、月建、日干支及三位本支")
    month_index = MONTHS.index(month_branch)
    season = "春夏秋冬"[month_index // 3]
    targets = calendar_targets(year_branch=year_branch, month_branch=month_branch)
    checks = []
    definitions = [
        ("tianxi", "天喜", "month_building", targets["tianxi"], 118),
        ("tianma", "天马", "month_building", targets["tianma"], 119),
        ("yima", "驿马", "month_building", targets["yima"], 119),
        (
            "sangche",
            "丧车",
            "month_building",
            targets["sangche"],
            120,
        ),
        ("sangmen", "丧门", "year_branch", targets["sangmen"], 120),
        ("diaoke", "吊客", "year_branch", targets["diaoke"], 120),
        (
            "tianshe",
            "天赦",
            "season_and_day",
            targets["tianshe"],
            118,
        ),
    ]
    for star_id, name, category, target, page in definitions:
        day_target = star_id == "tianshe"
        checks.append(
            dict(
                id=star_id,
                name=name,
                category=category,
                target_kind="day_ganzhi" if day_target else "branch",
                target=target,
                matched_positions=(
                    []
                    if day_target
                    else [p for p in POSITIONS if input_branches[p] == target]
                ),
                matched_day=day_ganzhi == target if day_target else None,
                original_pdf_page=page,
            )
        )
    return dict(
        ruleset_id="jinkou_jingben_branch_stars_v1",
        source_url=SCAN_URL,
        source_sha256=SCAN_SHA256,
        original_pdf_pages=[118, 119, 120],
        year_branch=year_branch,
        month_building_branch=month_branch,
        nominal_month=month_index + 1,
        season_partition=season,
        month_profile="declared_term_month_ordinal_v1",
        day_ganzhi=day_ganzhi,
        input_branches=dict(input_branches),
        checks=checks,
        yima_anchor="month_building_branch",
        comprehensive_effect=None,
        complete_classical_conformance=False,
        scope=SCOPE,
    )


def branch_stars_trace(value: dict[str, Any]) -> dict[str, Any]:
    return dict(
        rule_id="jinkou.jingben_branch_stars",
        source_url=SCAN_URL,
        source_section="京本卷上·合用神煞·天赦、天喜、天马、驿马、丧门、吊客、丧车",
        result=value,
    )
