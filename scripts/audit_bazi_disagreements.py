"""Retain every original disagreement and reconcile its actual energy receipt."""

from __future__ import annotations

import argparse
import json
import math
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.utils.data import GENERATION_CYCLE, STEM_ELEMENTS

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "tests/fixtures/bazi_disagreement_review_v1/review.json"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def budget_components(assessment: dict[str, Any], day_stem: str) -> dict[str, Any]:
    """Sum supplied unrounded receipts; never calculate another strength label."""
    values: dict[str, list[float]] = {e.value: [] for e in GENERATION_CYCLE}
    for row in assessment["hidden_stem_ledger"]:
        values[row["element"]].append(row["engineering_energy"])
    for row in assessment["combination_contributions"]:
        phase = assessment["seasonal_phases"][row["element"]]
        factor = (
            1
            + (assessment["seasonal_factors"][phase] - 1)
            * assessment["parameters"]["seasonal_spread"]
        )
        values[row["element"]].append(row["mass"] * factor)
    for row in assessment["stem_energy_accounting"]["ledger"]:
        values[row["effective_element"]].append(row["energy"])
    totals = {key: math.fsum(parts) for key, parts in values.items()}
    own = STEM_ELEMENTS[day_stem][0]
    parent = next(e for e, child in GENERATION_CYCLE.items() if child == own)
    support = totals[own.value] + totals[parent.value]
    weaken = math.fsum(
        v for e, v in totals.items() if e not in {own.value, parent.value}
    )
    for actual, expected in [
        (support, assessment["support_strength"]),
        (weaken, assessment["weaken_strength"]),
    ]:
        if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("Supplied unrounded energy receipt does not reconcile")
    total = support + weaken
    return {
        "own_element": own.value,
        "parent_element": parent.value,
        "own_energy": totals[own.value],
        "parent_energy": totals[parent.value],
        "own_fraction": totals[own.value] / total if total else None,
        "parent_fraction": totals[parent.value] / total if total else None,
        "combined_support_fraction": support / total if total else None,
        "reconciles_supplied_support_and_weaken": True,
        "quantity_kind": "engineering_energy_not_classical_force_or_probability",
    }


def audit(replay: Path) -> dict[str, Any]:
    if digest(REVIEW) != REVIEW.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen review changed")
    review = json.loads(REVIEW.read_text())
    if digest(ROOT / review["baseline_replay"]) != review["baseline_replay_sha256"]:
        raise ValueError("Original disagreement baseline changed")
    for relative, expected in review["source_annotation_hashes"].items():
        if digest(ROOT / relative) != expected:
            raise ValueError("Original source annotation changed: " + relative)
    current = json.loads(replay.read_text())
    if current["source_drift"]:
        raise ValueError("Public replay source drifted")
    rows = []
    for source in review["cases"]:
        candidates = [
            c
            for c in current["groups"][source["baseline_group"]]["rows"]
            if c["id"] == source["id"]
        ]
        if len(candidates) != 1:
            raise ValueError("Original disagreement disappeared: " + source["id"])
        row = candidates[0]
        if (
            row["pillars"] != source["pillars"]
            or row["expected_strength"] != source["expected_strength"]
        ):
            raise ValueError("Original disagreement input or source label changed")
        if row["matches"] is not (row["actual_strength"] == row["expected_strength"]):
            raise ValueError("Replay match flag disagrees with its supplied labels")
        rows.append(
            {
                "id": source["id"],
                "pillars": source["pillars"],
                "expected_strength": source["expected_strength"],
                "actual_strength": row["actual_strength"],
                "status": (
                    "resolved_under_original_label"
                    if row["matches"] is True
                    else "unresolved"
                ),
                "method_id": row["method_id"],
                "components": budget_components(
                    row["assessment"], row["pillars"][2][0]
                ),
                "actual_decision": row["assessment"]["structural_decision"],
                "actual_relations": row["assessment"]["relations"],
                "source_reading_kind": source["source_reading_kind"],
                "source_review": source["source_review"],
                "mechanistic_hypothesis": source["mechanistic_hypothesis"],
                "next_required_validation": source["next_required_validation"],
            }
        )
    anchors = {tuple(c["pillars"]) for c in rows}
    return {
        "review_sha256": digest(REVIEW),
        "replay_sha256": digest(replay),
        "original_disagreements_retained": len(rows),
        "unresolved": [r["id"] for r in rows if r["status"] == "unresolved"],
        "resolved_under_original_label": [
            r["id"] for r in rows if r["status"] != "unresolved"
        ],
        "additional_current_disagreements": [
            m
            for m in current["distinct_mismatches"]
            if tuple(m["pillars"]) not in anchors
        ],
        "rows": rows,
        "classical_acceptance_passed": False,
        "authority_certified": False,
        "overall_score": None,
        "scope": "Nineteen original anchors remain even after repair; engineering receipt sums are not classical truth or semantic-model acceptance. Review is same-developer source reading, not independent expert adjudication. No old label, failed candidate or adoption threshold is changed.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve the earlier review")
    result = audit(args.replay)
    with args.output.open("x") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(
        json.dumps(
            {
                "retained": len(result["rows"]),
                "unresolved": len(result["unresolved"]),
                "resolved": result["resolved_under_original_label"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
