"""Keep explicit rule observations distinct from unadjudicated text readings."""

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.qimen_tombs import describe_wonder_tombs, palace_wonder_tombs


def audit_wonder_tomb_clauses(directory: Path) -> dict[str, Any]:
    ref = json.loads((directory / "sources-and-tomb-clauses.json").read_text())
    if ref["excerpt_file"] != "siku-pages32-33.pdf" or ref["original_pdf_pages"] != [
        32,
        33,
    ]:
        raise ValueError("须保留第32至33页完整上下文")
    if (
        hashlib.sha256((directory / ref["excerpt_file"]).read_bytes()).hexdigest()
        != ref["excerpt_sha256"]
    ):
        raise ValueError("三奇入墓异文参考指纹不一致")
    clauses = ref["clauses"]
    if set(clauses) != {
        "wangzhang_enumeration",
        "opening_sentence_literal_candidate",
    } or any(set(c["mapping"]) != set("乙丙丁") for c in clauses.values()):
        raise ValueError("须保留明确列举及未采纳句读的全部三奇")
    if ref["unresolved_priority_stems"] != ["乙", "丁"]:
        raise ValueError("乙、丁两项原文释读及优先关系仍须保留未通过")
    selected = clauses["wangzhang_enumeration"]["mapping"]
    candidate = clauses["opening_sentence_literal_candidate"]["mapping"]
    profile = describe_wonder_tombs()
    disagreements = []
    if (
        profile["selected_stem_trigrams"] != selected
        or profile["unadopted_literal_candidate"]["stem_trigrams"] != candidate
    ):
        disagreements.append({"field": "source_clause_mappings", "actual": profile})
    for stem in "乙丙丁":
        for trigram in "坎坤震巽乾兑艮离":
            result = palace_wonder_tombs(trigram, [stem])
            if (
                result["selected_matched_stems"]
                != ([stem] if selected[stem] == trigram else [])
                or result["unadopted_literal_candidate_matched_stems"]
                != ([stem] if candidate[stem] == trigram else [])
                or result["candidate_adopted"]
            ):
                disagreements.append(
                    {"stem": stem, "trigram": trigram, "actual": result}
                )
    return {
        "selected_explicit_rule_cells": 3,
        "unadopted_literal_candidate_cells": 3,
        "finite_stem_palace_comparisons": 24,
        "independent_original_chart_examples_added": 0,
        "implementation_disagreements": disagreements,
        "unresolved_source_priorities": [
            {
                "case_id": f"vol2-wonder-tomb-{s}-reading-priority",
                "heaven_stem": s,
                "selected_named_enumeration": selected[s],
                "unadopted_literal_candidate": candidate[s],
                "status": "literal_reading_and_source_priority_unresolved",
                "candidate_adopted": False,
            }
            for s in ref["unresolved_priority_stems"]
        ],
        "source_reading_adjudicated": False,
        "whole_book_conformance_established": False,
        "real_world_efficacy": "not_tested",
    }
