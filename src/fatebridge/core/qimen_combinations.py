"""Conjunctive Qimen patterns with the qualifications retained by Dunjia Yanyi.

Matches are traditional structures, never an outcome score. Source conflicts
stay visible rather than resolving them by changing a computed door or stem.
"""

from __future__ import annotations

from typing import Any, Dict, List

DE_SHI = {"乙": {"己", "辛"}, "丙": {"戊", "庚"}, "丁": {"壬", "癸"}}
ADVERSE_PAIRS = {
    ("乙", "辛"): "青龙逃走",
    ("丙", "庚"): "荧入太白",
    ("丁", "癸"): "朱雀投江",
}
MEANINGS = {
    "heaven_dun": "传统以生门、丙奇和丁奇相合解释藏护与行动配合；原文另要求不犯奇墓、门迫。",
    "earth_dun": "传统以乙奇、开门、己仪相合解释藏护与布置；这是盘面象义，不保证现实行动顺利。",
    "human_dun": "传统将丁奇、休门、太阴相合用于和合、谋议的象义；不能据此读心或保证关系、交易结果。",
    "spirit_dun": "传统以丙奇、生门、九天相合描述象征性的蔽护；结构命中不证明超自然效力。",
    "wonders_de_shi": "传统把三奇加相配六仪称为得使；它可能同时构成冲突格，不能单独解释为吉。",
    "jade_maiden_gate": "丁为玉女，值使门与地盘丁相会称玉女守门，传统用作和合协作的象义，不推断他人意愿。",
    "flying_bird_enters_cave": "丙奇加地盘本时甲旬头，原文称飞鸟跌穴；传统用于会合、得地的象义，不能据此保证现实成功。",
    "dragon_returns_head": "本旬值符所遁六仪加地盘丙，原文称青龙回首；原文另分合奇门与无吉门的层次，此处不据格名合成吉凶。",
    "hidden_palace": "天盘庚加地盘本旬值符原宫，原文称天乙伏宫格；传统描述主客受制，不据此断言某人不在或不会来。",
    "flying_palace": "本旬天盘值符加地盘庚，原文称天乙飞宫格；传统描述主客受制，不据此断言现实胜负或人身灾祸。",
}


def build_combinations(
    board: Dict[str, Any],
    *,
    leader: Dict[str, str],
    source: str,
    existing_patterns: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Read the actual layers, including hosted stems, with no time-table shortcut."""
    result: List[Dict[str, Any]] = []
    for index, palace in enumerate(board["palaces"]):
        if palace["trigram"] == "中":
            continue
        path = f"qimen.palaces.{index}"
        local = [p for p in existing_patterns if p["palace"] == palace["name"]]

        def append(
            rule_id: str,
            name: str,
            facts: Dict[str, Any],
            *,
            section: str,
            scan_pages: List[int],
            condition: str,
            observed: bool,
            blockers: List[str] | None = None,
            conflicts: List[str] | None = None,
            same_leader_required: bool = False,
            identity_binding: Dict[str, Any] | None = None,
        ) -> None:
            source_disagreements = list(board.get("source_disagreements", []))
            result.append(
                {
                    "rule_id": rule_id,
                    "name": name,
                    "palace": palace["name"],
                    "evidence_paths": [path, "qimen.zhifu", "qimen.zhishi"],
                    "facts": facts,
                    "source": source,
                    "section": section,
                    "source_scan_pages": scan_pages,
                    "layer": "traditional_rule_match",
                    "traditional_meaning": MEANINGS[rule_id],
                    "qualification": {
                        "condition": condition,
                        "condition_observed": observed,
                        "blocking_rule_names": blockers or [],
                        "same_palace_conflicts": conflicts or [],
                        "same_xun_leader_required": same_leader_required,
                        "same_xun_leader_observed": leader["star_gong"]
                        == palace["trigram"],
                        "overall_judgment": "requires_whole_board",
                        "outcome_inference_allowed": False,
                        "source_disagreements": source_disagreements,
                        "tomb_rule_evidence_path": f"{path}.evidence.wonder_tomb",
                        "tomb_profile_id": palace.get("evidence", {})
                        .get("wonder_tomb", {})
                        .get("profile_id"),
                    },
                }
            )
            if identity_binding is not None:
                result[-1]["qualification"]["identity_binding"] = identity_binding
                result[-1]["evidence_paths"].extend(
                    ["qimen.xun_head", "qimen.rule_trace.0.outputs"]
                )

        for sky in palace["heaven_stems"]:
            for earth in palace["earth_stems"]:
                facts = {
                    "heaven_stem": sky,
                    "earth_stem": earth,
                    "door": palace["door"],
                }
                hidden = leader["zhifu_heaven_stem"]
                native_host = (
                    "坤" if leader["source_gong"] == "中" else leader["source_gong"]
                )
                ground_head = earth == hidden and palace["trigram"] == native_host
                moving_head = sky == hidden and palace["trigram"] == leader["star_gong"]
                binding = {
                    "scope": "current_hour_xun",
                    "hour_ganzhi": board["time_ganzhi"],
                    "xun_head": leader["xun_head"],
                    "hidden_stem": hidden,
                    "native_raw_trigram": leader["source_gong"],
                    "native_host_trigram": native_host,
                    "moving_trigram": leader["star_gong"],
                    "fixed_wu_substitution_allowed": False,
                    "independent_outcome_evidence": False,
                    "source_example_scope": "selected_jiazi_xun_examples; other_xuns_follow_declared_hour_head_and_hosting_rule",
                }
                for rule_id, name, matched, section, pages, condition in [
                    (
                        "flying_bird_enters_cave",
                        "飞鸟跌穴",
                        sky == "丙" and ground_head,
                        "飞鸟跌穴",
                        [18, 19],
                        "天盘丙加地盘本时甲旬头所遁六仪；不是任意丙戊干对",
                    ),
                    (
                        "dragon_returns_head",
                        "青龙返首",
                        moving_head and earth == "丙",
                        "青龙回首",
                        [19],
                        "本时天盘值符所遁六仪加地盘丙；只判结构，合奇门层次与全盘另核",
                    ),
                    (
                        "hidden_palace",
                        "天乙伏宫格",
                        sky == "庚" and ground_head,
                        "伏宫格",
                        [31, 32],
                        "天盘庚加地盘本旬值符原宫；不是庚与移动八神值符同宫",
                    ),
                    (
                        "flying_palace",
                        "天乙飞宫格",
                        moving_head and earth == "庚",
                        "飞宫格",
                        [32],
                        "本旬移动值符星所遁天盘六仪加地盘庚；不是任意戊庚干对",
                    ),
                ]:
                    if matched:
                        append(
                            rule_id,
                            name,
                            dict(facts),
                            section="卷二·" + section,
                            scan_pages=pages,
                            condition=condition,
                            observed=True,
                            conflicts=list(dict.fromkeys(p["name"] for p in local)),
                            identity_binding=binding,
                        )
                if earth in DE_SHI.get(sky, set()):
                    conflict = ADVERSE_PAIRS.get((sky, earth))
                    same_leader = leader["star_gong"] == palace["trigram"]
                    append(
                        "wonders_de_shi",
                        "三奇得使",
                        facts,
                        section="卷二·三奇得使",
                        scan_pages=[19, 20],
                        condition="若同时为乙辛、丙庚或丁癸，须本旬值符同临；普通得使不自动判吉",
                        observed=not conflict or same_leader,
                        conflicts=[conflict] if conflict else [],
                        same_leader_required=bool(conflict),
                    )
                if sky == "丙" and earth == "丁" and palace["door"] == "生门":
                    blockers = [
                        p["name"]
                        for p in local
                        if p["rule_id"] == "door_pressure"
                        or (
                            p["rule_id"] == "wonder_tomb"
                            and p["facts"]["heaven_stem"] == "丙"
                        )
                    ]
                    append(
                        "heaven_dun",
                        "天遁",
                        facts,
                        section="卷二·天遁",
                        scan_pages=[16, 17],
                        condition="生门、天盘丙、地盘丁同宫，且不可犯丙奇入墓或门迫",
                        observed=not blockers,
                        blockers=blockers,
                    )
                if sky == "乙" and earth == "己" and palace["door"] == "开门":
                    append(
                        "earth_dun",
                        "地遁",
                        facts,
                        section="卷二·地遁",
                        scan_pages=[17],
                        condition="开门、天盘乙、地盘己同宫；仍须合看全局",
                        observed=True,
                    )
            if sky == "丁" and palace["door"] == "休门" and palace["god"] == "太阴":
                append(
                    "human_dun",
                    "人遁",
                    {"heaven_stem": "丁", "door": "休门", "god": "太阴"},
                    section="卷二·人遁",
                    scan_pages=[17, 18],
                    condition="休门、天盘丁、太阴同宫；不以此推断现实和合",
                    observed=True,
                )
            if sky == "丙" and palace["door"] == "生门" and palace["god"] == "九天":
                append(
                    "spirit_dun",
                    "神遁",
                    {"heaven_stem": "丙", "door": "生门", "god": "九天"},
                    section="卷二·神遁",
                    scan_pages=[20],
                    condition="生门、天盘丙、九天同宫；仅记录原典组合",
                    observed=True,
                )
        if palace["trigram"] == leader["door_gong"] and "丁" in palace["earth_stems"]:
            append(
                "jade_maiden_gate",
                "玉女守门",
                {
                    "earth_stem": "丁",
                    "door": palace["door"],
                    "hour_ganzhi": board["time_ganzhi"],
                },
                section="卷二·玉女守门",
                scan_pages=[19],
                condition="本时值使门落地盘丁所在宫，不是天盘丁或任意门逢丁",
                observed=True,
            )
    return result
