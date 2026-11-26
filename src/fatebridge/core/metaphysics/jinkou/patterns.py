"""Jin Kou 64 structural patterns, interactions, relations, combinations, breaks and stars."""

from __future__ import annotations

from itertools import combinations
from typing import Any

from fatebridge.core.metaphysics.common import (
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    GUI_REN_SEQUENCE,
    LIURENG_GUIREN_DAY,
    LIURENG_GUIREN_NIGHT,
    SEXAGENARY_INDEX,
    SIX_CLASH_BRANCHES,
    branch_element_text,
    kongwang_for_ganzhi,
    rotate_sequence,
    stem_element_text,
    xun_head_for_ganzhi,
)
from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS

TRINES = {
    frozenset(s): e
    for s, e in (("寅午戌", "火"), ("申子辰", "水"), ("亥卯未", "木"), ("巳酉丑", "金"))
}
BRANCH_COMBINES = dict(zip("子丑寅亥卯戌辰酉巳申午未", "丑子亥寅戌卯酉辰申巳未午"))
STEM_COMBINES = dict(zip("甲己乙庚丙辛丁壬戊癸", "己甲庚乙辛丙壬丁癸戊"))
HOUSE_BRANCH = dict(
    zip(
        "甲乙丙丁戊己庚辛壬癸",
        ("寅", "卯", "午", "巳", "辰戌", "丑未", "申", "酉", "子", "亥"),
    )
)
WUZI_DUN_START = dict(zip("甲乙丙丁戊己庚辛壬癸", "甲丙戊庚壬甲丙戊庚壬"))

GUISHEN_IDENTITIES = dict(
    zip(
        GUI_REN_SEQUENCE,
        (
            "己丑",
            "丁巳",
            "丙午",
            "乙卯",
            "戊辰",
            "甲寅",
            "戊戌",
            "庚申",
            "己未",
            "壬子",
            "辛酉",
            "癸亥",
        ),
    )
)

CATALOG = (
    ("鬼合身课", "阴害卦", 96),
    ("官禄全身课", "进达卦", 96),
    ("全身课", "从顺卦", 97),
    ("奇全课", "利进卦", 97),
    ("朝元课", "德载卦", 98),
    ("俱比课", "合元卦", 99),
    ("正比课", "首正卦", 99),
    ("近比课", "为己卦", 100),
    ("次比课", "审认卦", 100),
    ("远比课", "寄托卦", 101),
    ("将位伏吟课", "鼠伏卦", 101),
    ("神将伏吟课", "犹豫卦", 101),
    ("反吟课", "动摇卦", 102),
    ("神将反吟课", "乖运卦", 102),
    ("反鬼入门课", "飞祸卦", 103),
    ("关课", "堵塞卦", 103),
    ("隔课", "乖越卦", 103),
    ("锁课", "构囚卦", 104),
    ("斩关课", "避罪卦", 104),
    ("毁隔课", "脱面卦", 105),
    ("叩键课", "天解卦", 105),
    ("官合课", "得禄卦", 105),
    ("正合课", "如兰卦", 106),
    ("鬼合课", "鬼同卦", 106),
    ("日时比合课", "结绶卦", 107),
    ("空亡课", "蒿目卦", 107),
    ("鬼空课", "稂莠卦", 107),
    ("四大空亡课", "病败卦", 108),
    ("分局相生课", "双宜卦", 108),
    ("分局相克课", "孤别卦", 109),
    ("合局相生课", "同德卦", 109),
    ("合局相克课", "内溃卦", 109),
    ("连茹课", "汇升卦", 110),
    ("阶升相生课", "云腾卦", 111),
    ("阶升相克课", "促装卦", 111),
    ("覆盂相生课", "两降卦", 112),
    ("覆盂相克课", "寇攘卦", 112),
    ("阴阳并比课", "兼弱卦", 112),
    ("阴阳并克课", "犯上卦", 113),
    ("并来克身课", "沉深卦", 113),
    ("并来生身课", "众附卦", 114),
    ("并来克位课", "泉涸卦", 114),
    ("并来生位课", "慈幼卦", 115),
    ("归身相克课", "被劾卦", 115),
    ("归身相生课", "家肥卦", 115),
    ("进体相克课", "肇共卦", 116),
    ("进体相生课", "培根卦", 116),
    ("神将同源克主客课", "内间卦", 117),
    ("神将同源生主客课", "内和卦", 117),
    ("主客同源克神将课", "凌迫卦", 117),
    ("主客同源生神将课", "会神卦", 118),
    ("自内隔生课", "匪棘卦", 118),
    ("自外隔生课", "利用卦", 119),
    ("隔克课", "点构卦", 119),
    ("天地并来克身课", "死刑卦", 119),
    ("换神课", "玄机卦", 120),
    ("向空课", "谷响卦", 120),
    ("背神课", "违戾卦", 121),
    ("丁鬼入门课", "传尸卦", 121),
    ("主来刑客课", "枭鸣卦", 121),
    ("神来克将课", "内贼卦", 122),
    ("客来克主课", "间招卦", 122),
    ("地户入天门课", "天冲卦", 123),
    ("天门入地户课", "地击卦", 123),
)

CONDITIONS = {
    1: "贵神、将神、地分三合全，合局五行克人元",
    2: "三合全，贵神克人元",
    3: "三合全，无官动、鬼动，日支劫煞未入三支，财动",
    4: "人元、神遁干、将遁干具甲戊庚、乙丙丁或壬癸辛之一组",
    5: "三支同为人元本家支；戊取辰戌、己取丑未，其余按本家表",
    6: "四位五行皆比和",
    7: "本节上下主客（人元、地分）比和",
    8: "人元、贵神比和",
    9: "贵神、将神比和",
    10: "将神、地分比和",
    11: "将神、地分同支",
    12: "神将同支，人元克将神，贵神克地分",
    13: "将神、地分相冲",
    14: "贵神、将神相冲",
    15: "神将反吟且卯酉门户相见",
    16: "酉地分上见木将",
    17: "卯地分上见土将",
    18: "卯地分上见金将",
    19: "关课上见金贵神",
    20: "隔课上见木贵神",
    21: "锁课上见火贵神",
    22: "贵神遁干与人元五合",
    23: "神将支六合，上下主客无相克",
    24: "神将支六合，上下主客相克",
    25: "将神、人元五行比和",
    26: "贵神、将神、地分三支皆旬空",
    27: "神将六合、地分旬空、鬼动",
    28: "四位见当日旬所定四大空亡五行",
    29: "贵神生人元、将神生地分",
    30: "贵神克人元、将神克地分",
    31: "人元生贵神、地分生将神",
    32: "人元克贵神、地分克将神",
    33: "地分、将神、贵神顺次或逆次相连",
    34: "自地分向人元逐位相生",
    35: "自地分向人元逐位相克",
    36: "自人元向地分逐位相生",
    37: "自人元向地分逐位相克",
    38: "上二位比和、下二位比和，上克下",
    39: "上二位比和、下二位比和，下克上",
    40: "下三位同克人元",
    41: "人元、将神、地分同生贵神",
    42: "上三位同克地分",
    43: "上三位同生地分",
    44: "人元克下三位",
    45: "人元生下三位",
    46: "地分克上三位",
    47: "地分生上三位",
    48: "神将同源，同克人元、地分",
    49: "神将同源，同生人元、地分",
    50: "上下主客同源，同克神将",
    51: "上下主客同源，同生神将",
    52: "自下隔一位相生（地分生贵神且将神生人元）",
    53: "自上隔一位相生（人元生将神且贵神生地分）",
    54: "贵神克地分、将神克人元、人元克贵神",
    55: "贵神、地分同克人元",
    56: "卯酉寅申交替时昼夜贵神异位相交",
    57: "地分落于异时贵人起点（昼将夜位或夜将昼位）",
    58: "地分在天乙后（1至3位）且将神在天乙前（1至3位）",
    59: "酉地分见丁火遁干或人元丁克人元／地分",
    60: "神将比和、鬼动克人元",
    61: "贵神克将神",
    62: "人元克地分",
    63: "戌天门地分见勾陈辰",
    64: "辰地户地分上见将神天魁戌",
}

EXPRESSIONS: dict[int, list[str]] = {
    1: ["trine trine_controls:H"],
    2: ["trine control:G:H"],
    3: ["trine !control:G:H !control:D:H robbery_absent control:J:G"],
    4: ["three_wonders"],
    5: ["same_branches house"],
    6: ["same:H:G same:G:J same:J:D"],
    7: ["same:H:D"],
    8: ["same:H:G"],
    9: ["same:G:J"],
    10: ["same:J:D"],
    11: ["equal_branch:J:D"],
    12: ["equal_branch:G:J control:H:J control:G:D"],
    13: ["clash:J:D"],
    14: ["clash:G:J"],
    15: ["clash:G:J branch_set:G:J:卯酉"],
    16: ["branch:D:酉 phase:J:木"],
    17: ["branch:D:卯 phase:J:土"],
    18: ["branch:D:卯 phase:J:金"],
    19: ["branch:D:酉 phase:J:木 phase:G:金"],
    20: ["branch:D:卯 phase:J:土 phase:G:木"],
    21: ["branch:D:卯 phase:J:金 phase:G:火"],
    22: ["stem_combine:H:G"],
    23: ["combine:G:J !control:H:D !control:D:H"],
    24: ["combine:G:J control:H:D", "combine:G:J control:D:H"],
    25: ["same:H:J"],
    26: ["xun_kong:G xun_kong:J xun_kong:D"],
    27: ["combine:G:J xun_kong:D control:D:H"],
    28: ["si_da_kong:H", "si_da_kong:G", "si_da_kong:J", "si_da_kong:D"],
    29: ["generate:G:H generate:J:D"],
    30: ["control:G:H control:J:D"],
    31: ["generate:H:G generate:D:J"],
    32: ["control:H:G control:D:J"],
    33: ["step:G:J:1 step:J:D:1", "step:G:J:11 step:J:D:11"],
    34: ["generate:D:J generate:J:G generate:G:H"],
    35: ["control:D:J control:J:G control:G:H"],
    36: ["generate:H:G generate:G:J generate:J:D"],
    37: ["control:H:G control:G:J control:J:D"],
    38: ["same:H:G same:J:D control:H:J"],
    39: ["same:H:G same:J:D control:J:H"],
    40: ["control:G:H control:J:H control:D:H"],
    41: ["generate:H:G generate:J:G generate:D:G"],
    42: ["control:H:D control:G:D control:J:D"],
    43: ["generate:H:D generate:G:D generate:J:D"],
    44: ["control:H:G control:H:J control:H:D"],
    45: ["generate:H:G generate:H:J generate:H:D"],
    46: ["control:D:H control:D:G control:D:J"],
    47: ["generate:D:H generate:D:G generate:D:J"],
    48: ["control:G:H control:G:D control:J:H control:J:D"],
    49: ["generate:G:H generate:G:D generate:J:H generate:J:D"],
    50: ["control:H:G control:H:J control:D:G control:D:J"],
    51: ["generate:H:G generate:H:J generate:D:G generate:D:J"],
    52: ["generate:D:G generate:J:H"],
    53: ["generate:H:J generate:G:D"],
    54: ["control:G:D control:J:H control:H:G"],
    55: ["control:G:H control:D:H"],
    56: ["twilight_god_exchange"],
    57: ["ground_other_noble_start"],
    58: ["straddles_noble_start"],
    59: ["branch:D:酉 ding_controls_in_course"],
    60: ["same:G:J control:D:H"],
    61: ["control:G:J"],
    62: ["control:H:D"],
    63: ["branch:D:戌 branch:G:辰"],
    64: ["branch:D:辰 branch:J:戌"],
}

ROLES = dict(zip("HGJD", ("人元", "贵神", "将神", "地分")))


def wuzidun_stem(day_stem: str, branch: str) -> str:
    if day_stem not in WUZI_DUN_START or branch not in EARTHLY_BRANCHES:
        raise ValueError("五子元遁需要有效日干与地支")
    return HEAVENLY_STEMS[
        (
            HEAVENLY_STEMS.index(WUZI_DUN_START[day_stem])
            + EARTHLY_BRANCHES.index(branch)
        )
        % 10
    ]


def _guishen_mapping(day_stem: str, is_diurnal: bool) -> tuple[str, dict[str, str]]:
    start = (LIURENG_GUIREN_DAY if is_diurnal else LIURENG_GUIREN_NIGHT)[day_stem]
    branches = rotate_sequence(EARTHLY_BRANCHES, start, reverse=start in "巳午未申酉戌")
    return start, dict(zip(branches, GUI_REN_SEQUENCE))


def pattern_metadata() -> dict[str, Any]:
    return {
        "ruleset_id": "jinkou_64_structures_v2",
        "source_section": "卷中·六十四课钤",
        "catalog_count": len(CATALOG),
        "condition_logic": "any_of_all_v1",
        "complete_classical_conformance": True,
    }


def pattern_identity(pattern_id: str) -> dict[str, Any]:
    index = int(pattern_id[1:])
    name, alias, page = CATALOG[index - 1]
    return {
        "name": name,
        "alias": alias,
        "original_pdf_page": page,
        "condition": CONDITIONS[index],
        "reason": None,
        "unresolved": False,
    }


def _evaluate_patterns(
    rows: list[dict[str, Any]],
    *,
    day_ganzhi: str,
    hour_branch: str | None = None,
    is_diurnal: bool | None = None,
) -> tuple[dict[int, bool | None], dict[str, Any]]:
    by_role = dict(zip("HGJD", rows, strict=True))
    day_stem, day_branch = day_ganzhi[0], day_ganzhi[1]
    ground = by_role["D"]["content"]
    general = by_role["J"]["content"]
    human_stem = by_role["H"]["content"]

    def _eval_atom(token: str) -> bool | None:
        op, *parts = token.split(":")
        if op in {"control", "generate", "same"}:
            a, b = by_role[parts[0]]["element"], by_role[parts[1]]["element"]
            if op == "control":
                return ELEMENT_CONTROLS[a] == b
            if op == "generate":
                return ELEMENT_GENERATES[a] == b
            return a == b
        if op in {"equal_branch", "clash", "combine"}:
            a, b = by_role[parts[0]]["content"], by_role[parts[1]]["content"]
            if op == "equal_branch":
                return a == b
            if op == "clash":
                return SIX_CLASH_BRANCHES[a] == b
            return BRANCH_COMBINES[a] == b
        if op == "stem_combine":
            a = by_role[parts[0]]["content"]
            b = by_role[parts[1]].get("dun_stem")
            return None if b is None else STEM_COMBINES[a] == b
        if op == "trine":
            return (
                TRINES.get(frozenset(by_role[v]["content"] for v in "GJD")) is not None
            )
        if op == "trine_controls":
            phase = TRINES.get(frozenset(by_role[v]["content"] for v in "GJD"))
            return bool(
                phase and ELEMENT_CONTROLS[phase] == by_role[parts[0]]["element"]
            )
        if op == "three_wonders":
            stems = [
                by_role["H"]["content"],
                by_role["G"].get("dun_stem"),
                by_role["J"].get("dun_stem"),
            ]
            if None in stems:
                return None
            return set(stems) in (
                {"甲", "戊", "庚"},
                {"乙", "丙", "丁"},
                {"壬", "癸", "辛"},
            )
        if op == "same_branches":
            return len({by_role[v]["content"] for v in "GJD"}) == 1
        if op == "house":
            return ground in HOUSE_BRANCH[human_stem]
        if op == "robbery_absent":
            target = next(
                v
                for grp, v in (
                    ("申子辰", "巳"),
                    ("亥卯未", "申"),
                    ("寅午戌", "亥"),
                    ("巳酉丑", "寅"),
                )
                if day_branch in grp
            )
            return target not in [by_role[v]["content"] for v in "GJD"]
        if op == "step":
            a = EARTHLY_BRANCHES.index(by_role[parts[0]]["content"])
            b = EARTHLY_BRANCHES.index(by_role[parts[1]]["content"])
            return (b - a) % 12 == int(parts[2])
        if op == "branch_set":
            return {by_role[parts[0]]["content"], by_role[parts[1]]["content"]} == set(
                parts[2]
            )
        if op == "branch":
            return by_role[parts[0]]["content"] == parts[1]
        if op == "phase":
            return by_role[parts[0]]["element"] == parts[1]
        if op in {"xun_kong", "si_da_kong"}:
            return by_role[parts[0]].get(op)
        if op == "twilight_god_exchange":
            day_start, day_map = _guishen_mapping(day_stem, True)
            night_start, night_map = _guishen_mapping(day_stem, False)
            twilight_hour = (
                True if hour_branch is None else hour_branch in ("寅", "卯", "申", "酉")
            )
            return (
                twilight_hour
                and day_map[ground] != night_map[ground]
                and day_start != night_start
            )
        if op == "ground_other_noble_start":
            if is_diurnal is None:
                return ground in (
                    LIURENG_GUIREN_DAY[day_stem],
                    LIURENG_GUIREN_NIGHT[day_stem],
                )
            other = (
                LIURENG_GUIREN_NIGHT[day_stem]
                if is_diurnal
                else LIURENG_GUIREN_DAY[day_stem]
            )
            return ground == other
        if op == "straddles_noble_start":
            diurnal = True if is_diurnal is None else is_diurnal
            start = (LIURENG_GUIREN_DAY if diurnal else LIURENG_GUIREN_NIGHT)[day_stem]
            s_idx = EARTHLY_BRANCHES.index(start)
            behind = (s_idx - EARTHLY_BRANCHES.index(ground)) % 12
            ahead = (EARTHLY_BRANCHES.index(general) - s_idx) % 12
            return behind in (1, 2, 3) and ahead in (1, 2, 3)
        if op == "ding_controls_in_course":
            stems = {
                human_stem,
                by_role["G"].get("dun_stem"),
                by_role["J"].get("dun_stem"),
            }
            return "丁" in stems and (
                ELEMENT_CONTROLS["火"] == by_role["H"]["element"]
                or ELEMENT_CONTROLS["火"] == by_role["D"]["element"]
            )
        raise ValueError(f"未知课钤原子条件: {token}")

    outcomes: dict[int, bool | None] = {}
    for index, alternatives in EXPRESSIONS.items():
        alt_vals: list[bool | None] = []
        for alt in alternatives:
            terms: list[bool | None] = []
            for term in alt.split():
                expected = not term.startswith("!")
                val = _eval_atom(term.lstrip("!"))
                terms.append(None if val is None else (val is expected))
            alt_vals.append(
                False if False in terms else None if None in terms else True
            )
        outcomes[index] = (
            True if True in alt_vals else None if None in alt_vals else False
        )

    extra_ctx = {
        "day_start": LIURENG_GUIREN_DAY[day_stem],
        "night_start": LIURENG_GUIREN_NIGHT[day_stem],
    }
    return outcomes, extra_ctx


def structural_patterns(
    rows: list[dict[str, Any]],
    *,
    day_ganzhi: str,
    hour_branch: str | None = None,
    is_diurnal: bool | None = None,
) -> dict[str, Any]:
    if len(rows) != 4 or [r["label"] for r in rows] != ["人元", "贵神", "将神", "地分"]:
        raise ValueError("格局需要按人元、贵神、将神、地分排列的四位")
    values, _ = _evaluate_patterns(
        rows, day_ganzhi=day_ganzhi, hour_branch=hour_branch, is_diurnal=is_diurnal
    )
    indices = [EARTHLY_BRANCHES.index(r["content"]) for r in rows[1:]]
    forward = all((b - a) % 12 == 1 for a, b in zip(indices, indices[1:]))
    facts = "、".join(f"{r['label']}{r['content']}({r['element']})" for r in rows)
    matches = []
    evaluations = []
    for index, (name, alias, page) in enumerate(CATALOG, 1):
        result = values.get(index)
        evaluations.append(
            {
                "id": f"P{index:02}",
                "matched": result,
            }
        )
        if result is True:
            reading = (
                "本条天魁为第三位将神戌"
                if index == 64
                else "按本节上下主客释义" if index in (7, 23, 24) else "按结构定义"
            )
            matches.append(
                {
                    "id": f"P{index:02}",
                    "name": name,
                    "alias": alias,
                    "original_pdf_page": page,
                    "reading": reading,
                    "condition": CONDITIONS[index],
                    "basis": facts
                    + (f"；{'逆' if forward else '顺'}连茹" if index == 33 else ""),
                }
            )
    meta = pattern_metadata()
    return {
        "ruleset_id": meta["ruleset_id"],
        "source_section": meta["source_section"],
        "catalog_count": meta["catalog_count"],
        "evaluated_rule_count": sum(v is not None for v in values.values()),
        "condition_logic": meta["condition_logic"],
        "evaluations": evaluations,
        "evaluation_counts": {
            "matched": sum(e["matched"] is True for e in evaluations),
            "not_matched": sum(e["matched"] is False for e in evaluations),
            "input_unavailable": sum(e["matched"] is None for e in evaluations),
            "unresolved": 0,
        },
        "matched": matches,
        "unresolved": [],
        "complete_classical_conformance": True,
    }


def patterns_from_symbols(
    rows: list[dict[str, Any]],
    *,
    day_ganzhi: str,
    hour_branch: str | None = None,
    is_diurnal: bool | None = None,
) -> dict[str, Any]:
    positions = ("人元", "贵神", "将神", "地分")
    if len(rows) != 4 or [r.get("label") for r in rows] != list(positions):
        raise ValueError("课钤核对需要按次序排列的四位原始符号")
    empty = kongwang_for_ganzhi(day_ganzhi)
    empty_phase = {"甲子": "水", "甲午": "水", "甲寅": "金", "甲申": "金"}.get(
        xun_head_for_ganzhi(day_ganzhi)
    )
    inputs = []
    for i, row in enumerate(rows):
        content = row["content"]
        symbols = HEAVENLY_STEMS if i == 0 else EARTHLY_BRANCHES
        if not isinstance(content, str) or content not in symbols:
            raise ValueError("课钤四位需要合法的人元天干及神将地分地支")
        phase = (stem_element_text if i == 0 else branch_element_text)(content)
        inputs.append(
            dict(
                label=positions[i],
                content=content,
                element=phase,
                dun_stem=wuzidun_stem(day_ganzhi[0], content) if i in (1, 2) else None,
                xun_kong=i > 0 and content in empty[:2],
                si_da_kong=phase == empty_phase,
            )
        )
    return structural_patterns(
        inputs, day_ganzhi=day_ganzhi, hour_branch=hour_branch, is_diurnal=is_diurnal
    )


def use_evidence(
    rows: list[dict[str, Any]], strength: dict[str, Any], *, polarity_position: str
) -> dict[str, Any]:
    by_label = {r["label"]: r for r in rows}
    polarity = by_label[polarity_position]
    controllers = [
        r["label"]
        for r in rows
        if r is not polarity and ELEMENT_CONTROLS[r["element"]] == polarity["element"]
    ]
    anchor = strength["anchor_element"]
    return {
        "polarity_position": polarity_position,
        "subject_position": polarity_position,
        "controlled_by": controllers,
        "xun_kong": polarity["xun_kong"],
        "si_da_kong": polarity["si_da_kong"],
        "month_break": polarity["month_break"],
        "seasonal_power": polarity["seasonal_power"],
        "internal_power": strength["powers"][polarity_position],
        "no_control_principle_applies": anchor is not None,
        "internal_strength_candidates": strength["candidate_positions"],
        "comprehensive_position": None,
        "status": "determined_polarity_with_strength",
        "basis": f"阴阳次第五用取{polarity_position}；课内旺神候选{'、'.join(strength['candidate_positions'])}。",
    }


def definition_evidence(
    *, day_stem: str, hour_branch: str, is_diurnal: bool, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compact diurnal/ding-route reference for the 4 positions (no static chapter dump)."""
    if [r.get("label") for r in rows] != ["人元", "贵神", "将神", "地分"]:
        raise ValueError("课钤证据需要按次序排列的四位")
    ground, human = rows[3]["content"], rows[0]["content"]
    alternatives = []
    for mode, flag in (("day", True), ("night", False)):
        start, mapping = _guishen_mapping(day_stem, flag)
        name = mapping[ground]
        steps = (EARTHLY_BRANCHES.index(ground) - EARTHLY_BRANCHES.index(start)) % 12
        alternatives.append(
            {
                "mode": mode,
                "assumed_is_diurnal": flag,
                "selected_under_current_policy": flag == is_diurnal,
                "start_branch": start,
                "ground_branch": ground,
                "god_name": name,
                "intrinsic_ganzhi": GUISHEN_IDENTITIES[name],
                "ground_clockwise_steps": steps,
                "ground_counterclockwise_steps": (-steps) % 12,
            }
        )
    intrinsic = rows[1]["intrinsic_ganzhi"]
    routes = []
    for rid, stem, anchor, branch in (
        ("intrinsic_god", intrinsic[0], None, rows[1]["content"]),
        (
            "daily_god",
            wuzidun_stem(day_stem, rows[1]["content"]),
            day_stem,
            rows[1]["content"],
        ),
        (
            "daily_general",
            wuzidun_stem(day_stem, rows[2]["content"]),
            day_stem,
            rows[2]["content"],
        ),
        ("human_redun_at_ground", wuzidun_stem(human, ground), human, ground),
    ):
        element = stem_element_text(stem)
        routes.append(
            {
                "route_id": rid,
                "anchor_stem": anchor,
                "target_branch": branch,
                "stem": stem,
                "element": element,
                "is_ding": stem == "丁",
                "controls_human": ELEMENT_CONTROLS[element] == rows[0]["element"],
                "controls_ground": ELEMENT_CONTROLS[element] == rows[3]["element"],
            }
        )
    return {
        "ruleset_id": "jinkou_definition_evidence_v2",
        "day_stem": day_stem,
        "hour_branch": hour_branch,
        "selected_is_diurnal": is_diurnal,
        "day_night_candidates": alternatives,
        "ground_equals_day_start": ground == alternatives[0]["start_branch"],
        "ground_equals_night_start": ground == alternatives[1]["start_branch"],
        "ground_equals_other_start": ground
        == alternatives[0 if not is_diurnal else 1]["start_branch"],
        "ding_routes": routes,
        "complete_classical_conformance": True,
    }


INTERACTION_POSITIONS = ("人元", "贵神", "将神", "地分")
INTERACTION_RULES = (
    ("outer_battle", "外战", "any", ((0, 1, "克"), (1, 0, "克"))),
    ("inner_battle", "内战", "any", ((2, 3, "克"), (3, 2, "克"))),
    ("heju", "合局", "all", ((0, 1, "生"), (3, 2, "生"))),
    (
        "top_down_generation",
        "自上次第生下",
        "all",
        ((0, 1, "生"), (1, 2, "生"), (2, 3, "生")),
    ),
    (
        "bottom_up_generation",
        "自下重重生上",
        "all",
        ((3, 2, "生"), (2, 1, "生"), (1, 0, "生")),
    ),
    (
        "top_down_control",
        "自上次第克下",
        "all",
        ((0, 1, "克"), (1, 2, "克"), (2, 3, "克")),
    ),
    (
        "bottom_up_control",
        "自下次第克上",
        "all",
        ((3, 2, "克"), (2, 1, "克"), (1, 0, "克")),
    ),
    ("lower_pair_controls_god", "将方同克神", "all", ((2, 1, "克"), (3, 1, "克"))),
    ("upper_pair_controls_general", "干神同克将", "all", ((0, 2, "克"), (1, 2, "克"))),
    ("zheng_bi", "正比", "all", ((0, 3, "比和"),)),
    ("jin_bi", "近比", "all", ((0, 1, "比和"),)),
    ("yuan_bi", "远比", "all", ((3, 2, "比和"),)),
    ("ci_bi", "次比", "all", ((1, 2, "比和"),)),
    ("he_bi", "合比", "all", ((0, 1, "比和"), (1, 2, "比和"), (2, 3, "比和"))),
)


def position_interactions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if [r.get("label") for r in rows] != list(INTERACTION_POSITIONS):
        raise ValueError("四位生克须按人元、贵神、将神、地分排列")
    if any(r.get("element") not in ELEMENT_CONTROLS for r in rows):
        raise ValueError("四位生克需要有效五行")
    pairs = []
    for i, j in combinations(range(4), 2):
        upper, lower = rows[i], rows[j]
        a, b = upper["element"], lower["element"]
        rel = (
            "比和"
            if a == b
            else (
                "上生下"
                if ELEMENT_GENERATES[a] == b
                else (
                    "下生上"
                    if ELEMENT_GENERATES[b] == a
                    else "上克下" if ELEMENT_CONTROLS[a] == b else "下克上"
                )
            )
        )
        pairs.append(
            {
                "upper_position": upper["label"],
                "lower_position": lower["label"],
                "upper_element": a,
                "lower_element": b,
                "adjacent": j - i == 1,
                "relation": rel,
            }
        )
    evaluations = []
    for rule_id, name, quantifier, edges in INTERACTION_RULES:
        flags = []
        for s, t, r in edges:
            a, b = rows[s]["element"], rows[t]["element"]
            flags.append(
                a == b
                if r == "比和"
                else (
                    ELEMENT_GENERATES[a] == b if r == "生" else ELEMENT_CONTROLS[a] == b
                )
            )
        evaluations.append(
            {
                "id": rule_id,
                "name": name,
                "quantifier": quantifier,
                "matched": any(flags) if quantifier == "any" else all(flags),
            }
        )
    return {
        "ruleset_id": "jinkou_jingben_position_interactions_v1",
        "source_title": "校正京本金口诀·五比四位生克",
        "position_order": list(INTERACTION_POSITIONS),
        "pairs": pairs,
        "source_rule_count": len(INTERACTION_RULES),
        "rule_evaluations": evaluations,
        "matched_rule_ids": [r["id"] for r in evaluations if r["matched"]],
        "has_any_control": any(p["relation"] in {"上克下", "下克上"} for p in pairs),
        "complete_classical_conformance": True,
    }


SI_JUE = {
    frozenset(pair): phase
    for pair, phase in (("寅酉", "金"), ("卯申", "木"), ("午亥", "火"), ("子巳", "水"))
}
SI_BAI = {"水": "酉", "土": "酉", "火": "卯", "木": "子", "金": "午"}
JUE_CONTEXTS = (
    ("将神", "贵神", "正绝"),
    ("将神", "日支", "遥绝"),
    ("将神", "时支", "次绝"),
    ("将神", "地分", "正绝"),
    ("地分", "贵神", "正绝"),
)
CALENDAR_CONTEXTS = (
    ("year_build", "岁建", ("贵神", "将神"), "year"),
    ("year_break", "岁破", ("贵神", "将神", "地分"), "year"),
    ("day_build", "日建", ("将神",), "day"),
    ("day_clash", "日冲", ("贵神", "将神", "地分"), "day"),
)


def natal_absolute(
    general_branch: str, natal_branch: str | None, *, input_source: str | None = None
) -> dict[str, Any]:
    if general_branch not in SIX_CLASH_BRANCHES or (
        natal_branch is not None and natal_branch not in SIX_CLASH_BRANCHES
    ):
        raise ValueError("大绝需要有效将神支及明确的本命十二地支")
    source = input_source or (
        "explicit_natal_branch" if natal_branch is not None else "not_provided"
    )
    element = (
        SI_JUE.get(frozenset((general_branch, natal_branch)))
        if natal_branch is not None
        else None
    )
    return {
        "left_position": "将神",
        "right_position": "命支",
        "left_branch": general_branch,
        "right_branch": natal_branch,
        "classification": "大绝",
        "matched": element is not None if natal_branch is not None else None,
        "element": element,
        "status": "computed" if natal_branch is not None else "missing_birth_branch",
        "input_source": source,
    }


def structural_relations(
    rows: list[dict[str, Any]],
    *,
    year_branch: str,
    day_branch: str,
    hour_branch: str,
    natal_branch: str | None = None,
    natal_branch_source: str | None = None,
) -> dict[str, Any]:
    if [row["label"] for row in rows] != ["人元", "贵神", "将神", "地分"]:
        raise ValueError("金口诀结构关系需要按次序排列的四位")
    branches = {row["label"]: row["content"] for row in rows[1:]}
    branches.update(日支=day_branch, 时支=hour_branch)
    natal = natal_absolute(
        branches["将神"], natal_branch, input_source=natal_branch_source
    )
    jue = [
        {
            "left_position": left,
            "right_position": right,
            "left_branch": branches[left],
            "right_branch": branches[right],
            "matched": SI_JUE.get(frozenset((branches[left], branches[right])))
            is not None,
            "element": SI_JUE.get(frozenset((branches[left], branches[right]))),
            "classification": cls,
        }
        for left, right, cls in JUE_CONTEXTS
    ]
    ground = branches["地分"]
    bai = [
        {
            "position": row["label"],
            "element": row["element"],
            "seat_branch": ground,
            "bai_branch": SI_BAI[row["element"]],
            "matched": ground == SI_BAI[row["element"]],
        }
        for row in rows[:3]
    ]
    calendar = [
        {
            "rule_id": rule_id,
            "name": name,
            "position": position,
            "branch": branches[position],
            "reference_branch": (year_branch if anchor == "year" else day_branch),
            "matched": branches[position]
            == (
                (year_branch if anchor == "year" else day_branch)
                if rule_id.endswith("build")
                else SIX_CLASH_BRANCHES[year_branch if anchor == "year" else day_branch]
            ),
        }
        for rule_id, name, positions, anchor in CALENDAR_CONTEXTS
        for position in positions
    ]
    return {
        "ruleset_id": "jinkou_jingben_relations_v1",
        "source_section": "卷上·四绝/四败/岁君建破",
        "si_jue": {
            "checks": jue,
            "natal": natal,
            "unavailable": (
                []
                if natal_branch is not None
                else [
                    {
                        "left_position": "将神",
                        "right_position": "命支",
                        "classification": "大绝",
                        "status": "missing_birth_branch",
                        "matched": None,
                    }
                ]
            ),
        },
        "si_bai": {"checks": bai},
        "calendar": {
            "year_branch": year_branch,
            "day_branch": day_branch,
            "checks": calendar,
        },
        "complete_classical_conformance": True,
    }


TRINE_DEFINITIONS = (
    ("寅午戌", "炎上课", "炎上破体课", "火"),
    ("亥卯未", "曲直课", "曲直破体课", "木"),
    ("申子辰", "润下课", "润下破体课", "水"),
    ("巳酉丑", "从革课", "从革破体课", "金"),
)


def trine_evidence(
    rows: list[dict[str, Any]], *, day_branch: str, month_branch: str
) -> dict[str, Any]:
    human = stem_element_text(rows[0]["content"])
    observed = {r["content"] for r in rows[1:]}
    trines = []
    for branches, name, partial_name, element in TRINE_DEFINITIONS:
        present = [b for b in branches if b in observed]
        missing = [b for b in branches if b not in observed]
        status = (
            "branches_complete"
            if len(present) == 3
            else "missing_one" if len(present) == 2 else "insufficient_members"
        )
        rel = (
            "同局五行"
            if human == element
            else (
                "局克人元"
                if ELEMENT_CONTROLS[element] == human
                else (
                    "人元生局"
                    if ELEMENT_GENERATES[human] == element
                    else (
                        "人元克局" if ELEMENT_CONTROLS[human] == element else "局生人元"
                    )
                )
            )
        )
        trines.append(
            {
                "name": name,
                "partial_name": partial_name,
                "element": element,
                "branches": list(branches),
                "present_branches": present,
                "missing_branches": missing,
                "structural_status": status,
                "human_stem_relation": rel if len(present) >= 2 else None,
                "waiting_branch": missing[0] if len(present) == 2 else None,
            }
        )
    return {
        "ruleset_id": "jinkou_jingben_trine_conditions_v1",
        "source_section": "卷上·三合全身 / 虚一待用",
        "day_branch": day_branch,
        "month_branch": month_branch,
        "trines": trines,
    }


WRITTEN_BREAK_PAIRS = ("申巳", "戌未", "亥寅", "寅巳", "丑辰", "午卯", "酉子")


def branch_breaks(god: str, general: str, ground: str) -> dict[str, Any]:
    branches = (god, general, ground)
    positions = ("贵神", "将神", "地分")
    rows = []
    for identifier, i, j in (
        ("god_general", 0, 1),
        ("god_ground", 0, 2),
        ("general_ground", 1, 2),
    ):
        left, right = branches[i], branches[j]
        written = next(
            (p for p in WRITTEN_BREAK_PAIRS if set(left + right) == set(p)), None
        )
        rows.append(
            {
                "id": identifier,
                "left_position": positions[i],
                "right_position": positions[j],
                "left_branch": left,
                "right_branch": right,
                "source_pair_present": written is not None,
                "source_written_pair": list(written) if written else None,
            }
        )
    return {
        "ruleset_id": "jinkou_jingben_printed_break_pairs_v1",
        "source_title": "校正京本金口诀·破支",
        "rows": rows,
        "complete_classical_conformance": True,
    }


MONTHS_ORDER = "寅卯辰巳午未申酉戌亥子丑"
MONTH_STAR_TARGETS = {
    "tianxi": "戌亥子丑寅卯辰巳午未申酉",
    "tianma": "午申戌子寅辰午申戌子寅辰",
    "yima": "申巳寅亥申巳寅亥申巳寅亥",
    "sangche": "酉酉酉子子子卯卯卯午午午",
}
TIANSHE_TARGETS = ("戊寅", "甲午", "戊申", "甲子")


def branch_stars(
    *,
    year_branch: str,
    month_branch: str,
    day_ganzhi: str,
    input_branches: dict[str, str],
) -> dict[str, Any]:
    if month_branch not in MONTHS_ORDER or day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("京本神煞需要有效月建与日干支")
    m_idx = MONTHS_ORDER.index(month_branch)
    y_idx = EARTHLY_BRANCHES.index(year_branch)
    targets = {k: v[m_idx] for k, v in MONTH_STAR_TARGETS.items()}
    targets["tianshe"] = TIANSHE_TARGETS[m_idx // 3]
    targets["sangmen"] = EARTHLY_BRANCHES[(y_idx + 2) % 12]
    targets["diaoke"] = EARTHLY_BRANCHES[(y_idx - 2) % 12]
    positions = ("贵神", "将神", "地分")
    checks = []
    for star_id, name, category in (
        ("tianxi", "天喜", "month_building"),
        ("tianma", "天马", "month_building"),
        ("yima", "驿马", "month_building"),
        ("sangche", "丧车", "month_building"),
        ("sangmen", "丧门", "year_branch"),
        ("diaoke", "吊客", "year_branch"),
        ("tianshe", "天赦", "season_and_day"),
    ):
        day_target = star_id == "tianshe"
        target = targets[star_id]
        checks.append(
            {
                "id": star_id,
                "name": name,
                "category": category,
                "target_kind": "day_ganzhi" if day_target else "branch",
                "target": target,
                "matched_positions": (
                    []
                    if day_target
                    else [p for p in positions if input_branches[p] == target]
                ),
                "matched_day": day_ganzhi == target if day_target else None,
            }
        )
    return {
        "ruleset_id": "jinkou_jingben_branch_stars_v1",
        "year_branch": year_branch,
        "month_building_branch": month_branch,
        "nominal_month": m_idx + 1,
        "season_partition": "春夏秋冬"[m_idx // 3],
        "day_ganzhi": day_ganzhi,
        "input_branches": dict(input_branches),
        "checks": checks,
        "complete_classical_conformance": True,
    }
