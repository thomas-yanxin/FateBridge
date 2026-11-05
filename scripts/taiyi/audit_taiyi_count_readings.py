"""Audit source-specific count catalogues without inventing one harmony rank."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_counts import (
    count_labels,
    count_reading,
    source_profiles,
)

CORPUS = Path(__file__).resolve().parents[2] / "tests/fixtures/taiyi_jinjing_v16"
MANIFEST_SHA256 = "baa90a3cdc40bbb8972f865c4edf1efe48e138bb4620d9ae00d2e9567c870b4c"


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    corpus = corpus.resolve()
    raw = (corpus / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("须保留实施前完整1至40域、五个源读法及所有未决材料")
    manifest = json.loads(raw)
    for item in manifest["source_files"] + manifest["prior_source_references"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("来源指纹不符：" + item["file"])
    cases = json.loads((corpus / "numeric-cases.json").read_text())["cases"]
    if [c["count"] for c in cases] != list(range(1, 41)):
        raise ValueError("不能删去15/25/35、10或有源差异的数值")
    catalog = json.loads((corpus / "source-profiles.json").read_text())
    profiles = catalog["profiles"]
    if profiles != source_profiles():
        raise ValueError("运行分源目录与独立冻结转录不一致")
    checks = []
    for c in cases:
        r = count_reading(c["count"])
        checks.append(
            {
                "count": c["count"],
                "checks": {
                    "labels": count_labels(c["count"]) == c["expected_labels"],
                    "missing": r["missing_labels"] == c["expected_missing"],
                    "fullness_inference": r["three_talents_inferred"]
                    is c["expected_fullness_inference"],
                    "duse": r["duse"] is c["expected_duse"],
                    "length": r["length_label"] == c["expected_length"],
                },
            }
        )
    differences = []
    gaps = []
    for n in range(1, 41):
        r = count_reading(n)
        if r["literal_rank_status"] == "different_source_ranks":
            differences.append({"count": n, "memberships": r["source_memberships"]})
        elif r["literal_rank_status"] == "partial_listing_not_unified":
            gaps.append(n)
    return {
        "completion_claim": False,
        "source_numeric_domain": 40,
        "source_profiles": len(profiles),
        "catalogue_transcriptions_match": profiles == source_profiles(),
        "source_and_inference_checks_separate": checks,
        "all_selected_numeric_and_inference_checks_passed": all(
            all(r["checks"].values()) for r in checks
        ),
        "literal_rank_differences": differences,
        "partial_listings_not_negatives": gaps,
        "source_unadjudicated_readings": [
            {"profile_id": p["id"], **r}
            for p in profiles
            for key in ("unadjudicated_readings", "out_of_range_readings")
            for r in p.get(key, [])
        ],
        "whole_classic_acceptance_passed": False,
        "scope": "40个数的源列表/推导属性和五条文献读法是分类验收，不是40历史课例；和数等级与位置配数分开，原未列/缩写/越界转录不删、不计通过。",
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
