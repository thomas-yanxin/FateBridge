"""Complete BaZi 神煞 (symbolic stars) engine, strictly separating natal 4 pillars vs 三垣/胎息."""

from __future__ import annotations

from typing import Any, Literal, Mapping

from fatebridge.utils.data import (
    EARTHLY_BRANCHES,
    HEAVENLY_STEMS,
    get_nayin,
    kongwang_for_ganzhi,
)

PEACH_BLOSSOM_TARGETS = (
    (("申", "子", "辰"), "酉"),
    (("寅", "午", "戌"), "卯"),
    (("亥", "卯", "未"), "子"),
    (("巳", "酉", "丑"), "午"),
)
WEN_CHANG_TARGETS = {
    "甲": "巳",
    "乙": "午",
    "丙": "申",
    "丁": "酉",
    "戊": "申",
    "己": "酉",
    "庚": "亥",
    "辛": "子",
    "壬": "寅",
    "癸": "卯",
}
HONG_LUAN_TARGETS = {
    "子": "卯",
    "丑": "寅",
    "寅": "丑",
    "卯": "子",
    "辰": "亥",
    "巳": "戌",
    "午": "酉",
    "未": "申",
    "申": "未",
    "酉": "午",
    "戌": "巳",
    "亥": "辰",
}
TIAN_XI_TARGETS = {
    "子": "酉",
    "丑": "申",
    "寅": "未",
    "卯": "午",
    "辰": "巳",
    "巳": "辰",
    "午": "卯",
    "未": "寅",
    "申": "丑",
    "酉": "子",
    "戌": "亥",
    "亥": "戌",
}
GU_CHEN_TARGETS = {
    branch: target
    for group, target in (
        ("亥子丑", "寅"),
        ("寅卯辰", "巳"),
        ("巳午未", "申"),
        ("申酉戌", "亥"),
    )
    for branch in group
}
GUA_SU_TARGETS = {
    branch: target
    for group, target in (
        ("亥子丑", "戌"),
        ("寅卯辰", "丑"),
        ("巳午未", "辰"),
        ("申酉戌", "未"),
    )
    for branch in group
}

Pillars = Mapping[str, tuple[str, str]]
ORDER = ("year", "month", "day", "hour")

PILLAR_LABELS = {
    "year": "年柱",
    "month": "月柱",
    "day": "日柱",
    "hour": "时柱",
    "taiyuan": "胎元",
    "minggong": "命宫",
    "shengong": "身宫",
    "taixi": "胎息",
}

TIAN_YI_TABLES: dict[str, dict[str, tuple[str, ...]]] = {
    # 甲戊兼牛羊，乙己鼠猴乡，丙丁猪鸡位，壬癸兔蛇藏，六辛逢马虎
    "standard": {
        "甲": ("丑", "未"),
        "戊": ("丑", "未"),
        "庚": ("丑", "未"),
        "乙": ("子", "申"),
        "己": ("子", "申"),
        "丙": ("亥", "酉"),
        "丁": ("亥", "酉"),
        "辛": ("寅", "午"),
        "壬": ("卯", "巳"),
        "癸": ("卯", "巳"),
    },
    # 《三命通会》一说：甲羊戊庚牛（阳贵分主）
    "alt_yang_yin": {
        "甲": ("未", "丑"),
        "戊": ("丑", "未"),
        "庚": ("丑", "未"),
        "乙": ("申", "子"),
        "己": ("子", "申"),
        "丙": ("酉", "亥"),
        "丁": ("亥", "酉"),
        "辛": ("午", "寅"),
        "壬": ("巳", "卯"),
        "癸": ("卯", "巳"),
    },
}

TAI_JI_TARGETS: dict[str, tuple[str, ...]] = {
    "甲": ("子", "午"),
    "乙": ("子", "午"),
    "丙": ("卯", "酉"),
    "丁": ("卯", "酉"),
    "戊": ("辰", "戌", "丑", "未"),
    "己": ("辰", "戌", "丑", "未"),
    "庚": ("寅", "亥"),
    "辛": ("寅", "亥"),
    "壬": ("巳", "申"),
    "癸": ("巳", "申"),
}

TIAN_DE_TARGETS: dict[str, str] = {
    "子": "巳",
    "丑": "庚",
    "寅": "丁",
    "卯": "申",
    "辰": "壬",
    "巳": "辛",
    "午": "亥",
    "未": "甲",
    "申": "癸",
    "酉": "寅",
    "戌": "丙",
    "亥": "乙",
}

TIAN_DE_HE_TARGETS: dict[str, str] = {
    "子": "申",
    "丑": "乙",
    "寅": "壬",
    "卯": "巳",
    "辰": "丁",
    "巳": "丙",
    "午": "寅",
    "未": "己",
    "申": "戊",
    "酉": "亥",
    "戌": "辛",
    "亥": "庚",
}

YUE_DE_TARGETS: dict[str, str] = {
    "寅": "丙",
    "午": "丙",
    "戌": "丙",
    "申": "壬",
    "子": "壬",
    "辰": "壬",
    "亥": "甲",
    "卯": "甲",
    "未": "甲",
    "巳": "庚",
    "酉": "庚",
    "丑": "庚",
}

YUE_DE_HE_TARGETS: dict[str, str] = {
    "寅": "辛",
    "午": "辛",
    "戌": "辛",
    "申": "丁",
    "子": "丁",
    "辰": "丁",
    "亥": "己",
    "卯": "己",
    "未": "己",
    "巳": "乙",
    "酉": "乙",
    "丑": "乙",
}

TRAVEL_HORSE_TARGETS = (
    (("申", "子", "辰"), "寅"),
    (("寅", "午", "戌"), "申"),
    (("亥", "卯", "未"), "巳"),
    (("巳", "酉", "丑"), "亥"),
)
HUA_GAI_TARGETS = (
    (("申", "子", "辰"), "辰"),
    (("寅", "午", "戌"), "戌"),
    (("亥", "卯", "未"), "未"),
    (("巳", "酉", "丑"), "丑"),
)
JIANG_XING_TARGETS = (
    (("申", "子", "辰"), "子"),
    (("寅", "午", "戌"), "午"),
    (("亥", "卯", "未"), "卯"),
    (("巳", "酉", "丑"), "酉"),
)
WANG_SHEN_TARGETS = (
    (("申", "子", "辰"), "亥"),
    (("寅", "午", "戌"), "巳"),
    (("亥", "卯", "未"), "寅"),
    (("巳", "酉", "丑"), "申"),
)
JIE_SHA_TARGETS = (
    (("申", "子", "辰"), "巳"),
    (("寅", "午", "戌"), "亥"),
    (("亥", "卯", "未"), "申"),
    (("巳", "酉", "丑"), "寅"),
)
ZAI_SHA_TARGETS = (
    (("申", "子", "辰"), "午"),
    (("寅", "午", "戌"), "子"),
    (("亥", "卯", "未"), "酉"),
    (("巳", "酉", "丑"), "卯"),
)
LIU_E_TARGETS = (
    (("申", "子", "辰"), "卯"),
    (("寅", "午", "戌"), "酉"),
    (("亥", "卯", "未"), "午"),
    (("巳", "酉", "丑"), "子"),
)

JIN_YU_TARGETS = {
    "甲": "辰",
    "乙": "巳",
    "丙": "未",
    "丁": "申",
    "戊": "未",
    "己": "申",
    "庚": "戌",
    "辛": "亥",
    "壬": "丑",
    "癸": "寅",
}

XUE_TANG_TARGETS = {
    "甲": "亥",
    "乙": "午",
    "丙": "寅",
    "丁": "酉",
    "戊": "寅",
    "己": "酉",
    "庚": "巳",
    "辛": "子",
    "壬": "申",
    "癸": "卯",
}

# 词馆 requires full stem+branch pair (《三命通会》)
CI_GUAN_PILLARS: dict[str, str] = {
    "甲": "庚寅",
    "乙": "辛卯",
    "丙": "乙巳",
    "丁": "戊午",
    "戊": "丁巳",
    "己": "庚午",
    "庚": "壬申",
    "辛": "癸酉",
    "壬": "癸亥",
    "癸": "壬子",
}

LU_SHEN_TARGETS = dict(zip("甲乙丙丁戊己庚辛壬癸", "寅卯巳午巳午申酉亥子"))
YANG_REN_TARGETS = {"甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子"}
YIN_REN_TARGETS = {"乙": "辰", "丁": "未", "己": "未", "辛": "戌", "癸": "丑"}
FEI_REN_TARGETS = {"甲": "酉", "丙": "子", "戊": "子", "庚": "卯", "壬": "午"}

XUE_REN_TARGETS = {
    "寅": "丑",
    "卯": "未",
    "辰": "寅",
    "巳": "申",
    "午": "卯",
    "未": "酉",
    "申": "辰",
    "酉": "戌",
    "戌": "巳",
    "亥": "亥",
    "子": "午",
    "丑": "子",
}

TIAN_YI_DOCTOR_TARGETS = {
    "寅": "丑",
    "卯": "寅",
    "辰": "卯",
    "巳": "辰",
    "午": "巳",
    "未": "午",
    "申": "未",
    "酉": "申",
    "戌": "酉",
    "亥": "戌",
    "子": "亥",
    "丑": "子",
}

FU_XING_TARGETS: dict[str, tuple[str, ...]] = {
    "甲": ("寅", "子"),
    "丙": ("寅", "子"),
    "乙": ("卯", "丑"),
    "癸": ("卯", "丑"),
    "戊": ("申",),
    "己": ("未",),
    "丁": ("亥",),
    "庚": ("午",),
    "辛": ("巳",),
    "壬": ("辰",),
}

GUO_YIN_TARGETS = {
    "甲": "戌",
    "乙": "亥",
    "丙": "丑",
    "丁": "寅",
    "戊": "丑",
    "己": "寅",
    "庚": "辰",
    "辛": "巳",
    "壬": "未",
    "癸": "申",
}

DE_XIU_GROUPS = (
    (("寅", "午", "戌"), ("丙", "丁"), ("戊", "癸")),
    (("申", "子", "辰"), ("壬", "癸", "戊", "己"), ("丙", "辛", "甲")),
    (("巳", "酉", "丑"), ("庚", "辛"), ("乙",)),
    (("亥", "卯", "未"), ("甲", "乙"), ("丁", "壬")),
)

LIU_XIA_TARGETS = {
    "甲": "酉",
    "乙": "戌",
    "丙": "未",
    "丁": "申",
    "戊": "巳",
    "己": "午",
    "庚": "辰",
    "辛": "卯",
    "壬": "亥",
    "癸": "寅",
}

HONG_YAN_TARGETS = {
    "甲": "午",
    "乙": "午",
    "丙": "寅",
    "丁": "未",
    "戊": "辰",
    "己": "辰",
    "庚": "戌",
    "辛": "酉",
    "壬": "子",
    "癸": "申",
}

JIE_LU_KONGWANG_TARGETS = {
    "甲": ("申", "酉"),
    "己": ("申", "酉"),
    "乙": ("午", "未"),
    "庚": ("午", "未"),
    "丙": ("辰", "巳"),
    "辛": ("辰", "巳"),
    "丁": ("寅", "卯"),
    "壬": ("寅", "卯"),
    "戊": ("子", "丑"),
    "癸": ("子", "丑"),
}

SHI_E_DA_BAI = frozenset(
    {"甲辰", "乙巳", "丙申", "丁亥", "戊戌", "己丑", "庚辰", "辛巳", "壬申", "癸亥"}
)
YIN_YANG_CHA_CUO = frozenset(
    {
        "丙子",
        "丁丑",
        "戊寅",
        "辛卯",
        "壬辰",
        "癸巳",
        "丙午",
        "丁未",
        "戊申",
        "辛酉",
        "壬戌",
        "癸亥",
    }
)
SHI_LING_DAYS = frozenset(
    {"甲辰", "乙亥", "丙辰", "丁酉", "戊午", "庚戌", "庚寅", "辛亥", "壬寅", "癸未"}
)
JIN_SHEN_PILLARS = frozenset({"甲子", "甲午", "己卯", "己酉"})
TUI_SHEN_PILLARS = frozenset(
    {"甲戌", "甲辰", "乙丑", "乙未", "戊戌", "戊辰", "己丑", "己未"}
)
SI_FEI_DAYS = {
    "寅": {"庚申", "辛酉"},
    "卯": {"庚申", "辛酉"},
    "辰": {"庚申", "辛酉"},
    "巳": {"壬子", "癸亥"},
    "午": {"壬子", "癸亥"},
    "未": {"壬子", "癸亥"},
    "申": {"甲寅", "乙卯"},
    "酉": {"甲寅", "乙卯"},
    "戌": {"甲寅", "乙卯"},
    "亥": {"丙午", "丁巳"},
    "子": {"丙午", "丁巳"},
    "丑": {"丙午", "丁巳"},
}


def _find_group_target(
    source_branch: str, mappings: tuple[tuple[tuple[str, ...], str], ...]
) -> str | None:
    for group, target in mappings:
        if source_branch in group:
            return target
    return None


def _branch_hits(
    targets: list[str] | tuple[str, ...], branch_map: dict[str, str]
) -> list[str]:
    return [f"{PILLAR_LABELS[k]}{b}" for k, b in branch_map.items() if b in targets]


def _stem_or_branch_hits(
    target: str, stem_map: dict[str, str], branch_map: dict[str, str]
) -> list[str]:
    if target in HEAVENLY_STEMS:
        return [f"{PILLAR_LABELS[k]}{s}" for k, s in stem_map.items() if s == target]
    return [f"{PILLAR_LABELS[k]}{b}" for k, b in branch_map.items() if b == target]


def _pillar_hits(target_pillar: str, pillar_map: dict[str, str]) -> list[str]:
    return [
        f"{PILLAR_LABELS[k]}{p}" for k, p in pillar_map.items() if p == target_pillar
    ]


def _compute_kongwang_details(pillars: Pillars) -> dict[str, Any]:
    active_order = tuple(pos for pos in ORDER if pos in pillars)
    by_pillar = {
        pos: list(kongwang_for_ganzhi(f"{pillars[pos][0]}{pillars[pos][1]}"))
        for pos in active_order
    }
    year_kw = set(by_pillar["year"])
    day_kw = set(by_pillar["day"])
    year_kw_positions = [pos for pos in active_order if pillars[pos][1] in year_kw]
    day_kw_positions = [pos for pos in active_order if pillars[pos][1] in day_kw]

    day_stem = pillars["day"][0]
    hour_tuple = pillars.get("hour")
    jielu_targets = JIE_LU_KONGWANG_TARGETS[day_stem]
    jielu_hit = (hour_tuple[1] in jielu_targets) if hour_tuple is not None else False

    # 四大空亡: 甲子/甲午旬缺水(海/水空), 甲寅/甲申旬缺金(金空)
    day_kw_pair = tuple(by_pillar["day"])
    sida_element = None
    if day_kw_pair in {("戌", "亥"), ("辰", "巳")}:
        sida_element = "水"
    elif day_kw_pair in {("子", "丑"), ("午", "未")}:
        sida_element = "金"

    return {
        "by_pillar": by_pillar,
        "year_kongwang": by_pillar["year"],
        "day_kongwang": by_pillar["day"],
        "year_kongwang_positions": year_kw_positions,
        "day_kongwang_positions": day_kw_positions,
        "jielu_kongwang": {"targets": list(jielu_targets), "hour_hit": jielu_hit},
        "sida_kongwang_element": sida_element,
    }


def _evaluate_star_rules(
    *,
    pillars: Pillars,
    stem_map: dict[str, str],
    branch_map: dict[str, str],
    pillar_map: dict[str, str],
    tian_yi_school: Literal["standard", "alt_yang_yin"] = "standard",
) -> list[dict[str, Any]]:
    year_stem, year_branch = pillars["year"]
    month_branch = pillars["month"][1]
    day_stem, day_branch = pillars["day"]
    day_pillar = f"{day_stem}{day_branch}"
    hour_pillar = (
        f"{pillars['hour'][0]}{pillars['hour'][1]}" if "hour" in pillars else None
    )

    tian_yi_table = TIAN_YI_TABLES[tian_yi_school]
    rows: list[dict[str, Any]] = []

    def add_branch_star(
        label: str, anchor: str, targets: list[str] | tuple[str, ...]
    ) -> None:
        hits = _branch_hits(targets, branch_map)
        rows.append(
            {
                "label": label,
                "anchor": anchor,
                "targets": list(targets),
                "hits": hits,
                "value": "、".join(hits) if hits else "未触发",
            }
        )

    def add_group_star(
        name: str, mappings: tuple[tuple[tuple[str, ...], str], ...]
    ) -> None:
        for anchor_key, anchor_branch in (("年支", year_branch), ("日支", day_branch)):
            target = _find_group_target(anchor_branch, mappings)
            if target:
                add_branch_star(f"{anchor_key}{name}", anchor_key, [target])

    add_group_star("桃花", PEACH_BLOSSOM_TARGETS)
    add_group_star("驿马", TRAVEL_HORSE_TARGETS)
    add_group_star("华盖", HUA_GAI_TARGETS)
    add_group_star("将星", JIANG_XING_TARGETS)
    add_group_star("亡神", WANG_SHEN_TARGETS)
    add_group_star("劫煞", JIE_SHA_TARGETS)
    add_group_star("灾煞", ZAI_SHA_TARGETS)
    add_group_star("六厄", LIU_E_TARGETS)

    # 天乙贵人: both year_stem and day_stem
    add_branch_star("年干天乙贵人", "年干", tian_yi_table[year_stem])
    add_branch_star("日主天乙贵人", "日干", tian_yi_table[day_stem])

    # 孤辰/寡宿: primary anchor year_branch; day_branch labeled distinctly
    add_branch_star("年支孤辰", "年支", [GU_CHEN_TARGETS[year_branch]])
    add_branch_star("年支寡宿", "年支", [GUA_SU_TARGETS[year_branch]])
    add_branch_star("日支孤辰", "日支", [GU_CHEN_TARGETS[day_branch]])
    add_branch_star("日支寡宿", "日支", [GUA_SU_TARGETS[day_branch]])

    add_branch_star("年支红鸾", "年支", [HONG_LUAN_TARGETS[year_branch]])
    add_branch_star("年支天喜", "年支", [TIAN_XI_TARGETS[year_branch]])

    # 禄刃 & 贵人
    add_branch_star("日主禄神", "日干", [LU_SHEN_TARGETS[day_stem]])
    if day_stem in YANG_REN_TARGETS:
        add_branch_star("日主羊刃", "日干", [YANG_REN_TARGETS[day_stem]])
        add_branch_star("日主飞刃", "日干", [FEI_REN_TARGETS[day_stem]])
    else:
        add_branch_star("日主阴刃", "日干", [YIN_REN_TARGETS[day_stem]])

    add_branch_star("日主文昌", "日干", [WEN_CHANG_TARGETS[day_stem]])
    add_branch_star("年干文昌", "年干", [WEN_CHANG_TARGETS[year_stem]])
    add_branch_star("日主学堂", "日干", [XUE_TANG_TARGETS[day_stem]])
    add_branch_star("日主金舆", "日干", [JIN_YU_TARGETS[day_stem]])
    add_branch_star("日主太极贵人", "日干", TAI_JI_TARGETS[day_stem])
    add_branch_star("年干太极贵人", "年干", TAI_JI_TARGETS[year_stem])
    add_branch_star("日主福星贵人", "日干", FU_XING_TARGETS[day_stem])
    add_branch_star("年干福星贵人", "年干", FU_XING_TARGETS[year_stem])
    add_branch_star("日主国印贵人", "日干", [GUO_YIN_TARGETS[day_stem]])
    add_branch_star("年干国印贵人", "年干", [GUO_YIN_TARGETS[year_stem]])
    add_branch_star("日主流霞", "日干", [LIU_XIA_TARGETS[day_stem]])
    add_branch_star("日主红艳", "日干", [HONG_YAN_TARGETS[day_stem]])
    add_branch_star("月支血刃", "月支", [XUE_REN_TARGETS[month_branch]])
    add_branch_star("月支天医", "月支", [TIAN_YI_DOCTOR_TARGETS[month_branch]])

    # 词馆: full stem+branch match!
    for anchor_label, stem_val in (("日主词馆", day_stem), ("年干词馆", year_stem)):
        target_p = CI_GUAN_PILLARS[stem_val]
        hits = _pillar_hits(target_p, pillar_map)
        rows.append(
            {
                "label": anchor_label,
                "anchor": "日干" if "日主" in anchor_label else "年干",
                "targets": [target_p],
                "hits": hits,
                "value": "、".join(hits) if hits else "未触发",
            }
        )

    # 天德 / 天德合 / 月德 / 月德合
    for label, target in (
        ("天德", TIAN_DE_TARGETS[month_branch]),
        ("天德合", TIAN_DE_HE_TARGETS[month_branch]),
        ("月德", YUE_DE_TARGETS[month_branch]),
        ("月德合", YUE_DE_HE_TARGETS[month_branch]),
    ):
        hits = _stem_or_branch_hits(target, stem_map, branch_map)
        rows.append(
            {
                "label": label,
                "anchor": "月支",
                "targets": [target],
                "hits": hits,
                "value": "、".join(hits) if hits else "未触发",
            }
        )

    # 德秀贵人
    for group, de_stems, xiu_stems in DE_XIU_GROUPS:
        if month_branch in group:
            de_hits = [
                f"{PILLAR_LABELS[k]}{s}" for k, s in stem_map.items() if s in de_stems
            ]
            xiu_hits = [
                f"{PILLAR_LABELS[k]}{s}" for k, s in stem_map.items() if s in xiu_stems
            ]
            combined = de_hits if (de_hits and xiu_hits) else []
            if combined:
                combined = de_hits + [h for h in xiu_hits if h not in de_hits]
            rows.append(
                {
                    "label": "德秀贵人",
                    "anchor": "月支",
                    "targets": list(de_stems + xiu_stems),
                    "hits": combined,
                    "value": "、".join(combined) if combined else "未触发",
                }
            )
            break

    # 天罗地网 / 特殊日柱 / 三奇 / 童子 / 进退神 (only emit when checking natal 4 pillars)
    if set(branch_map) == set(ORDER):
        branches_set = set(branch_map.values())
        luo_wang = []
        if {"戌", "亥"} <= branches_set:
            luo_wang.append("天罗(戌亥)")
        if {"辰", "巳"} <= branches_set:
            luo_wang.append("地网(辰巳)")
        rows.append(
            {
                "label": "天罗地网",
                "anchor": "地支",
                "targets": ["戌亥", "辰巳"],
                "hits": luo_wang,
                "value": "、".join(luo_wang) if luo_wang else "未触发",
            }
        )

        # 三奇贵人 (adjacent pillar stems)
        ordered_stems = "".join(stem_map[p] for p in ORDER)
        sanqi_hits = []
        for name, seq in (
            ("天上三奇(甲戊庚)", "甲戊庚"),
            ("地下三奇(乙丙丁)", "乙丙丁"),
            ("人中三奇(壬癸辛)", "壬癸辛"),
        ):
            if seq in ordered_stems:
                sanqi_hits.append(name)
        if sanqi_hits:
            rows.append(
                {
                    "label": "三奇贵人",
                    "anchor": "天干顺排",
                    "targets": ["甲戊庚", "乙丙丁", "壬癸辛"],
                    "hits": sanqi_hits,
                    "value": "、".join(sanqi_hits),
                }
            )

        # 日柱特殊神煞
        for name, table in (
            ("十恶大败", SHI_E_DA_BAI),
            ("阴阳差错", YIN_YANG_CHA_CUO),
            ("十灵日", SHI_LING_DAYS),
        ):
            hit = [f"日柱{day_pillar}"] if day_pillar in table else []
            rows.append(
                {
                    "label": name,
                    "anchor": "日柱",
                    "targets": [day_pillar],
                    "hits": hit,
                    "value": hit[0] if hit else "未触发",
                }
            )

        sifei_hit = (
            [f"日柱{day_pillar}"] if day_pillar in SI_FEI_DAYS[month_branch] else []
        )
        rows.append(
            {
                "label": "四废日",
                "anchor": "月支+日柱",
                "targets": sorted(SI_FEI_DAYS[month_branch]),
                "hits": sifei_hit,
                "value": sifei_hit[0] if sifei_hit else "未触发",
            }
        )

        jinshen_hits = [
            f"{PILLAR_LABELS[p]}{pillar_map[p]}"
            for p in ORDER
            if pillar_map[p] in JIN_SHEN_PILLARS
        ]
        tuishen_hits = [
            f"{PILLAR_LABELS[p]}{pillar_map[p]}"
            for p in ORDER
            if pillar_map[p] in TUI_SHEN_PILLARS
        ]
        if jinshen_hits:
            rows.append(
                {
                    "label": "进神",
                    "anchor": "柱干支",
                    "targets": sorted(JIN_SHEN_PILLARS),
                    "hits": jinshen_hits,
                    "value": "、".join(jinshen_hits),
                }
            )
        if tuishen_hits:
            rows.append(
                {
                    "label": "退神",
                    "anchor": "柱干支",
                    "targets": sorted(TUI_SHEN_PILLARS),
                    "hits": tuishen_hits,
                    "value": "、".join(tuishen_hits),
                }
            )

        # 童子煞: 春秋寅子贵, 冬夏卯未辰 (日支或时支)
        tongzi_targets = (
            ("寅", "子")
            if month_branch in {"寅", "卯", "辰", "申", "酉", "戌"}
            else ("卯", "未", "辰")
        )
        tongzi_hits = [
            f"{PILLAR_LABELS[p]}{branch_map[p]}"
            for p in ("day", "hour")
            if branch_map[p] in tongzi_targets
        ]
        rows.append(
            {
                "label": "童子煞",
                "anchor": "月令+日时支",
                "targets": list(tongzi_targets),
                "hits": tongzi_hits,
                "value": "、".join(tongzi_hits) if tongzi_hits else "未触发",
            }
        )

        # 截路空亡 (day_stem -> hour_branch)
        jielu_targets = JIE_LU_KONGWANG_TARGETS[day_stem]
        jielu_hits = (
            [f"时柱{hour_pillar}"]
            if hour_pillar is not None and pillars["hour"][1] in jielu_targets
            else []
        )
        rows.append(
            {
                "label": "截路空亡",
                "anchor": "日干+时支",
                "targets": list(jielu_targets),
                "hits": jielu_hits,
                "value": jielu_hits[0] if jielu_hits else "未触发",
            }
        )

    return rows


def build_shensha_profile(
    *,
    pillars: Pillars,
    three_origins: dict[str, dict[str, Any]] | None = None,
    taixi: dict[str, Any] | None = None,
    tian_yi_school: Literal["standard", "alt_yang_yin"] = "standard",
) -> dict[str, Any]:
    """Compute complete natal 神煞 strictly separated from 三垣/胎息."""
    active_order = tuple(p for p in ORDER if p in pillars)
    natal_stems = {p: pillars[p][0] for p in active_order}
    natal_branches = {p: pillars[p][1] for p in active_order}
    natal_pillars = {p: f"{pillars[p][0]}{pillars[p][1]}" for p in active_order}

    natal_rows = _evaluate_star_rules(
        pillars=pillars,
        stem_map=natal_stems,
        branch_map=natal_branches,
        pillar_map=natal_pillars,
        tian_yi_school=tian_yi_school,
    )
    kongwang = _compute_kongwang_details(pillars)

    nayin_entries = [
        {
            "label": f"{PILLAR_LABELS[p]}纳音",
            "value": get_nayin(pillars[p][0], pillars[p][1]),
        }
        for p in active_order
    ]

    entries: list[dict[str, str]] = [
        *nayin_entries,
        {"label": "年柱空亡", "value": "".join(kongwang["year_kongwang"])},
        {"label": "月柱空亡", "value": "".join(kongwang["by_pillar"]["month"])},
        {"label": "日柱空亡", "value": "".join(kongwang["day_kongwang"])},
        *(
            [{"label": "时柱空亡", "value": "".join(kongwang["by_pillar"]["hour"])}]
            if "hour" in kongwang["by_pillar"]
            else []
        ),
        *[{"label": row["label"], "value": row["value"]} for row in natal_rows],
    ]

    aux_hits: list[dict[str, str]] = []
    if three_origins or taixi:
        aux_stems: dict[str, str] = {}
        aux_branches: dict[str, str] = {}
        aux_pillars: dict[str, str] = {}
        for k, data in (three_origins or {}).items():
            aux_stems[k] = data["stem"]
            aux_branches[k] = data["branch"]
            aux_pillars[k] = data["pillar"]
            aux_hits.append(
                {"label": f"{PILLAR_LABELS[k]}纳音", "value": data["nayin"]}
            )
        if taixi:
            aux_stems["taixi"] = taixi["stem"]
            aux_branches["taixi"] = taixi["branch"]
            aux_pillars["taixi"] = taixi["pillar"]
            aux_hits.append({"label": "胎息纳音", "value": taixi["nayin"]})
        for row in _evaluate_star_rules(
            pillars=pillars,
            stem_map=aux_stems,
            branch_map=aux_branches,
            pillar_map=aux_pillars,
            tian_yi_school=tian_yi_school,
        ):
            if row["hits"]:
                aux_hits.append({"label": row["label"], "value": row["value"]})

    return {
        "natal_entries": entries,
        "triggered_natal": [
            {"label": row["label"], "anchor": row["anchor"], "hits": row["hits"]}
            for row in natal_rows
            if row["hits"]
        ],
        "three_origins_entries": aux_hits,
        "kongwang": kongwang,
    }


def timing_shensha(
    natal_pillars: Pillars,
    layer_stem: str,
    layer_branch: str,
    *,
    tian_yi_school: Literal["standard", "alt_yang_yin"] = "standard",
) -> list[dict[str, Any]]:
    """Compute ShenSha / 太岁 / 岁破 / 空亡填实 interactions for one timing pillar."""
    year_stem, year_branch = natal_pillars["year"]
    day_stem, day_branch = natal_pillars["day"]
    stars: list[dict[str, Any]] = []

    if layer_branch == year_branch:
        stars.append({"name": "伏吟太岁(本命支)", "anchor": "年支"})
    if EARTHLY_BRANCHES[(EARTHLY_BRANCHES.index(year_branch) + 6) % 12] == layer_branch:
        stars.append({"name": "岁破", "anchor": "年支"})
    if layer_branch in TIAN_YI_TABLES[tian_yi_school][day_stem]:
        stars.append({"name": "天乙贵人", "anchor": "日干"})
    if layer_branch in TIAN_YI_TABLES[tian_yi_school][year_stem]:
        stars.append({"name": "年干天乙贵人", "anchor": "年干"})
    if layer_branch == LU_SHEN_TARGETS[day_stem]:
        stars.append({"name": "禄神", "anchor": "日干"})
    if layer_branch == YANG_REN_TARGETS.get(day_stem):
        stars.append({"name": "羊刃", "anchor": "日干"})
    if layer_branch == WEN_CHANG_TARGETS[day_stem]:
        stars.append({"name": "文昌", "anchor": "日干"})

    for anchor_label, anchor_branch in (("年支", year_branch), ("日支", day_branch)):
        if layer_branch == _find_group_target(anchor_branch, TRAVEL_HORSE_TARGETS):
            stars.append({"name": "驿马", "anchor": anchor_label})
        if layer_branch == _find_group_target(anchor_branch, PEACH_BLOSSOM_TARGETS):
            stars.append({"name": "桃花", "anchor": anchor_label})
        if layer_branch == _find_group_target(anchor_branch, HUA_GAI_TARGETS):
            stars.append({"name": "华盖", "anchor": anchor_label})

    if layer_branch == HONG_LUAN_TARGETS[year_branch]:
        stars.append({"name": "红鸾", "anchor": "年支"})
    if layer_branch == TIAN_XI_TARGETS[year_branch]:
        stars.append({"name": "天喜", "anchor": "年支"})

    day_kw = set(kongwang_for_ganzhi(f"{day_stem}{day_branch}"))
    year_kw = set(kongwang_for_ganzhi(f"{year_stem}{year_branch}"))
    if layer_branch in day_kw:
        stars.append({"name": "填实日柱空亡", "anchor": "日柱"})
    if layer_branch in year_kw:
        stars.append({"name": "填实年柱空亡", "anchor": "年柱"})
    # 冲空: timing branch clashes with a natal kongwang branch that actually sits in natal chart
    clash_branch = EARTHLY_BRANCHES[(EARTHLY_BRANCHES.index(layer_branch) + 6) % 12]
    if clash_branch in day_kw and any(
        natal_pillars[p][1] == clash_branch for p in ORDER if p in natal_pillars
    ):
        stars.append({"name": "冲空(日柱空亡)", "anchor": "日柱"})

    return stars
