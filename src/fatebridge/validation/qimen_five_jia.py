"""Check retained naming clauses separately from source-layer ambiguities."""

import hashlib
import json
from itertools import product
from pathlib import Path
from typing import Any

from fatebridge.core.qimen_five_jia import describe_five_jia, five_jia_context


def audit_five_jia(directory: Path) -> dict[str, Any]:
    ref = json.loads((directory / "source-and-five-jia.json").read_text())
    definitions = ref["definitions"]
    if (
        ref.get("excerpt_file") != "siku-pages26-35.pdf"
        or ref.get("original_one_based_pages") != [26, 35]
        or hashlib.sha256((directory / "siku-pages26-35.pdf").read_bytes()).hexdigest()
        != ref["excerpt_sha256"]
        or [
            (d["name"], d["door"], "".join(d["heaven_stems"]), d["god"], d["clause"])
            for d in definitions
        ]
        != [
            ("天假", "景门", "乙丙丁", "九天", "若景门合乙丙丁临九天名曰天假"),
            ("地假", "杜门", "丁己癸", "九地", "若杜门合丁己癸下临九地名曰地假"),
            ("神假", "伤门", "丁己癸", "九地", "若伤门合丁己癸下临九地名曰神假"),
            ("鬼假", "死门", "丁己癸", "九地", "若死门合丁己癸临九地名曰鬼假"),
        ]
        or ref["human_jia"]
        != {
            "rule_id": "human_jia",
            "name": "人假",
            "printed_clause": "若惊门合六合下临九天宫名曰人假",
            "status": "unresolved_liuhe_identity_and_layer",
            "supporting_clause": "时加六己如神所使不知六己出被凶咎故己为六合",
            "supporting_page": 35,
            "ji_candidate_adopted": False,
            "ren_emendation_adopted": False,
            "adopted_match": None,
        }
        or ref["unnamed_clauses"]
        != [
            {
                "id": "du_ding_ji_gui_liuhe_unnamed",
                "clause": "若杜门合丁己癸下临六合宫利逃亡",
                "god": "六合",
            },
            {
                "id": "du_ding_ji_gui_taiyin_unnamed",
                "clause": "若杜门合丁己癸下临太阴宫利遣人间谍探事",
                "god": "太阴",
            },
        ]
        or ref.get("all_five_names_computable") is not False
        or ref.get("printed_complete_chart_cases") != 0
    ):
        raise ValueError(
            "五假须保留四条可算定义、人假原字及未决身份、两条未命名旁例与整页指纹"
        )
    errors = []
    profile = describe_five_jia()
    if profile["definitions"] != [
        {k: v for k, v in d.items() if k != "clause"} for d in definitions
    ]:
        errors.append({"kind": "printed_definition_mismatch"})
    if (
        profile["human_jia"]["adopted_match"] is not None
        or profile["all_five_names_computable"] is not False
    ):
        errors.append({"kind": "unwarranted_human_jia_resolution"})
    total = matched = auxiliaries = candidates = 0
    for gua, stem, door, god in product(
        "坎坤震巽乾兑艮离",
        "戊己庚辛壬癸丁丙乙",
        [f"{d}门" for d in "休生伤杜景死惊开"],
        [
            "值符",
            "螣蛇",
            "太阴",
            "六合",
            "白虎",
            "玄武",
            "九地",
            "九天",
            "勾陈",
            "朱雀",
        ],
    ):
        actual = five_jia_context(gua, [stem], door, god)
        expected = [
            d
            for d in definitions
            if stem in d["heaven_stems"] and door == d["door"] and god == d["god"]
        ]
        expected_aux = next(
            (
                d["id"]
                for d in ref["unnamed_clauses"]
                if door == "杜门" and stem in "丁己癸" and god == d["god"]
            ),
            None,
        )
        expected_candidate = door == "惊门" and stem == "己" and god == "九天"
        total += 1
        matched += len(actual["named_matches"])
        auxiliaries += int(actual["unnamed_du_door_clause"] is not None)
        candidates += int(actual["human_jia"]["unadopted_ji_stem_candidate_observed"])
        if (
            [(d["rule_id"], d["name"]) for d in actual["named_matches"]]
            != [(d["rule_id"], d["name"]) for d in expected]
            or actual["unnamed_du_door_clause"] != expected_aux
            or actual["human_jia"]["unadopted_ji_stem_candidate_observed"]
            != expected_candidate
            or actual["human_jia"]["adopted_match"] is not None
            or actual["outcome_inference_allowed"] is not False
        ):
            errors.append(
                {
                    "kind": "finite_context_mismatch",
                    "trigram": gua,
                    "stem": stem,
                    "door": door,
                    "god": god,
                }
            )
    return {
        "method_id": "qimen_five_jia_four_definitions_human_unresolved_v1",
        "source": ref["source"],
        "excerpt_sha256": ref["excerpt_sha256"],
        "printed_computable_naming_definitions": 4,
        "printed_unresolved_naming_definitions": 1,
        "printed_unnamed_clauses": 2,
        "finite_single_stem_context_probes": total,
        "finite_named_match_probes": matched,
        "finite_unnamed_clause_probes": auxiliaries,
        "finite_unadopted_ji_candidate_probes": candidates,
        "implementation_disagreements": errors,
        "unresolved_source_priorities": [
            {
                "id": "vol2-human-jia-liuhe-identity-and-layer",
                "scope": "人假惊门合六合下临九天之六合身份与层次；另段己为六合不足以独立裁定跨段同义",
                "ji_candidate_adopted": False,
                "ren_emendation_adopted": False,
            }
        ],
        "printed_complete_chart_cases": 0,
        "independent_new_reference_cases": 0,
        "whole_section_reconciled": False,
        "real_world_efficacy_validated": False,
    }
