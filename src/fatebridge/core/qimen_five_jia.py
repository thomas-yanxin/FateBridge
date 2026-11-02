"""Four named 五假 triples; the printed 人假 identity remains unresolved."""

from typing import Any

from fatebridge.core.qimen_three_deceptions import GODS

SOURCE = "https://zh.wikisource.org/w/index.php?oldid=625940"
PROFILE_ID = "yanyi_vol2_five_jia_four_triples_human_unresolved_v1"
DEFINITIONS = [
    ("heaven_jia", "天假", "景门", "乙丙丁", "九天"),
    ("earth_jia", "地假", "杜门", "丁己癸", "九地"),
    ("spirit_jia", "神假", "伤门", "丁己癸", "九地"),
    ("ghost_jia", "鬼假", "死门", "丁己癸", "九地"),
]


def describe_five_jia() -> dict[str, Any]:
    return {
        "id": PROFILE_ID,
        "title": "卷二五假：四条完整组合；人假六合身份未决",
        "source": SOURCE,
        "section": "卷二·三诈五假·五假",
        "scan_pages": [26],
        "definitions": [
            {
                "rule_id": rule,
                "name": name,
                "door": door,
                "heaven_stems": list(stems),
                "god": god,
            }
            for rule, name, door, stems, god in DEFINITIONS
        ],
        "layer_mapping": "显式采用现行天盘干（含寄干）、实际门、所选八神同宫；丁己癸不是三奇，亦不以本时干或地盘干代替天盘干。此为实现口径，不宣称原书所有盘层已独立认证。",
        "human_jia": {
            "rule_id": "human_jia",
            "name": "人假",
            "printed_clause": "若惊门合六合下临九天宫名曰人假",
            "status": "unresolved_liuhe_identity_and_layer",
            "adopted_match": None,
            "literal_eight_gods_reading": "六合与九天不能同时作为同一宫单一八神层的神；这不证明人假不存在",
            "unadopted_ji_stem_candidate": "卷二另段称己为六合（影印35页）；跨段把本句六合解释为天盘己仅作候选，未采纳",
            "supporting_scan_pages": [35],
            "ren_stem_emendation_adopted": False,
            "negative_pattern_inference_allowed": False,
        },
        "unnamed_du_door_cases": "杜门合丁己癸临六合或太阴另有用事说明，原句未另命名地假；只保留组合，不移植九地下地假的名称",
        "all_five_names_computable": False,
        "full_name_is_overall_auspiciousness": False,
        "whole_section_reconciled": False,
        "real_world_efficacy_validated": False,
    }


def five_jia_context(
    trigram: str, heaven_stems: list[str], door: str, god: str
) -> dict[str, Any]:
    if (
        type(trigram) is not str
        or trigram not in set("坎坤震巽乾兑艮离")
        or type(heaven_stems) is not list
        or not heaven_stems
        or any(
            type(s) is not str or s not in "戊己庚辛壬癸丁丙乙" or len(s) != 1
            for s in heaven_stems
        )
        or len(set(heaven_stems)) != len(heaven_stems)
        or type(door) is not str
        or door not in {f"{d}门" for d in "休生伤杜景死惊开"}
        or type(god) is not str
        or god not in GODS
    ):
        raise ValueError(
            "五假须读取实际外八宫、天盘主寄干、门和所选八神；不猜六合身份或补缺项"
        )
    matches = []
    for rule, name, wanted_door, stems, wanted_god in DEFINITIONS:
        eligible = [s for s in heaven_stems if s in stems]
        if door == wanted_door and god == wanted_god and eligible:
            matches.append(
                {
                    "rule_id": rule,
                    "name": name,
                    "qualifying_heaven_stems": eligible,
                    "stem_roles": [
                        {"stem": s, "role": "main" if i == 0 else "hosted"}
                        for i, s in enumerate(heaven_stems)
                        if s in stems
                    ],
                }
            )
    auxiliary = (
        f"du_ding_ji_gui_{'liuhe' if god == '六合' else 'taiyin'}_unnamed"
        if door == "杜门"
        and any(s in "丁己癸" for s in heaven_stems)
        and god in {"六合", "太阴"}
        else None
    )
    return {
        "profile_id": PROFILE_ID,
        "observed_trigram": trigram,
        "observed_heaven_stems": list(heaven_stems),
        "observed_door": door,
        "observed_god": god,
        "named_matches": matches,
        "unnamed_du_door_clause": auxiliary,
        "human_jia": {
            "status": "unresolved_liuhe_identity_and_layer",
            "adopted_match": None,
            "unadopted_ji_stem_candidate_observed": "己" in heaven_stems
            and door == "惊门"
            and god == "九天",
            "candidate_is_formal_match": False,
            "candidate_failure_proves_absence": False,
        },
        "heaven_stem_replaced_by_hour_or_earth_stem": False,
        "outcome_inference_allowed": False,
        "source": SOURCE,
        "source_scan_pages": [26],
    }


def build_five_jia(
    board: dict[str, Any], existing: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for index, palace in enumerate(board["palaces"]):
        if palace["trigram"] == "中":
            continue
        context = five_jia_context(
            palace["trigram"], palace["heaven_stems"], palace["door"], palace["god"]
        )
        palace["evidence"]["five_jia"] = context
        local = [p for p in existing if p["palace"] == palace["name"]]
        for match in context["named_matches"]:
            path = f"qimen.palaces.{index}"
            result.append(
                {
                    "rule_id": match["rule_id"],
                    "name": match["name"],
                    "palace": palace["name"],
                    "facts": {
                        "qualifying_heaven_stems": match["qualifying_heaven_stems"],
                        "door": palace["door"],
                        "god": palace["god"],
                    },
                    "evidence_paths": [
                        path,
                        f"{path}.evidence.five_jia",
                        "qimen.rule_profiles.five_jia",
                    ],
                    "source": SOURCE,
                    "section": "卷二·三诈五假·五假",
                    "source_scan_pages": [26],
                    "layer": "traditional_rule_match",
                    "traditional_meaning": "假为古籍借取门、干、神组合的格名。天假联系进谒，地假联系隐伏，神假与鬼假联系丧葬祭祀语境；名称不证明现实成败、他人行为或神鬼存在，也不据此安排医疗、生死或丧葬时间。",
                    "qualification": {
                        "condition": "所列门、至少一个所列天盘干（含寄干）与指定八神同宫；天假取乙丙丁，其余三类取丁己癸，不统称三奇",
                        "condition_observed": True,
                        "blocking_rule_names": [],
                        "same_palace_conflicts": [],
                        "coexisting_rule_names": [p["name"] for p in local],
                        "whole_board_restrictions_evaluated": False,
                        "name_match_is_overall_auspiciousness": False,
                        "source_disagreements": list(board["source_disagreements"]),
                        "human_jia_identity_resolved": False,
                        "overall_judgment": "requires_whole_board",
                        "outcome_inference_allowed": False,
                        "five_jia_evidence": context,
                    },
                }
            )
    return result
