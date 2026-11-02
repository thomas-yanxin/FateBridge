"""Named Jingben relations, kept separate from strength and event predictions."""

from __future__ import annotations

from typing import Any

from .common import SIX_CLASH_BRANCHES

SOURCE_URL = "https://upload.wikimedia.org/wikipedia/commons/e/e1/CNTS-00047981961_1_六壬神課金口訣.pdf"
SOURCE_SHA256 = "dfa4b039f30100eb75a8fe21904256bc4e47c04538c8602d08aec9e7f7646364"
# PDF109 reads 午亥火绝 / 子巳水绝. The web table labels the opposite phases;
# identity of the transcription's physical base edition is unverified.
# These are this chapter's four branch pairs, not a generic twelve-stage table.
SI_JUE = {
    frozenset(pair): phase
    for pair, phase in (
        ("寅酉", "金"),
        ("卯申", "木"),
        ("午亥", "火"),
        ("子巳", "水"),
    )
}
SI_BAI = {"水": "酉", "土": "酉", "火": "卯", "木": "子", "金": "午"}
JUE_CONTEXTS = (
    ("将神", "贵神", "正绝", 109),
    ("将神", "日支", "遥绝", 109),
    ("将神", "时支", "次绝", 109),
    ("将神", "地分", "正绝", 110),
    ("地分", "贵神", "正绝", 110),
)
CALENDAR_CONTEXTS = (
    ("year_build", "岁建", ("贵神", "将神"), "year", 115),
    ("year_break", "岁破", ("贵神", "将神", "地分"), "year", 116),
    ("day_build", "日建", ("将神",), "day", 115),
    ("day_clash", "日冲", ("贵神", "将神", "地分"), "day", 115),
)


def absolute_check(left: str, right: str, a: str, b: str) -> dict[str, Any]:
    context = next((c for c in JUE_CONTEXTS if c[:2] == (left, right)), None)
    if context is None or a not in SIX_CLASH_BRANCHES or b not in SIX_CLASH_BRANCHES:
        raise ValueError("四绝须使用本节已有配对角色及明确地支")
    element = SI_JUE.get(frozenset((a, b)))
    return dict(
        left_position=left,
        right_position=right,
        left_branch=a,
        right_branch=b,
        matched=element is not None,
        element=element,
        classification=context[2],
        original_pdf_page=context[3],
        basis=f"{left}{a}与{right}{b}：{element + '绝' if element else '不在本节四绝配对内'}",
    )


def defeat_check(position: str, phase: str, ground: str) -> dict[str, Any]:
    if (
        position not in ("人元", "贵神", "将神")
        or phase not in SI_BAI
        or ground not in SIX_CLASH_BRANCHES
    ):
        raise ValueError("四败须使用所选三位五行及明确共同地分")
    return dict(
        position=position,
        element=phase,
        seat_branch=ground,
        bai_branch=SI_BAI[phase],
        matched=ground == SI_BAI[phase],
        original_pdf_page=110,
        basis=f"{position}{phase}临地分{ground}；本节{phase}败在{SI_BAI[phase]}",
    )


def calendar_target(rule_id: str, reference: str) -> str:
    if (
        rule_id not in {c[0] for c in CALENDAR_CONTEXTS}
        or reference not in SIX_CLASH_BRANCHES
    ):
        raise ValueError("岁日关系须使用所选规则及明确年／日支")
    return reference if rule_id.endswith("build") else SIX_CLASH_BRANCHES[reference]


def calendar_check(
    rule_id: str, position: str, branch: str, reference: str
) -> dict[str, Any]:
    context = next((c for c in CALENDAR_CONTEXTS if c[0] == rule_id), None)
    if (
        context is None
        or position not in context[2]
        or branch not in SIX_CLASH_BRANCHES
    ):
        raise ValueError("岁日关系不支持该规则／位置或地支")
    matched = branch == calendar_target(rule_id, reference)
    return dict(
        rule_id=rule_id,
        name=context[1],
        position=position,
        branch=branch,
        reference_branch=reference,
        matched=matched,
        original_pdf_page=context[4],
        basis=f"{position}{branch}与{'年' if rule_id.startswith('year') else '日'}支{reference}{'同支' if rule_id.endswith('build') else '对冲'}条件：{'符合' if matched else '不符合'}",
    )


def natal_absolute(
    general_branch: str, natal_branch: str | None, *, input_source: str | None = None
) -> dict[str, Any]:
    """将与命: require an explicitly supplied natal branch, never another clock."""
    if general_branch not in SIX_CLASH_BRANCHES or (
        natal_branch is not None and natal_branch not in SIX_CLASH_BRANCHES
    ):
        raise ValueError("大绝需要有效将神支及明确的本命十二地支")
    source = input_source or (
        "explicit_natal_branch" if natal_branch is not None else "not_provided"
    )
    if source not in {
        "explicit_natal_branch",
        "explicit_birth_year_ganzhi",
        "not_provided",
    } or (natal_branch is None) != (source == "not_provided"):
        raise ValueError("本命年支及其明确输入来源不一致")
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
        "original_pdf_page": 109,
        "basis": (
            f"将神{general_branch}与明确输入的命支{natal_branch}："
            f"{element + '绝' if element else '不在本节四绝配对内'}（大绝）"
            if natal_branch is not None
            else "本命支未输入，大绝未计算；不以分析年、日、时、地分或行年支代替"
        ),
        "scope": "仅京本将命四绝配对；命支由调用者明确提供，不从占时推定，不据绝字断言现实结局",
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
    if any(
        branch not in SIX_CLASH_BRANCHES for branch in (*branches.values(), year_branch)
    ):
        raise ValueError("金口诀结构关系需要有效地支")
    if any(row["element"] not in SI_BAI for row in rows):
        raise ValueError("金口诀结构关系需要有效五行")
    jue = [
        absolute_check(left, right, branches[left], branches[right])
        for left, right, _, _ in JUE_CONTEXTS
    ]
    ground = branches["地分"]
    bai = [defeat_check(row["label"], row["element"], ground) for row in rows[:3]]
    calendar = [
        calendar_check(
            rule_id,
            position,
            branches[position],
            year_branch if anchor == "year" else day_branch,
        )
        for rule_id, _, positions, anchor, _ in CALENDAR_CONTEXTS
        for position in positions
    ]
    return {
        "ruleset_id": "jinkou_jingben_relations_v1",
        "source_url": SOURCE_URL,
        "transcription_url": "https://divinehere.com/classic/0905011.html",
        "source_sha256": SOURCE_SHA256,
        "source_section": "卷上·四绝/四败/岁君建破/论岁神",
        "si_jue": {
            "checks": jue,
            "natal": natal,
            "unavailable": (
                [
                    {
                        "left_position": "将神",
                        "right_position": "命支",
                        "classification": "大绝",
                        "status": "missing_birth_branch",
                        "matched": None,
                        "original_pdf_page": 109,
                        "reason": "本命支未输入；不以分析年支或行年支代替",
                    }
                ]
                if natal_branch is None
                else []
            ),
            "scope": "按本节四组配对核对五种课内日时关系及另列的将命大绝；命支省略时大绝未知，不套用一般十二长生，不据绝字断言现实事体结局",
        },
        "si_bai": {
            "checks": bai,
            "scope": "仅计算人元、贵神、将神五行临共同地分；未认证原文遇字的全部位置范围，不能替代季节或课内旺衰",
        },
        "calendar": {
            "year_branch": year_branch,
            "day_branch": day_branch,
            "checks": calendar,
            "scope": "岁建只按神将同岁支；日建只按将神同日支；岁破及日冲核对三支。仅结构事实，不导出年内、日内必然应验",
        },
        "transcription_variants": [
            {
                "branches": ["午", "亥"],
                "scan_element": "火",
                "transcription_element": "水",
                "original_pdf_page": 109,
            },
            {
                "branches": ["子", "巳"],
                "scan_element": "水",
                "transcription_element": "火",
                "original_pdf_page": 109,
            },
        ],
        "complete_classical_conformance": False,
        "scope": "独立结构关系；不改变四位、阴阳用位、三种旺衰或综合取用，不将未算本命关系当作不成立",
    }
