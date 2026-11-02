"""Audit the three printed naming clauses without grading real outcomes."""

import hashlib
import json
from itertools import product
from pathlib import Path
from typing import Any

from fatebridge.core.qimen_three_deceptions import (
    describe_three_deceptions,
    three_deception_context,
)


def audit_three_deceptions(directory: Path) -> dict[str, Any]:
    ref = json.loads((directory / "source-and-three-deceptions.json").read_text())
    if (
        ref.get("excerpt_file") != "siku-pages25-26.pdf"
        or ref.get("original_one_based_pages") != [25, 26]
        or hashlib.sha256((directory / "siku-pages25-26.pdf").read_bytes()).hexdigest()
        != ref["excerpt_sha256"]
        or len(ref["definitions"]) != 3
        or {(d["name"], d["god"]) for d in ref["definitions"]}
        != {("真诈", "太阴"), ("重诈", "九地"), ("休诈", "六合")}
        or len(ref["partial_clauses"]) != 3
        or {d["id"] for d in ref["partial_clauses"]}
        != {
            "verse-two-components",
            "prose-wonder-door-without-yin",
            "prose-door-taiyin-no-wonder",
        }
        or {d["clause"] for d in ref["partial_clauses"]}
        != {
            "奇与门兮共太阴三般难得总加临若还得二亦为吉举措行藏必遂心",
            "若三门合三奇无诈宫谓之有奇无阴得七分之利",
            "若三门合太阴无三奇谓之有阴无奇犯者不利",
        }
        or ref.get("partial_priority_resolved") is not False
        or ref.get("rhetorical_fractions_are_probabilities") is not False
        or ref.get("printed_complete_chart_cases") != 0
    ):
        raise ValueError(
            "三诈须保留三条完整命名、三条缺项语境、整页指纹及未决范围，不伪造印例或概率"
        )
    profile = describe_three_deceptions()
    errors: list[dict[str, Any]] = []
    if profile["definitions"] != [
        {k: v for k, v in d.items() if k != "clause"} for d in ref["definitions"]
    ]:
        errors.append({"kind": "printed_name_definition_mismatch"})
    if profile.get("two_factor_judgment_priority_resolved") is not False:
        errors.append({"kind": "unwarranted_partial_priority_resolution"})
    if profile.get("rhetorical_fractions_are_probabilities") is not False:
        errors.append({"kind": "unwarranted_probability_mapping"})
    probe_count = 0
    matched = 0
    # Exhaustive single-stem domain probes; these are not 5760 printed cases.
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
        actual = three_deception_context(gua, [stem], door, god)
        expected = next(
            (
                d
                for d in ref["definitions"]
                if stem in d["wonder_stems"] and door in d["doors"] and god == d["god"]
            ),
            None,
        )
        probe_count += 1
        matched += int(actual["matched"])
        if (
            actual["matched"] != (expected is not None)
            or actual["rule_id"] != (expected["rule_id"] if expected else None)
            or actual["name"] != (expected["name"] if expected else None)
        ):
            errors.append(
                {
                    "kind": "finite_domain_mismatch",
                    "trigram": gua,
                    "stem": stem,
                    "door": door,
                    "god": god,
                }
            )
        if (
            actual.get("two_factor_auspiciousness_adopted") is not False
            or actual.get("outcome_inference_allowed") is not False
            or actual.get("rhetorical_fractions_converted_to_probability") is not False
        ):
            errors.append(
                {
                    "kind": "unsupported_outcome_interpretation",
                    "trigram": gua,
                    "stem": stem,
                    "door": door,
                    "god": god,
                }
            )
    return {
        "method_id": "qimen_three_deceptions_full_naming_clauses_v1",
        "source": ref["source"],
        "excerpt_sha256": ref["excerpt_sha256"],
        "printed_naming_definitions": len(ref["definitions"]),
        "retained_partial_clauses": len(ref["partial_clauses"]),
        "finite_single_stem_context_probes": probe_count,
        "finite_matched_probes": matched,
        "implementation_disagreements": errors,
        "unresolved_source_priorities": [
            {
                "id": "vol2-three-deceptions-two-factor-priority",
                "scope": "太阴与吉门同宫但无天盘三奇时，歌诀得二亦吉与正文有阴无奇不利的适用及优先",
                "source_clause_ids": [
                    "verse-two-components",
                    "prose-door-taiyin-no-wonder",
                ],
                "adopted_partial_outcome_judgment": None,
            }
        ],
        "printed_complete_chart_cases": 0,
        "independent_new_reference_cases": 0,
        "whole_section_reconciled": False,
        "whole_book_conformance_established": False,
        "real_world_efficacy_validated": False,
    }
