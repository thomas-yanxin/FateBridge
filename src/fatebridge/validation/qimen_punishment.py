"""Check six instrument identities and retain two source-scope readings."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.common import MetaphysicsSeed
from fatebridge.core.metaphysics.qimen import _qimen_build_palaces, _qimen_zhifu_zhishi
from fatebridge.core.qimen_evidence import enrich_qimen_evidence
from fatebridge.core.qimen_punishment import describe_punishment, palace_punishment


def audit_punishment(directory: Path) -> dict[str, Any]:
    ref = json.loads((directory / "sources-and-punishment.json").read_text())
    if (
        ref.get("excerpt_file") != "siku-pages33-34.pdf"
        or ref.get("original_one_based_pages") != [33, 34]
        or ref.get("scope_clause") != "六仪击刑者谓六甲直符加所刑之地也"
        or hashlib.sha256((directory / "siku-pages33-34.pdf").read_bytes()).hexdigest()
        != ref["excerpt_sha256"]
    ):
        raise ValueError("击刑须保留完整两页、直符限定及来源指纹")
    definitions = ref["definitions"]
    if len(definitions) != 6 or {r["xun_head"] for r in definitions} != set(
        ("甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅")
    ):
        raise ValueError("击刑须保留六甲关系及王璋六宫列举")
    if (
        len(ref["examples"]) != 2
        or {c["id"] for c in ref["examples"]}
        != {"vol2-yang1-gengwu-punishment", "vol2-yang1-mao-punishment-scope"}
        or ref.get("unresolved_example_ids") != ["vol2-yang1-mao-punishment-scope"]
    ):
        raise ValueError("击刑须保留庚午和未统一的卯时两个原例")
    by_id = {case["id"]: case for case in ref["examples"]}
    positive = by_id["vol2-yang1-gengwu-punishment"]
    disputed = by_id["vol2-yang1-mao-punishment-scope"]
    if (
        positive["hour"] != "庚午"
        or positive.get("source_leader_trigram") != "震"
        or disputed["hour"] != "丁卯"
        or disputed.get("printed_hour_branch") != "卯"
        or disputed.get("printed_day_stem_group") != ["甲", "己"]
        or not all(c["source_claim_matched"] is True for c in ref["examples"])
    ):
        raise ValueError("不得改写庚午宫位、卯时原例、日组或原文击刑判断以消除差异")
    definition_disagreements = []
    profile = describe_punishment()
    for expected in definitions:
        actual = next(
            r for r in profile["definitions"] if r["xun_head"] == expected["xun_head"]
        )
        for key in ("hidden_stem", "punished_branch", "trigram"):
            if actual[key] != expected[key]:
                definition_disagreements.append(
                    {
                        "xun_head": expected["xun_head"],
                        "field": key,
                        "source_value": expected[key],
                        "computed_value": actual[key],
                    }
                )
        actual_number = "坎坤震巽中乾兑艮离".index(actual["trigram"]) + 1
        if expected["palace_number"] != actual_number:
            definition_disagreements.append(
                {
                    "xun_head": expected["xun_head"],
                    "field": "palace_number",
                    "source_value": expected["palace_number"],
                    "computed_value": actual_number,
                }
            )
        probe = palace_punishment(
            expected["xun_head"], expected["trigram"], [expected["hidden_stem"]]
        )
        if not probe["matched"]:
            definition_disagreements.append(
                {
                    "xun_head": expected["xun_head"],
                    "field": "matched",
                    "source_value": True,
                    "computed_value": False,
                }
            )
    examples = []
    for case in ref["examples"]:
        ju = f'{case["dun"]}{"一二三四五六七八九"[case["ju"]-1]}局上元'
        leader = _qimen_zhifu_zhishi(case["hour"], ju, dun_type=case["dun"])
        palaces = _qimen_build_palaces(
            time_ganzhi=case["hour"],
            ju_text=ju,
            dun_type=case["dun"],
            current_term="冬至",
        )
        # This is symbolic source-input verification. The scaffold supplies
        # unrelated calendar fields, not a reconstructed historical date.
        moment = datetime(2026, 1, 1, 12)
        seed = MetaphysicsSeed(
            moment,
            moment,
            "Asia/Shanghai",
            None,
            False,
            0.0,
            {"month": ("丙", "寅")},
            {"current_solar_term": {"name": "冬至"}},
        )
        board = enrich_qimen_evidence(
            {
                "ju_text": ju,
                "palaces": palaces,
                "ju_method": "zhirun",
                "ju_term": "冬至",
                "day_ganzhi": "甲子",
                "time_ganzhi": case["hour"],
                "kongwang": "戌亥空",
            },
            seed=seed,
            leader=leader,
        )
        matches = [
            p for p in board["patterns"] if p["rule_id"] == "six_instrument_punishment"
        ]
        narrow_matched = any(
            p["evidence"]["six_instrument_punishment"]["current_zhifu_matched"]
            for p in palaces
            if p["trigram"] != "中"
        )
        geometry = [
            p["evidence"]["six_instrument_punishment"]
            for p in palaces
            if p["trigram"] != "中"
            and p["evidence"]["six_instrument_punishment"]["geometric_matches"]
        ]
        examples.append(
            {
                "case_id": case["id"],
                "hour_provenance": case["hour_provenance"],
                "source_claim_matched": case["source_claim_matched"],
                "computed_matched": bool(matches),
                "current_zhifu_candidate_matched": narrow_matched,
                "computed_leader_trigram": leader["star_gong"],
                "formal_patterns": matches,
                "retained_geometric_observations": geometry,
                "matches_printed_claim": bool(matches) == case["source_claim_matched"]
                and (
                    "source_leader_trigram" not in case
                    or leader["star_gong"] == case["source_leader_trigram"]
                ),
            }
        )
    unresolved = [
        {
            "case_id": row["case_id"],
            "field": "selected_broad_instrument_punishment",
            "source_value": row["source_claim_matched"],
            "computed_value": row["computed_matched"],
            "status": "selected_broad_reading_and_printed_example_disagree",
        }
        for row in examples
        if not row["matches_printed_claim"]
    ]
    narrow_disagreements = [
        {
            "case_id": row["case_id"],
            "field": "unadopted_current_zhifu_reading",
            "source_value": row["source_claim_matched"],
            "computed_value": row["current_zhifu_candidate_matched"],
            "status": "printed_example_distinguishes_scope_readings",
        }
        for row in examples
        if row["source_claim_matched"] != row["current_zhifu_candidate_matched"]
    ]
    return {
        "method_id": "qimen_six_instrument_scope_source_v1",
        "definition_count": 6,
        "example_count": 2,
        "matched_example_count": sum(r["matches_printed_claim"] for r in examples),
        "definition_disagreements": definition_disagreements,
        "example_disagreements": unresolved,
        "examples": examples,
        "narrow_reading_disagreements": narrow_disagreements,
        "unresolved_source_scope_priorities": [
            {
                "id": "vol2-six-instrument-punishment-scope-priority",
                "field": "meaning_of_six_jia_zhifu_scope",
                "source_wording": "六甲直符",
                "explicit_only_current_xun_wording_present": False,
                "narrow_reading_distinguishing_example": "vol2-yang1-mao-punishment-scope",
                "status": "broad_legacy_preserved_provisionally_scope_not_adjudicated",
            }
        ],
        "reference_input_scope": "Printed ju/hour; mao ganzhi derived from printed day group; no historical civil-date reconstruction",
        "broader_geometric_reading_adopted": True,
        "source_scope_adjudicated": False,
        "whole_section_reconciled": False,
        "whole_book_conformance_established": False,
        "real_world_efficacy_validated": False,
    }
