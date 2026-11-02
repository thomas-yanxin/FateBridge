"""Bounded predicates from 探原课体纲要; names never imply event outcomes."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.liureng_course_conditions_convention import CONVENTION
from fatebridge.core.metaphysics.ren_sources import TANYUAN_SCAN_SHA256, TANYUAN_SOURCE

from ...utils.data import EARTHLY_BRANCHES
from .common import GUI_REN_SEQUENCE, SEXAGENARY_INDEX, xun_head_for_ganzhi
from .liureng_course_layout import layout_compatibility_basis, pair_layout_necessity
from .liureng_life_stages import life_stage_cycle
from .liureng_transmissions import STEM_HOUSES

STAGE_PAIRS = (
    ("S01", "退龄", "长生", "青龙"),
    ("S02", "洁己", "沐浴", "玄武"),
    ("S03", "凶服", "冠带", "白虎"),
    ("S04", "衣禄", "临官", "太常"),
    ("S05", "崇位", "帝旺", "贵人"),
    ("S06", "荒淫", "衰", "天后"),
    ("S07", "久患", "病", "勾陈"),
    ("S08", "暗死", "死", "太阴"),
    ("S09", "禁系", "墓", "天空"),
    ("S10", "决绝", "绝", "朱雀"),
    ("S11", "孕童", "胎", "六合"),
    ("S12", "异产", "养", "螣蛇"),
)
GOD_PAIRS = tuple(
    (f"G{i:02}", name, god)
    for i, (name, god) in enumerate(
        zip(
            (
                "干贵",
                "恐惧",
                "文书",
                "交合",
                "争讼",
                "喜庆",
                "朝天",
                "灾伤",
                "宴会",
                "逃脱",
                "暗昧",
                "干妇",
            ),
            GUI_REN_SEQUENCE,
        ),
        1,
    )
)
SCOPE = (
    "仅核对课体纲要所选27条字面条件；十二运以本课日干依探原阳顺阴逆、戊己随丙丁定位，"
    "不取天将五行或承座十二运。斩关取初传辰戌临干寄宫或日支，与金口诀同名条件分开；"
    "一体只取酉酉酉；始终取占日同旬首尾，不取神将固有干支或五子元遁。"
    "各组可以同时命中，不设综合吉凶优先级。病、死、灾伤等仅为传统结构名，"
    "不导出寿命、临床、产育、灾祸或现实结局。题名退龄与遐龄未裁，所选书影读字保留；"
    "其余目录条目及全书一致性未完成，综合判断留空。"
    "另列日干十二运配将的可实现必要条件：仅穷举现支持的两张贵人表、昼夜及顺逆八种配置；可配不保证九宗发用，不可配也不作占事吉凶。崇位所需帝旺支与这些贵人起支无交集，字面公式保留，作者为何列此课的原意未裁，不换参照主体制造命中。"
)


def course_conditions(day_ganzhi: str, transmissions: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(day_ganzhi, str) or day_ganzhi not in SEXAGENARY_INDEX:
        raise ValueError("课体条件需要有效占日干支")
    if not isinstance(transmissions, dict):
        raise ValueError("课体条件需要实际三传")
    rows: list[dict[str, Any]] = []
    for position in ("initial", "middle", "final"):
        r = transmissions.get(position)
        if (
            not isinstance(r, dict)
            or r.get("branch") not in EARTHLY_BRANCHES
            or r.get("earth_branch") not in EARTHLY_BRANCHES
            or r.get("god") not in GUI_REN_SEQUENCE
        ):
            raise ValueError("课体条件需要三传支神、承座及天将")
        rows.append(r)
    branches = [r["branch"] for r in rows]
    initial = rows[0]
    stage = life_stage_cycle(day_ganzhi[0])[branches[0]]
    head = xun_head_for_ganzhi(day_ganzhi)[1]
    tail = EARTHLY_BRANCHES[(EARTHLY_BRANCHES.index(head) + 9) % 12]
    stage_rows = [
        dict(
            id=i,
            name=n,
            required_stage=s,
            required_god=g,
            stage_matches=stage == s,
            god_matches=initial["god"] == g,
            matched=stage == s and initial["god"] == g,
            **pair_layout_necessity(day_ganzhi[0], s, g),
        )
        for i, n, s, g in STAGE_PAIRS
    ]
    god_rows = [
        dict(id=i, name=n, required_god=g, matched=initial["god"] == g)
        for i, n, g in GOD_PAIRS
    ]
    structures = []
    for i, name, condition, checks in (
        (
            "B01",
            "斩关",
            "辰戌临干枝发用",
            [
                ("initial_is_chen_xu", branches[0] in ("辰", "戌")),
                (
                    "seat_is_day_stem_house_or_day_branch",
                    initial["earth_branch"]
                    in (STEM_HOUSES[day_ganzhi[0]], day_ganzhi[1]),
                ),
            ],
        ),
        (
            "B02",
            "一体",
            "三传酉酉酉",
            [("ordered_triple_is_you_you_you", branches == ["酉"] * 3)],
        ),
        (
            "B03",
            "始终",
            "初传属旬首末传属旬尾",
            [
                ("initial_is_day_xun_head", branches[0] == head),
                ("final_is_same_day_xun_tail", branches[2] == tail),
            ],
        ),
    ):
        structures.append(
            dict(
                id=i,
                name=name,
                condition=condition,
                checks=[dict(id=k, matched=v) for k, v in checks],
                matched=all(v for _, v in checks),
            )
        )
    return dict(
        ruleset_id="tanyuan_course_conditions_v1",
        source_title="大六壬探原·卷下集说篇·课体纲要",
        source_url=TANYUAN_SOURCE,
        source_sha256=TANYUAN_SCAN_SHA256,
        original_pdf_pages=[112, 114, 115],
        stage_basis_pdf_pages=[93, 94],
        day_ganzhi=day_ganzhi,
        branches=branches,
        initial_god=initial["god"],
        initial_earth_branch=initial["earth_branch"],
        initial_stage=stage,
        day_stem_house=STEM_HOUSES[day_ganzhi[0]],
        xun_head_branch=head,
        xun_tail_branch=tail,
        stage_god_patterns=stage_rows,
        layout_compatibility_basis=layout_compatibility_basis(),
        god_patterns=god_rows,
        structural_patterns=structures,
        matched_ids=[
            r["id"] for r in stage_rows + god_rows + structures if r["matched"]
        ],
        name_reading_notes=[
            dict(
                id="S01",
                scan_reading="退齡",
                online_transcription="遐龄",
                adjudication=None,
            ),
            dict(
                id="S05",
                scan_reading="崇位",
                online_transcription="祟位",
                adjudication="selected_scan_literal",
            ),
            dict(
                id="S11",
                scan_reading="孕童",
                online_transcription="孕儿",
                adjudication="selected_scan_literal",
            ),
        ],
        comprehensive_judgement=None,
        complete_classical_conformance=False,
        scope=SCOPE,
    )


def course_conditions_trace(evidence: dict[str, Any]) -> dict[str, Any]:
    return dict(
        rule_id="liuren.course_conditions",
        source_url=evidence["source_url"],
        source_section=evidence["source_title"],
        result=evidence,
    )
