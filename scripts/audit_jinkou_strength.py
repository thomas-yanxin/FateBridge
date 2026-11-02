"""Compare the selected inference with uncorrected scan diagrams and judgments."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/jinkou_strength_scan_v1"
REFERENCE_FREEZE_SHA256 = (
    "644f4e0bb1145abb4bccd91f2c37c8b4440b60864e24767bd818e2adfa09207b"
)
IMPLEMENTATION = (
    "src/fatebridge/core/metaphysics/jinkou_strength.py",
    "src/fatebridge/core/metaphysics/jinkou_sources.py",
    "src/fatebridge/core/metaphysics/jinkou_patterns.py",
    "src/fatebridge/core/metaphysics/common.py",
    "src/fatebridge/core/metaphysics/jinkou.py",
    "src/fatebridge/core/metaphysics/ren_evidence.py",
    "src/fatebridge/core/output_jinkou_sources.py",
    "src/fatebridge/core/output_chinese.py",
    "src/fatebridge/services/metaphysics.py",
    "scripts/audit_jinkou_strength.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(corpus: Path = CORPUS) -> dict[str, Any]:
    if sha(corpus / "freeze.json") != REFERENCE_FREEZE_SHA256:
        raise ValueError("Frozen strength manifest identity changed")
    freeze = json.loads((corpus / "freeze.json").read_text())
    if {p.name for p in corpus.iterdir()} != set(freeze["files"]) | {"freeze.json"}:
        raise ValueError("Frozen strength inventory changed")
    for name, digest in freeze["files"].items():
        if sha(corpus / name) != digest:
            raise ValueError(f"Frozen strength source changed: {name}")
    ref: dict[str, Any] = json.loads((corpus / "reference.json").read_text())
    for name, digest in ref["reference_hashes"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"Referenced older witness changed: {name}")
    return ref


def audit() -> dict[str, Any]:
    ref = reference()
    older = json.loads(
        (ROOT / "tests/fixtures/ren_depth_v2/jinkou-internal.json").read_text()
    )
    before = {p: sha(ROOT / p) for p in IMPLEMENTATION}
    from fatebridge.core.metaphysics.jinkou_strength import internal_strength

    comparisons = []
    witness_comparisons = []
    online_comparisons = []
    for case, online in zip(ref["cases"], older["cases"], strict=True):
        rows = [
            dict(label=p, element=e)
            for p, e in zip(ref["positions"], case["elements"], strict=True)
        ]
        actual = internal_strength(rows)
        comparisons.append(
            {
                "id": case["id"],
                "god": case["god"],
                "original_pdf_pages": case["original_pdf_pages"],
                "raw_diagram_elements": case["elements"],
                "expected_anchor": case["stated_anchor"],
                "expected_god_power": case["stated_god_power"],
                "actual_anchor": actual["anchor_element"],
                "actual_candidates": actual["candidate_elements"],
                "actual_god_power": actual["powers"]["贵神"],
                "matched": actual["anchor_element"] == case["stated_anchor"]
                and actual["powers"]["贵神"] == case["stated_god_power"],
            }
        )
        witness_comparisons.append(
            {
                "id": case["id"],
                "scan_elements": case["elements"],
                "online_elements": online["elements"],
                "same_elements": case["elements"] == online["elements"],
                "same_stated_anchor": case["stated_anchor"] == online["anchor"],
                "same_stated_god_power": case["stated_god_power"]
                == online["god_power"],
            }
        )
        online_actual = internal_strength(
            [
                dict(label=p, element=e)
                for p, e in zip(ref["positions"], online["elements"], strict=True)
            ]
        )
        online_comparisons.append(
            {
                "id": case["id"],
                "matched": online_actual["anchor_element"] == online["anchor"]
                and online_actual["powers"]["贵神"] == online["god_power"],
            }
        )
    unchanged = before == {p: sha(ROOT / p) for p in IMPLEMENTATION}
    raw_matches = sum(c["matched"] for c in comparisons)
    return {
        "audit_id": "jinkou_strength_scan_v1",
        "scan_comparisons": comparisons,
        "scan_case_count": len(comparisons),
        "scan_matched_count": raw_matches,
        "scan_failures": [c for c in comparisons if not c["matched"]],
        "witness_comparisons": witness_comparisons,
        "witness_row_differences": [
            c for c in witness_comparisons if not c["same_elements"]
        ],
        "older_online_comparisons": online_comparisons,
        "older_online_matched_count": sum(c["matched"] for c in online_comparisons),
        "unique_symbolic_examples_in_section": 12,
        "new_unique_symbolic_examples": 0,
        "additional_real_world_outcomes": 0,
        "source_sha256": ref["source_sha256"],
        "reference_sha256": sha(CORPUS / "freeze.json"),
        "implementation_sha256": before,
        "implementation_unchanged_during_audit": unchanged,
        "raw_scan_excerpt_conformance": unchanged and raw_matches == len(comparisons),
        "unresolved": ref["unresolved"],
        "limits": ref["limits"],
        "classical_acceptance_passed": False,
        "goal_complete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "scan_case_count",
                    "scan_matched_count",
                    "raw_scan_excerpt_conformance",
                )
            }
        )
    )
    return 0 if report["raw_scan_excerpt_conformance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
