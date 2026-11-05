"""Audit all selected main-side opposition notes, retaining wording conflicts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_oppositions import opposition_assessment
from fatebridge.core.metaphysics.taiyi_year import cyclic_core

CORPUS = Path(__file__).resolve().parents[2] / "tests/fixtures/taiyi_jinjing_v14"
MANIFEST_SHA256 = "806d20549cc96bd17ec92a110f7566643500d081350fd4f8faa3e44e542ac5b7"
REQUIRED_JU = (13, 16, 21, 25, 34, 45, 48, 53, 54, 58, 59, 60)


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    corpus = corpus.resolve()
    raw = (corpus / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("须保留实施前的完整12条注记清单")
    manifest = json.loads(raw)
    for item in manifest["source_files"] + manifest["prior_source_references"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError(f"来源指纹不符：{item['file']}")
    notes = json.loads((corpus / "opposition-notes.json").read_text())["records"]
    if tuple(row["ju"] for row in notes) != REQUIRED_JU:
        raise ValueError("不能删去原注、异称或阳53的附带外迫")
    results = []
    for note in notes:
        core = cyclic_core(note["ju"])
        row = next(
            r
            for r in opposition_assessment(core)["entries"]
            if r["field"] == note["general_field"]
        )
        results.append(
            {
                "ju": note["ju"],
                "subject": row["subject"],
                "taiyi_number_source": note["expected_taiyi_number"],
                "taiyi_number_computed": core["taiyi_number"],
                "general_number_source": note["expected_general_number"],
                "general_number_computed": core[note["general_field"]],
                "numeric_matches": [
                    core["taiyi_number"] == note["expected_taiyi_number"],
                    core[note["general_field"]] == note["expected_general_number"],
                ],
                "is_opposite": row["is_opposite"],
                "source_name": note["source_name"],
                "source_reading": note["source_reading"],
                "source_comparison": row["source_comparison"],
            }
        )
    extra = [
        r for row in results for r in row["source_comparison"]["additional_readings"]
    ]
    if len(extra) != 1 or extra[0]["source_name"] != "外迫":
        raise ValueError("阳53的外迫反例必须保留")
    return {
        "completion_claim": False,
        "selected_annotation_records": 12,
        "required_numeric_observations": 24,
        "matching_numeric_observations": sum(
            v for r in results for v in r["numeric_matches"]
        ),
        "required_opposition_observations": 12,
        "matching_opposition_observations": sum(
            r["is_opposite"] is True for r in results
        ),
        "source_name_counts": {
            name: sum(r["source_name"] == name for r in results)
            for name in ("格", "對")
        },
        "names_unified": False,
        "additional_reading_observations": extra,
        "additional_reading_disagreements": sum(
            r["matches_selected_taiyi_reference"] is False for r in extra
        ),
        "selected_geometry_passed": all(
            all(r["numeric_matches"]) and r["is_opposite"] is True for r in results
        ),
        "whole_selected_annotation_conformance_passed": False,
        "whole_classic_acceptance_passed": False,
        "rows": results,
        "scope": "24宫数与12对宫几何分列；格10/對2是原词统计，不算名称预测命中率。阳53附带外迫的所核不符保留，其他参照未裁定。12循环注记不是12完整盘或12历史应验。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0 if report["whole_classic_acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
