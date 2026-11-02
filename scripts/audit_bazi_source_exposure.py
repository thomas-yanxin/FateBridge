"""Correct source exposure metadata without replacing first results or labels."""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = "tests/fixtures/bazi_clash_power_v3/reference.json"
FIRST = "docs/validation/bazi-clash-power-first-v3.json"
ORDER = ("year", "month", "day", "hour")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def frozen(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Original frozen source/report changed")
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def key(raw: Any) -> tuple[str, ...]:
    return tuple(raw[k] for k in ORDER) if isinstance(raw, dict) else tuple(raw)


def audit() -> dict[str, Any]:
    reference, first = frozen(REFERENCE), frozen(FIRST)
    sources = dict(reference["overlap_source_hashes"])
    sources.update(
        {
            g["source"]: g["source_sha256"]
            for g in first["groups"].values()
            if g["source"] != REFERENCE
        }
    )
    prior: dict[tuple[str, ...], list[dict[str, Any]]] = {}

    def visit(obj: Any, source: str) -> None:
        if isinstance(obj, dict):
            raw = obj.get("pillars")
            if isinstance(raw, (list, dict)) and len(raw) == 4:
                values = key(raw)
                if all(isinstance(v, str) and len(v) == 2 for v in values):
                    prior.setdefault(values, []).append(
                        {"source": source, "id": obj.get("id")}
                    )
            for value in obj.values():
                visit(value, source)
        elif isinstance(obj, list):
            for value in obj:
                visit(value, source)

    for relative, expected in sources.items():
        path = ROOT / relative
        if digest(path) != expected:
            raise ValueError("Exposed input changed: " + relative)
        visit(json.loads(path.read_text()), relative)
    rows = []
    for case in reference["cases"]:
        overlaps = prior.get(key(case["pillars"]), [])
        eligible = case["source_unit"] != "干支总论尾例" and not overlaps
        rows.append(
            {
                "id": case["id"],
                "pillars": case["pillars"],
                "expected_strength": case["expected_strength"],
                "previous_chapter_tail": case["source_unit"] == "干支总论尾例",
                "all_prior_exact_overlaps": overlaps,
                "first_recorded_fresh_gate_eligible": case["fresh_gate_eligible"],
                "corrected_fresh_gate_eligible": eligible,
            }
        )
    fresh = [r for r in rows if r["corrected_fresh_gate_eligible"]]
    return {
        "scope": "Post-first metadata correction. Original annotations, unknowns, candidate bytes and all numerical results remain unchanged. Not a new blind test or accuracy improvement.",
        "reference_sha256": digest(ROOT / REFERENCE),
        "first_report_sha256": digest(ROOT / FIRST),
        "exposed_source_hashes": sources,
        "reason": "Initial directory glob omitted standalone bazi-strength-reference.json. Explicit sources from the already-frozen first comparison restore the21-case exposed group.",
        "rows": rows,
        "new_chapter_cases": sum(not r["previous_chapter_tail"] for r in rows),
        "nonoverlap_new_chapter_cases": len(fresh),
        "nonoverlap_adjudicated": sum(
            r["expected_strength"] is not None for r in fresh
        ),
        "nonoverlap_unknown": sum(r["expected_strength"] is None for r in fresh),
        "corrected_case_ids": [
            r["id"]
            for r in rows
            if r["first_recorded_fresh_gate_eligible"]
            != r["corrected_fresh_gate_eligible"]
        ],
        "all_numeric_results_unchanged": True,
        "candidate_adopted": False,
        "overall_score": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve the earlier exposure record")
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"rows", "exposed_source_hashes"}
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
