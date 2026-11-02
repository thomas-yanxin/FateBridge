"""Named 三诈 triples and unresolved partial readings in Dunjia Yanyi."""

from typing import Any

SOURCE = "https://zh.wikisource.org/w/index.php?oldid=625940"
PROFILE_ID = "yanyi_vol2_three_deceptions_full_triples_v1"
DEFINITIONS = {
    "太阴": ("true_deception", "真诈"),
    "九地": ("heavy_deception", "重诈"),
    "六合": ("rest_deception", "休诈"),
}
GOOD_DOORS = {"开门", "休门", "生门"}
GODS = {"值符", "螣蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天", "勾陈", "朱雀"}


def describe_three_deceptions() -> dict[str, Any]:
    return {
        "id": PROFILE_ID,
        "title": "卷二三诈完整奇门神组合；缺项判断优先未决",
        "source": SOURCE,
        "section": "卷二·三诈五假·三诈",
        "scan_pages": [25, 26],
        "definitions": [
            {
                "rule_id": rule,
                "name": name,
                "god": god,
                "doors": ["开门", "休门", "生门"],
                "wonder_stems": ["乙", "丙", "丁"],
            }
            for god, (rule, name) in DEFINITIONS.items()
        ],
        "layer_mapping": "现行时家转盘天盘三奇（含寄干）、实际八门、所选八神同宫；此层映射为显式实现口径，不宣称已独立验明原书所有盘层",
        "partial_verse_scope": "歌诀及释文说奇、门、太阴三者得二亦吉；不能把太阴自动扩成任意神",
        "partial_prose_scope": "正文另说三门合太阴而无三奇为有阴无奇、犯者不利；缺项解释优先尚未裁定",
        "two_factor_judgment_priority_resolved": False,
        "two_factor_auspiciousness_adopted": False,
        "rhetorical_fractions_are_probabilities": False,
        "human_dun_overlap": "丁、休门、太阴既满足人遁又属于本口径真诈；两名在此共享事实，不算独立印证，不把全部真诈等同人遁",
        "five_false_patterns_evaluated": False,
        "whole_section_reconciled": False,
        "whole_book_conformance_established": False,
    }


def three_deception_context(
    trigram: str, heaven_stems: list[str], door: str, god: str
) -> dict[str, Any]:
    if (
        type(trigram) is not str
        or trigram not in set("坎坤震巽乾兑艮离")
        or type(heaven_stems) is not list
        or not heaven_stems
        or any(
            type(s) is not str or s not in set("戊己庚辛壬癸丁丙乙")
            for s in heaven_stems
        )
        or len(set(heaven_stems)) != len(heaven_stems)
        or type(door) is not str
        or door not in {f"{d}门" for d in "休生伤杜景死惊开"}
        or type(god) is not str
        or god not in GODS
    ):
        raise ValueError(
            "三诈须读取实际外八宫、天盘主寄干、门和所选八神，不猜缺项或套别名"
        )
    wonders = [s for s in heaven_stems if s in "乙丙丁"]
    good_door = door in GOOD_DOORS
    full = bool(wonders) and good_door and god in DEFINITIONS
    rule, name = DEFINITIONS[god] if full else (None, None)
    verse = {
        "heaven_wonder": bool(wonders),
        "good_door": good_door,
        "taiyin": god == "太阴",
    }
    if wonders and good_door and god not in DEFINITIONS:
        partial = "wonder_and_door_without_named_yin_spirit"
    elif not wonders and good_door and god == "太阴":
        partial = "door_and_taiyin_without_wonder_priority_unresolved"
    else:
        partial = None
    return {
        "profile_id": PROFILE_ID,
        "observed_trigram": trigram,
        "observed_heaven_stems": list(heaven_stems),
        "heaven_wonder_stems": wonders,
        "wonder_roles": [
            {"stem": stem, "role": "main" if index == 0 else "hosted"}
            for index, stem in enumerate(heaven_stems)
            if stem in "乙丙丁"
        ],
        "observed_door": door,
        "observed_god": god,
        "matched": full,
        "rule_id": rule,
        "name": name,
        "verse_taiyin_component_presence": verse,
        "verse_exactly_two_components_present": sum(verse.values()) == 2,
        "prose_partial_case": partial,
        "partial_case_is_full_named_triple": False,
        "two_factor_judgment_priority_resolved": False,
        "two_factor_auspiciousness_adopted": False,
        "rhetorical_fractions_converted_to_probability": False,
        "earth_wonder_used_as_heaven_wonder": False,
        "outcome_inference_allowed": False,
        "source": SOURCE,
        "source_scan_pages": [25, 26],
    }


def build_three_deceptions(
    board: dict[str, Any], existing: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for index, palace in enumerate(board["palaces"]):
        if palace["trigram"] == "中":
            continue
        context = three_deception_context(
            palace["trigram"], palace["heaven_stems"], palace["door"], palace["god"]
        )
        palace["evidence"]["three_deceptions"] = context
        if not context["matched"]:
            continue
        path = f"qimen.palaces.{index}"
        local = [p for p in existing if p["palace"] == palace["name"]]
        overlap = [
            p
            for p in local
            if p["rule_id"] == "human_dun"
            and context["rule_id"] == "true_deception"
            and "丁" in context["heaven_wonder_stems"]
            and palace["door"] == "休门"
        ]
        group = f"{path}:overlapping_wonder_door_god_facts"
        for pattern in overlap:
            pattern["qualification"].update(
                {
                    "overlapping_evidence_group": group,
                    "overlapping_rule_ids": [context["rule_id"]],
                    "independent_confirmation": False,
                }
            )
        result.append(
            {
                "rule_id": context["rule_id"],
                "name": context["name"],
                "palace": palace["name"],
                "facts": {
                    "heaven_wonder_stems": context["heaven_wonder_stems"],
                    "door": palace["door"],
                    "god": palace["god"],
                },
                "evidence_paths": [
                    path,
                    f"{path}.evidence.three_deceptions",
                    "qimen.rule_profiles.three_deceptions",
                ],
                "source": SOURCE,
                "section": "卷二·三诈五假·三诈",
                "source_scan_pages": [25, 26],
                "layer": "traditional_rule_match",
                "traditional_meaning": "原文以奇、三吉门与阴神会合命名三诈，并分别联系施恩、收纳或祈禳等古代语境；格名不认定他人欺骗，也不证明现实收益、关系或医疗效果。",
                "qualification": {
                    "condition": "天盘乙丙丁至少一奇、开休生之一门、对应太阴／九地／六合同宫；三层缺一不命名完整三诈",
                    "condition_observed": True,
                    "blocking_rule_names": [],
                    "same_palace_conflicts": [],
                    "coexisting_rule_names": [p["name"] for p in local],
                    "whole_board_restrictions_evaluated": False,
                    "name_match_is_overall_auspiciousness": False,
                    "source_disagreements": list(board["source_disagreements"]),
                    "partial_judgment": "得二亦吉与有阴无奇不利的优先未决；未采纳缺项吉凶或把十分七分当概率",
                    "two_factor_judgment_priority_resolved": False,
                    "overlapping_evidence_group": group if overlap else None,
                    "overlapping_rule_ids": [p["rule_id"] for p in overlap],
                    "independent_confirmation": False,
                    "overall_judgment": "requires_whole_board",
                    "outcome_inference_allowed": False,
                    "three_deceptions_evidence": context,
                },
            }
        )
    return result
