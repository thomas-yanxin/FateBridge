"""探原五季五态；支神、天将和地盘各按自身五行定位。"""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.liureng_relation_tables import GOD_ELEMENTS
from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from .common import (
    SEXAGENARY_INDEX,
    branch_element_text,
    kongwang_for_ganzhi,
    stem_element_text,
)

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
MONTH_PARTITION = {
    "寅": "春",
    "卯": "春",
    "辰": "季月",
    "巳": "夏",
    "午": "夏",
    "未": "季月",
    "申": "秋",
    "酉": "秋",
    "戌": "季月",
    "亥": "冬",
    "子": "冬",
    "丑": "季月",
}
POWERS = {
    "春": {"木": "旺", "火": "相", "土": "死", "金": "囚", "水": "休"},
    "夏": {"木": "休", "火": "旺", "土": "相", "金": "死", "水": "囚"},
    "秋": {"木": "死", "火": "囚", "土": "休", "金": "旺", "水": "相"},
    "冬": {"木": "相", "火": "死", "土": "囚", "金": "休", "水": "旺"},
    "季月": {"木": "囚", "火": "休", "土": "旺", "金": "相", "水": "死"},
}
SCOPE = (
    "采用探原五季25项五态表，月建支按当前季月整月配置分组，季末十八日异法未裁。"
    "天盘支神、所乘天将固有五行与地盘分别定位，日干五态只作日干事实，不替代其他对象。"
    "仅在支神本空并按该五行季节状态适用的假设下列真空、半空条件；天空天将、坐空及日干寄宫例外不替换支神本空。"
    "原文壬申例未载月令，不据其真空字样认证季节真半分类。"
    "扶助、冲剋、太岁月建月将及年命等角色须合看，调整后的真半及综合有效空亡未裁，不将原文效力折扣转为成功率或现实结果。"
)


def seasonal_metadata() -> dict[str, Any]:
    """Fixed source and scope anchors, also valid in sparse evidence views."""
    return dict(
        ruleset_id="tanyuan_seasonal_month_conditions_v1",
        source_title="袁树珊《大六壬探原》论空亡、论十二天将、论旺相死囚休",
        source_url=TANYUAN_SOURCE,
        source_sha256=TANYUAN_SCAN_SHA256,
        original_pdf_pages=[84, 86, 89, 90],
        month_partition_profile="declared_seasonal_month_branches_v1",
        month_partition_basis="月建寅卯取春、巳午取夏、申酉取秋、亥子取冬，辰未戌丑整月取季月；这是当前配置，不认证季末十八日异法",
        effective_empty_classification=None,
        effective_true_half_adjudicated=False,
        complete_classical_conformance=False,
        scope=SCOPE,
    )


def empty_condition(power: str, xun_kong: bool) -> str | None:
    if power not in ("旺", "相", "休", "囚", "死") or type(xun_kong) is not bool:
        raise ValueError("本空季节条件需要有效五态与布尔本空")
    return ("半空条件" if power in ("旺", "相") else "真空条件") if xun_kong else None


def seasonal_evidence(
    *,
    day_ganzhi: str,
    month_branch: str,
    sky_by_earth: dict[str, str],
    god_by_sky: dict[str, str],
) -> dict[str, Any]:
    if (
        not isinstance(day_ganzhi, str)
        or day_ganzhi not in SEXAGENARY_INDEX
        or not isinstance(month_branch, str)
        or month_branch not in MONTH_PARTITION
    ):
        raise ValueError("六壬季节条件需要有效日干支与月建支")
    if (
        not isinstance(sky_by_earth, dict)
        or set(sky_by_earth) != set(BRANCHES)
        or not all(
            isinstance(v, str) and v in BRANCHES and len(v) == 1
            for v in sky_by_earth.values()
        )
        or set(sky_by_earth.values()) != set(BRANCHES)
    ):
        raise ValueError("六壬季节条件需要完整天地盘")
    if (
        len(
            {
                (BRANCHES.index(s) - BRANCHES.index(e)) % 12
                for e, s in sky_by_earth.items()
            }
        )
        != 1
    ):
        raise ValueError("六壬季节条件的天地盘须一致转动")
    if (
        not isinstance(god_by_sky, dict)
        or set(god_by_sky) != set(BRANCHES)
        or not all(
            isinstance(v, str) and v in GOD_ELEMENTS for v in god_by_sky.values()
        )
        or set(god_by_sky.values()) != set(GOD_ELEMENTS)
    ):
        raise ValueError("六壬季节条件需要完整十二天将")
    partition = MONTH_PARTITION[month_branch]
    powers = POWERS[partition]
    empty = list(kongwang_for_ganzhi(day_ganzhi)[:2])
    rows = []
    for earth in BRANCHES:
        sky = sky_by_earth[earth]
        god = god_by_sky[sky]
        sky_phase = branch_element_text(sky)
        earth_phase = branch_element_text(earth)
        god_phase = GOD_ELEMENTS[god]
        power = powers[sky_phase]
        rows.append(
            dict(
                earth_branch=earth,
                sky_branch=sky,
                sky_element=sky_phase,
                sky_seasonal_power=power,
                god=god,
                god_element=god_phase,
                god_seasonal_power=powers[god_phase],
                earth_element=earth_phase,
                earth_seasonal_power=powers[earth_phase],
                sky_xun_kong=sky in empty,
                sky_empty_seasonal_condition=empty_condition(power, sky in empty),
                effective_empty_class=None,
            )
        )
    metadata = seasonal_metadata()
    tail = {
        key: metadata.pop(key)
        for key in (
            "effective_empty_classification",
            "effective_true_half_adjudicated",
            "complete_classical_conformance",
            "scope",
        )
    }
    return dict(
        **metadata,
        day_ganzhi=day_ganzhi,
        month_branch=month_branch,
        season_partition=partition,
        phase_powers=dict(powers),
        day_stem_element=stem_element_text(day_ganzhi[0]),
        day_stem_seasonal_power=powers[stem_element_text(day_ganzhi[0])],
        empty_branches=empty,
        rows=rows,
        raw_true_condition_branches=[
            b for b in empty if powers[branch_element_text(b)] in ("死", "休", "囚")
        ],
        raw_half_condition_branches=[
            b for b in empty if powers[branch_element_text(b)] in ("旺", "相")
        ],
        **tail,
    )


def seasonal_trace(evidence: dict[str, Any]) -> dict[str, Any]:
    return dict(
        rule_id="liuren.seasonal_conditions",
        source_url=evidence["source_url"],
        source_section=evidence["source_title"],
        result={
            k: evidence[k]
            for k in [
                "day_ganzhi",
                "month_branch",
                "season_partition",
                "raw_true_condition_branches",
                "raw_half_condition_branches",
                "effective_empty_classification",
            ]
        },
    )
