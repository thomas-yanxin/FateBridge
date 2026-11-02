"""Audit all sixteen spirits in the eight directional gate sectors."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_gates import SECTORS

CORPUS = Path(__file__).resolve().parents[1] / "tests/fixtures/taiyi_gate_sectors_v1"


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    manifest = json.loads((corpus / "manifest.json").read_text())
    if {r["file"] for r in manifest["source_files"]} != {"sectors.json"}:
        raise ValueError("八门方位完整来源不得删除")
    for item in manifest["source_files"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("八门方位来源指纹不符")
    case = json.loads((corpus / "sectors.json").read_text())
    if (
        len(case["cases"]) != 16
        or {r["spirit"] for r in case["cases"]}
        != set("子丑艮寅卯辰巽巳午未坤申酉戌乾亥")
        or manifest["required_observations"] != 16
    ):
        raise ValueError("必须核全部16神，不可只测通过的后半间神")
    differences = [
        {**r, "computed_sector": SECTORS[r["spirit"]]}
        for r in case["cases"]
        if r["sector"] != SECTORS[r["spirit"]]
    ]
    return {
        "completion_claim": False,
        "required_observations": 16,
        "matching_observations": 16 - len(differences),
        "disagreements": differences,
        "geometry_acceptance_passed": not differences,
        "sources": case["sources"],
        "scope": case["scope"],
        "inference_scope": case["inference_scope"],
        "whole_book_conformance": "not_established",
        "real_world_efficacy": "not_tested",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw)
    print(raw, end="")
    return 0 if report["geometry_acceptance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
