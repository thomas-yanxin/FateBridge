"""Audit literal center notes separately from unknown-aware condition logic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_conditions import (
    conjunction,
    five_general_conditions,
)
from fatebridge.core.metaphysics.taiyi_year import (
    PALACES,
    cyclic_core,
    structural_patterns,
)

CORPUS = Path(__file__).resolve().parents[2] / "tests/fixtures/taiyi_jinjing_v15"
MANIFEST_SHA256 = "d0f318e57e9ed07d86e2bc2e694144bc24378e5e4f415baff47c98f792652f5d"
FACSIMILE_SHA256 = "095b8052699c198c89cb8a539a5c392d1167c3b67e382978a11bfb4ed0f8c501"


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    corpus = corpus.resolve()
    raw = (corpus / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("须保留实施前的4条中位原注和完整合成真值表")
    facsimile = (corpus / "facsimile-check.json").read_bytes()
    if hashlib.sha256(facsimile).hexdigest() != FACSIMILE_SHA256:
        raise ValueError("补核书影清单指纹不符，不得改实施前预期")
    images = json.loads(facsimile)["source_files"]
    for item in images:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("补核书影指纹不符：" + item["file"])
    manifest = json.loads(raw)
    for item in manifest["source_files"] + manifest["prior_source_references"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError(f"来源指纹不符：{item['file']}")
    notes = json.loads((corpus / "center-notes.json").read_text())["records"]
    if [n["ju"] for n in notes] != [7, 32, 35, 36]:
        raise ValueError("全部4条原注必须纳入")
    rows = []
    for note in notes:
        c = cyclic_core(note["ju"])
        a = five_general_conditions(structural_patterns(c), core=c)
        camp = note["camp"]
        rows.append(
            {
                "ju": note["ju"],
                "count_source": note["expected_count"],
                "count_computed": c[camp + "_count"],
                "count_matches": c[camp + "_count"] == note["expected_count"],
                "center_source": note["source_center_reading"],
                "both_generals_at_source_center": all(
                    PALACES[c[camp + f]] == note["expected_center_palace"]
                    for f in ("_general", "_vice_general")
                ),
                "source_non_dispatch_reading": note["source_dispatch_reading"],
                "source_quote": note["source_quote"],
                "source": note["source_url"],
                "source_word_is_not_new_guan_rule": True,
                "unassessed_same_camp_relations": a["five_generals"]["clauses"][2][
                    "unassessed"
                ],
                "conditions_satisfied": a["five_generals"]["conditions_satisfied"],
                "annotation_absence_is_negative": False,
            }
        )
    truth = json.loads((corpus / "truth-table.json").read_text())
    cases = truth["two_inputs"] + truth["three_inputs"]
    return {
        "completion_claim": False,
        "selected_source_notes": 4,
        "required_count_observations": 4,
        "matching_count_observations": sum(r["count_matches"] for r in rows),
        "required_center_observations": 4,
        "matching_center_observations": sum(
            r["both_generals_at_source_center"] for r in rows
        ),
        "literal_non_dispatch_readings_retained": len(rows),
        "supplementary_facsimile_images_verified": len(images),
        "initial_expectations_unchanged_after_facsimile_check": True,
        "synthetic_conjunction_cases": len(cases),
        "synthetic_conjunction_matches": sum(
            conjunction(*r["values"]) is r["expected"] for r in cases
        ),
        "same_camp_guan_adjudicated": False,
        "whole_classic_acceptance_passed": False,
        "rows": rows,
        "scope": "4算数、4中位语义、4个不出原词与36个合成逻辑状态分别报告；非4完整盘或36古例，未把中五直接定义为关或新增五将第四项。",
    }
