"""Source-scoped enclosure geometry; compound judgments remain separate."""

from __future__ import annotations

from typing import Any

SOURCE = "https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷03#推提挟法"
FACSIMILE = "https://commons.wikimedia.org/wiki/File:NCL-06604_太乙金鏡式經.pdf#page=51"
PAIR_PROFILE = "taojin_same_side_general_pair_v1"
PAIR_SOURCE = (
    "https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第687卷#提挾"
)
PAIR_ANNOTATIONS = (
    "https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第694卷"
)
PAIR_FACSIMILE = "https://zh.wikisource.org/wiki/Page:Gujin_Tushu_Jicheng,_Volume_477_(1700-1725).djvu/70"
GENERAL_FIELDS = {
    "main_general": "主大将",
    "main_vice_general": "主参将",
    "guest_general": "客大将",
    "guest_vice_general": "客参将",
}


def principal_enclosures(core: dict[str, Any]) -> list[dict[str, Any]]:
    """Use physical bearings, not numeric palace adjacency or a gate sector.

    One general and Taiyi flank a principal palace on its immediate two
    sides. NCL p51: 艮(主大三), 卯(始击/客大四), 巽(太乙九).
    A central general has no bearing and cannot serve as an endpoint.
    """
    from fatebridge.core.metaphysics.taiyi_geometry import PALACE_ORDER, PALACES

    ring = [PALACES[n] for n in PALACE_ORDER]
    taiyi = core["taiyi_palace"]
    index = ring.index(taiyi)
    targets = {
        "wenchang_palace": ("文昌", core["wenchang_palace"]),
        "shiji": ("始击", core["shiji"]),
        **{
            field: (label, PALACES[core[field]])
            for field, label in GENERAL_FIELDS.items()
        },
    }

    def fact(field: str) -> dict[str, Any]:
        return {
            "field": (
                field
                if field in {"taiyi_palace", "wenchang_palace"}
                else "core_board." + field
            ),
            "value": core[field],
        }

    patterns = []
    for field, label in GENERAL_FIELDS.items():
        end = PALACES[core[field]]
        if end not in ring:
            continue
        distance = (ring.index(end) - index) % 8
        if distance not in (2, 6):
            continue
        middle = ring[(index + (1 if distance == 2 else -1)) % 8]
        for target, (subject, palace) in targets.items():
            if target == field or palace != middle:
                continue
            patterns.append(
                {
                    "name": "提挟",
                    "subject": subject,
                    "variant": f"太乙与{label}夹{subject}于正宫",
                    "basis": [fact("taiyi_palace"), fact(field), fact(target)],
                    "traditional_meaning": f"太乙{taiyi}与{label}{end}从相邻两侧夹{subject}{middle}；命中李法正宫提挟的空间条件",
                    "source": SOURCE,
                    "scope": "只核正宫提挟几何；挟闭及四郭固杜未裁定，未核内外生死等后续断语，不能推出实际胜负",
                }
            )
    return patterns


def general_pair_enclosures(core: dict[str, Any]) -> list[dict[str, Any]]:
    """Read the short arc between one side's actual major/minor generals.

    The two principal endpoints flank one principal and its two intercalary
    neighbors. Yang19 explicitly places the enclosed eye at 申, not the
    midpoint 坤: never collapse it to a gate sector or require equal distance.
    No cross-side endpoint pair or same-side eye is inferred from this rule.
    """
    from fatebridge.core.metaphysics.taiyi_geometry import PALACE_ORDER, PALACES, RING

    ring = [PALACES[n] for n in PALACE_ORDER]
    patterns = []
    for camp, prefix, opposite in (("main", "主", "guest"), ("guest", "客", "main")):
        first, second = camp + "_general", camp + "_vice_general"
        a, b = PALACES[core[first]], PALACES[core[second]]
        if a not in ring or b not in ring:
            continue
        distance = (ring.index(b) - ring.index(a)) % 8
        if distance not in (2, 6):
            continue
        step = 1 if distance == 2 else -1
        inside = {RING[(RING.index(a) + step * j) % 16] for j in (1, 2, 3)}
        eye = "shiji" if opposite == "guest" else "wenchang_palace"
        targets = {
            "taiyi_palace": ("太乙", core["taiyi_palace"]),
            eye: ("始击" if opposite == "guest" else "文昌", core[eye]),
            **{
                field: (GENERAL_FIELDS[field], PALACES[core[field]])
                for field in (opposite + "_general", opposite + "_vice_general")
            },
        }
        for field, (label, palace) in targets.items():
            if palace not in inside:
                continue
            kind = "正宫" if palace in ring else "间神"
            facts = [
                {"field": "core_board." + first, "value": core[first]},
                {"field": "core_board." + second, "value": core[second]},
                {
                    "field": (
                        field
                        if field in {"taiyi_palace", "wenchang_palace"}
                        else "core_board." + field
                    ),
                    "value": core[field],
                },
            ]
            patterns.append(
                {
                    "name": "提挟",
                    "subject": label,
                    "variant": f"{prefix}方二将夹{label}于{kind}",
                    "basis": facts,
                    "traditional_meaning": f"{prefix}大将{a}与{prefix}参将{b}短弧夹{label}{palace}；{kind}夹持几何命中",
                    "source": PAIR_SOURCE if kind == "正宫" else PAIR_ANNOTATIONS,
                    "relation_profile": PAIR_PROFILE,
                    "scope": "同方二将夹持几何；间神命中不认证完整挟闭，亦不据此断现实胜负。",
                }
            )
    return patterns


def enclosure_assessment(
    patterns: list[dict[str, Any]], *, core: dict[str, Any] | None = None
) -> dict[str, Any]:
    refs = [
        f"taiyi.patterns.{i}" for i, p in enumerate(patterns) if p["name"] == "提挟"
    ]
    pairs = general_pair_enclosures(core) if core is not None else []
    pair_refs = [
        f"taiyi.enclosure_assessment.two_general_enclosure.patterns.{i}"
        for i in range(len(pairs))
    ]
    return {
        "ruleset": {
            "id": "jinjing_vol3_principal_enclosure_v1",
            "version": "1.0.0",
            "author": "FateBridge contributors",
            "classical_author": "李淳风条文，王希明编录",
            "sources": [SOURCE, FACSIMILE],
        },
        "principal_enclosure": {
            "status": "assessed_geometry",
            "present": bool(refs),
            "pattern_paths": refs,
            "meaning": (
                "命中所核的正宫提挟几何；逐项读取同盘太乙、夹将与被夹主体。"
                if refs
                else "未命中所核的正宫提挟几何；不据此断言全部提挟、挟闭或四郭条件均不存在。"
            ),
        },
        "two_general_ruleset": {
            "id": PAIR_PROFILE,
            "version": "1.0.0",
            "author": "FateBridge contributors",
            "classical_author": "太乙淘金歌及太乙局局注；金镜卷三张良条并参",
            "sources": [PAIR_SOURCE, PAIR_ANNOTATIONS, PAIR_FACSIMILE, SOURCE],
        },
        "two_general_enclosure": {
            "status": "assessed_geometry" if core is not None else "not_assessed",
            "present": bool(pair_refs) if core is not None else None,
            "pattern_paths": pair_refs,
            "patterns": pairs,
            "meaning": (
                "缺少同次核心，二将夹持未评估。"
                if core is None
                else (
                    "命中同方大小二将短弧夹太乙或对方目将的几何；逐项读取三主体。"
                    if pair_refs
                    else "未命中所核二将夹持几何；不据此否定其他提挟或挟闭分支。"
                )
            ),
        },
        "unassessed": [
            {
                "name": "挟闭",
                "status": "not_assessed",
                "reason": "间神夹目几何可另读，但完整挟闭的二目、二将、太乙复合条件仍待裁定。",
            },
            {
                "name": "四郭固",
                "status": "not_assessed",
                "reason": "或客目临之等分支的合取范围待完整校勘。",
            },
            {
                "name": "四郭杜",
                "status": "not_assessed",
                "reason": "主参/主大版本异文与原例关系待完整校勘。",
            },
        ],
        "scope": "两种夹持几何分别读取；同宫不同主体保留各自依据，不作独立古例。后续断语另核；不改变卷四五将三项或门具将发合取，不认证全书符合。",
    }


def enclosures_text(assessment: dict[str, Any]) -> str:
    hit = assessment["principal_enclosure"]
    refs = "、".join(hit["pattern_paths"])
    return (
        str(hit["meaning"])
        + (f"依据：{refs}。" if refs else "")
        + str(assessment["two_general_enclosure"]["meaning"])
        + "".join(
            f"{p['variant']}：{p['traditional_meaning']}；{p['scope']}。"
            for p in assessment["two_general_enclosure"]["patterns"]
        )
        + (
            "依据："
            + "、".join(assessment["two_general_enclosure"]["pattern_paths"])
            + "。"
            if assessment["two_general_enclosure"]["pattern_paths"]
            else ""
        )
        + "完整挟闭、四郭固、四郭杜均未评估。"
        + str(assessment["scope"])
    )
