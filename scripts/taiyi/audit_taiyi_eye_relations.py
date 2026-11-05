"""Keep numerical source conformance separate from selected pair annotations.

The old oracle and its disagreements are untouched. These eight cyclic
examples are neither eight historical events nor a complete 72-ju audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_eye_relations import PROFILE
from fatebridge.core.metaphysics.taiyi_year import cyclic_core, structural_patterns

CORPUS = Path(__file__).resolve().parents[2] / "tests/fixtures/taiyi_jinjing_v13"
MANIFEST_SHA256 = "4ece71115af3ee5da8148d755fabaeca835b78a9b41b06b68b8f745c3746c9c9"
REQUIRED_JU = (1, 2, 7, 11, 13, 15, 18, 27)
NUMERIC_FIELDS = {
    "taiyi_number",
    "taiyi_palace",
    "wenchang_palace",
    "jishen",
    "shiji",
    "main_count",
    "main_general",
    "main_vice_general",
    "guest_count",
    "guest_general",
    "guest_vice_general",
}
GENERAL_LABELS = {
    "main_general": "主大将",
    "main_vice_general": "主参将",
    "guest_general": "客大将",
    "guest_vice_general": "客参将",
}


def pair_key(pattern: dict[str, Any]) -> tuple[str, str, str]:
    """Resolve the actual target field, not a substring in a rendered meaning."""
    if pattern["name"] == "关":
        return "关", pattern["subject"], "文昌"
    field = pattern["basis"][1]["field"].removeprefix("core_board.")
    return "掩", "始击", GENERAL_LABELS[field]


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    corpus = corpus.resolve()
    manifest_bytes = (corpus / "manifest.json").read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256:
        raise ValueError("须保留实施前冻结的完整8局清单，不重建分母")
    manifest = json.loads(manifest_bytes)
    for item in manifest["source_files"] + manifest["prior_source_references"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError(f"来源文件指纹不符：{item['file']}")
    cases = json.loads((corpus / "eye-general-cases.json").read_text())["cases"]
    if tuple(c["ju"] for c in cases) != REQUIRED_JU or any(c["yin"] for c in cases):
        raise ValueError("须保留8个指定阳局，不以同相位新日期替换为新古例")
    rows = []
    for case in cases:
        if set(case["expected"]) != NUMERIC_FIELDS:
            raise ValueError("每局须保留完整11项数值与位置")
        core = cyclic_core(case["ju"])
        observations = [
            {
                "field": field,
                "source_value": value,
                "computed_value": core[field],
                "matches": core[field] == value,
            }
            for field, value in case["expected"].items()
        ]
        found = {
            pair_key(p)
            for p in structural_patterns(core)
            if p.get("relation_profile") == PROFILE
        }
        relations = [
            {**r, "matches": (r["name"], r["subject"], r["other"]) in found}
            for r in case["stated_relations"]
        ]
        rows.append(
            {
                "id": case["id"],
                "ju": case["ju"],
                "numeric_observations": observations,
                "stated_relations": relations,
                "numeric_match": all(r["matches"] for r in observations),
                "stated_pairs_match": all(r["matches"] for r in relations),
                "annotation_absence_is_negative": False,
            }
        )
    if sum(len(c["stated_relations"]) for c in cases) != 12:
        raise ValueError("须保留全部12条选定原文明载关系")
    return {
        "completion_claim": False,
        "profile": PROFILE,
        "selected_cyclic_charts": len(rows),
        "required_numeric_observations": 88,
        "matching_numeric_observations": sum(
            r["matches"] for row in rows for r in row["numeric_observations"]
        ),
        "required_stated_relations": 12,
        "matching_stated_relations": sum(
            r["matches"] for row in rows for r in row["stated_relations"]
        ),
        "selected_numerical_and_pair_conformance_passed": all(
            r["numeric_match"] and r["stated_pairs_match"] for r in rows
        ),
        "rows": rows,
        "whole_72_ju_annotation_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "historical_calendar_reconstructed": False,
        "unadjudicated": [
            "其余局注全部断语与阴遁注例",
            "同阵大小将中五同宫互关、二目互关和版本范围",
            "四郭固杜全部或段与挟闭",
            "全部11项原算表分歧与既有未决校勘",
            "完整历法及真实模型解释盲测",
        ],
        "count_policy": "88宫数和12对关系分列，8局来自同一循环课注；144循环盘是软件影响对照，不是新古例或现实预测验证。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(text)
    else:
        print(text, end="")
    return 0 if report["whole_classic_acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
