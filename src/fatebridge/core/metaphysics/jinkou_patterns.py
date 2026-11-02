"""Structural predicates for the 64 entries, independently of book examples.

The scan is the source of definitions, not a lookup table of answers. Known
ambiguous definitions remain unevaluated. Matching a structure does not
license the book's medical, calamity or event-outcome assertions.
"""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.jinkou_pattern_tables import (
    BRANCH_COMBINES,
    HOUSE_BRANCH,
    JINKOU_SCAN_SHA256,
    JINKOU_SCAN_URL,
    STEM_COMBINES,
    TRINES,
)

from ...utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS
from .common import (
    ELEMENT_CONTROLS,
    SIX_CLASH_BRANCHES,
    branch_element_text,
    kongwang_for_ganzhi,
    stem_element_text,
    xun_head_for_ganzhi,
)
from .jinkou_stems import wuzidun_stem

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
UNRESOLVED = {
    52: "隔生的跨位配对尚未裁定，原例不能唯一确定全部条件。",
    53: "隔生的跨位配对尚未裁定，原例不能唯一确定全部条件。",
    56: "需要已核对的星出星没与昼夜交界，不以固定寅时或时支代替。",
    57: "昼将夜位的昼夜所属口径尚未裁定。",
    58: "天乙前后位的距离及带神条件尚未裁定。",
    59: "丁入酉作鬼所指神干、将干和鬼的取法尚未裁定。",
}
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
    24: "神将支六合，上下主客相克；按例释相刑",
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
    54: "贵神克地分、将神克人元、人元克贵神",
    55: "贵神、地分同克人元",
    60: "神将比和、鬼动克人元",
    61: "贵神克将神",
    62: "人元克地分",
    63: "戌天门地分见勾陈辰",
    64: "辰地户地分上见将神天魁戌；不以贵神天空戌代替",
}


def pattern_metadata() -> dict[str, Any]:
    """Identity and limits of this selected excerpt, independent of a course."""
    return {
        "ruleset_id": "jinkou_64_structures_excerpt_v1",
        "source_url": JINKOU_SCAN_URL,
        "source_sha256": JINKOU_SCAN_SHA256,
        "source_section": "卷中·六十四课钤",
        "catalog_count": len(CATALOG),
        "condition_logic": "any_of_all_v1",
        "complete_classical_conformance": False,
        "scope": "仅识别四位结构，允许同时命中多课；evaluations列全64条，matched=true为命中、false为所选定义下未命中、null为疑义未判；六条疑义未判，不把未判当作不成立；不导出原书灾病、生死或现实成败断言；主客按本节上下位释读，部分课例与定义不符仍需校勘",
    }


def pattern_identity(pattern_id: str) -> dict[str, Any]:
    """Canonical implementation labels, not a certificate of literal headings."""
    index = int(pattern_id[1:])
    name, alias, page = CATALOG[index - 1]
    return dict(
        name=name,
        alias=alias,
        original_pdf_page=page,
        condition=CONDITIONS.get(index),
        reason=UNRESOLVED.get(index),
        unresolved=index in UNRESOLVED,
    )


def patterns_from_symbols(
    rows: list[dict[str, Any]], *, day_ganzhi: str
) -> dict[str, Any]:
    """Rebuild rule inputs from raw symbols, not a possibly edited verdict.

    This is the same selected definition set, including its unresolved
    readings and known book-example disagreements. It certifies neither the
    definitions nor the supplied civil day against an external original.
    """
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
    return structural_patterns(inputs, day_ganzhi=day_ganzhi)


def structural_patterns(
    rows: list[dict[str, Any]], *, day_ganzhi: str
) -> dict[str, Any]:
    if len(rows) != 4 or [r["label"] for r in rows] != ["人元", "贵神", "将神", "地分"]:
        raise ValueError("格局需要按人元、贵神、将神、地分排列的四位")
    from .jinkou_pattern_proofs import condition_evidence

    condition_facts, condition_groups, values = condition_evidence(
        rows, day_ganzhi=day_ganzhi
    )
    day_robbery = next(
        f["reference"][0] for f in condition_facts if f["id"] == "robbery_absent"
    )
    indices = [EARTHLY_BRANCHES.index(r["content"]) for r in rows[1:]]
    forward = all((b - a) % 12 == 1 for a, b in zip(indices, indices[1:]))
    if set(values) != set(CONDITIONS) or len(values) + len(UNRESOLVED) != len(CATALOG):
        raise RuntimeError("格局规则清单不完整")
    facts = "、".join(f"{r['label']}{r['content']}({r['element']})" for r in rows)
    matches = []
    evaluations = []
    for index, (name, alias, page) in enumerate(CATALOG, 1):
        result = values.get(index)
        reason = UNRESOLVED.get(index)
        if result is None and index in values:
            reason = (
                "所选定义明确，但本次原始条件有缺项；不将缺少遁干或空亡旗标当作不成立"
            )
        # Absence from the implemented definitions means unknown, never false.
        # Both lists consume this one result, so the complete ledger cannot
        # disagree with the legacy list of positive matches.
        evaluations.append(
            {
                "id": f"P{index:02}",
                "name": name,
                "original_pdf_page": page,
                "status": (
                    "unresolved_definition"
                    if index in UNRESOLVED
                    else (
                        "input_unavailable"
                        if result is None
                        else "matched" if result else "not_matched"
                    )
                ),
                "matched": result,
                "condition": CONDITIONS.get(index),
                "reason": reason,
                "condition_groups": condition_groups.get(index),
            }
        )
        if result is True:
            if index == 64:
                reading = "本条天魁为第三位将神戌；贵神另在第二位，不以天空同属戌代替"
            elif index in (7, 23, 24):
                reading = "按本节上下主客及例中相克解释相刑，非地支刑法"
            else:
                reading = "按所选结构定义"
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
    metadata = pattern_metadata()
    return {
        "ruleset_id": metadata["ruleset_id"],
        "source_url": metadata["source_url"],
        "source_sha256": metadata["source_sha256"],
        "source_section": metadata["source_section"],
        "catalog_count": metadata["catalog_count"],
        "evaluated_rule_count": sum(v is not None for v in values.values()),
        "condition_logic": metadata["condition_logic"],
        "condition_facts": condition_facts,
        "evaluations": evaluations,
        "evaluation_counts": {
            "matched": sum(e["matched"] is True for e in evaluations),
            "not_matched": sum(e["matched"] is False for e in evaluations),
            "unresolved": sum(e["matched"] is None for e in evaluations),
        },
        "matched": matches,
        "unresolved": [
            {"id": r["id"], "name": r["name"], "reason": r["reason"]}
            for r in evaluations
            if r["matched"] is None
        ],
        "day_robbery_branch": day_robbery,
        "complete_classical_conformance": metadata["complete_classical_conformance"],
        "scope": metadata["scope"],
    }


def use_evidence(
    rows: list[dict[str, Any]], strength: dict[str, Any], *, polarity_position: str
) -> dict[str, Any]:
    from .jinkou_sources import use_sources

    row = next(r for r in rows if r["label"] == polarity_position)
    controllers = [
        r["label"] for r in rows if ELEMENT_CONTROLS[r["element"]] == row["element"]
    ]
    no_control = not strength["has_control"]
    return {
        "polarity_position": polarity_position,
        "subject_position": "贵神",
        "controlled_by": controllers,
        "xun_kong": row["xun_kong"],
        "si_da_kong": row["si_da_kong"],
        "month_break": row["month_break"],
        "seasonal_power": row["seasonal_power"],
        "internal_power": row["internal_power"],
        "no_control_principle_applies": no_control,
        "internal_strength_candidates": strength["candidate_positions"],
        "comprehensive_position": None,
        "source_evidence": use_sources(),
        "status": (
            "no_control_strength_priority_unresolved"
            if no_control
            else "polarity_and_afflictions_only"
        ),
        "basis": "入式歌解说四位俱无克从旺取用；阴阳次第五用另定用位。已返回两层及实际受克空破，尚无已校勘依据将其合成唯一综合用神。",
        "scope": "只列原文用虚判断所需的已算事实，克煞等完整裁决尚未完成；不换算成成败概率，不据此另造替代用位",
    }
