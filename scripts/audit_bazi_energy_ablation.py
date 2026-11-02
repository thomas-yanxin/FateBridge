"""Diagnose exposed energy receipts without proposing another strength policy."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_element_knowledge_v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit() -> dict[str, Any]:
    path = FIXTURE / "ablation-protocol.json"
    if digest(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError("Frozen ablation protocol changed")
    protocol = json.loads(path.read_text())
    source = ROOT / protocol["input_path"]
    if digest(source) != protocol["input_sha256"]:
        raise ValueError("Frozen corpus receipt changed")
    # This diagnostic consumes frozen corpus receipts, not the live strength
    # kernel. Preserve the original kernel identity against its sealed source.
    original_kernel = (
        ROOT
        / "tests/fixtures/bazi_birth_seconds_v1/before/src/fatebridge/core/strength.py"
    )
    if digest(original_kernel) != protocol["strength_source_sha256"]:
        raise ValueError("Original strength source changed; do not change diagnosis")
    corpus = json.loads(gzip.decompress(source.read_bytes()))
    rows = []
    for group, result in corpus["groups"].items():
        for original in result["rows"]:
            a = original["assessment"]
            own = original["components"]["own_element"]
            parent = original["components"]["parent_element"]
            energies = a["effective_elements_unrounded"]
            arms = {}
            for arm in protocol["arms"]:
                no_season = arm in {
                    "without_seasonal_multiplier",
                    "without_parent_support_or_seasonal_multiplier",
                }
                no_parent = arm in {
                    "without_parent_support",
                    "without_parent_support_or_seasonal_multiplier",
                }
                values = {}
                for element, energy in energies.items():
                    factor = (
                        1
                        + (a["seasonal_factors"][a["seasonal_phases"][element]] - 1)
                        * a["parameters"]["seasonal_spread"]
                    )
                    if not math.isfinite(factor) or factor <= 0:
                        raise ValueError("Nonpositive or nonfinite seasonal factor")
                    values[element] = energy / factor if no_season else energy
                support = values[own] + (0 if no_parent else values[parent])
                weaken = math.fsum(
                    value for e, value in values.items() if e not in {own, parent}
                )
                share = support / (support + weaken)
                parameters = a["parameters"]
                label = (
                    "强"
                    if share > parameters["strong_share"]
                    else "弱" if share < parameters["weak_share"] else "中和"
                )
                arms[arm] = {
                    "arithmetic_support": support,
                    "arithmetic_weaken": weaken,
                    "arithmetic_share": share,
                    "numerical_ablation_grade": label,
                    "not_a_recomputed_final_strength": True,
                }
            baseline = arms["baseline_weighted"]
            if not math.isclose(
                baseline["arithmetic_share"],
                a["support_share"],
                abs_tol=1e-12,
                rel_tol=1e-12,
            ):
                raise ValueError("Baseline does not reconcile the same-run receipt")
            if (
                baseline["numerical_ablation_grade"]
                != a["structural_decision"]["numerical_label"]
            ):
                raise ValueError("Baseline arithmetic grade changed")
            rows.append(
                {
                    "group": group,
                    "id": original["id"],
                    "original": original,
                    "arms": arms,
                }
            )
    summaries = {}
    for arm in protocol["arms"]:
        known = [r for r in rows if r["original"]["expected_strength"] is not None]

        def matches(row: dict[str, Any], name: str) -> bool:
            return bool(
                row["arms"][name]["numerical_ablation_grade"]
                == row["original"]["expected_strength"]
            )

        summaries[arm] = {
            "known_records": len(known),
            "unknown_records_preserved": len(rows) - len(known),
            "arithmetic_only_matches_not_final_model_acceptance": sum(
                matches(r, arm) for r in known
            ),
            "new_matches_vs_baseline_arithmetic": [
                [r["group"], r["id"]]
                for r in known
                if matches(r, arm) and not matches(r, "baseline_weighted")
            ],
            "new_mismatches_vs_baseline_arithmetic": [
                [r["group"], r["id"]]
                for r in known
                if not matches(r, arm) and matches(r, "baseline_weighted")
            ],
            "changed_unknown_arithmetic_grades": [
                [r["group"], r["id"]]
                for r in rows
                if r["original"]["expected_strength"] is None
                and r["arms"][arm]["numerical_ablation_grade"]
                != r["arms"]["baseline_weighted"]["numerical_ablation_grade"]
            ],
        }
    return {
        "protocol_sha256": digest(path),
        "input_sha256": digest(source),
        "runner_sha256": digest(Path(__file__)),
        "strength_source_sha256": digest(original_kernel),
        "scope": protocol["scope"],
        "record_count": len(rows),
        "rows": rows,
        "summaries": summaries,
        "focus": next(r for r in rows if r["id"] == protocol["focus_case"]),
        "original_local_and_negative_claims_unchanged": corpus[
            "local_and_negative_claims"
        ],
        "source_labels_changed": False,
        "production_policy_changed": False,
        "new_independent_cases": 0,
        "adopted": False,
        "full_goal_complete": False,
        "real_world_efficacy": "not_tested",
        "overall_score": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite first diagnostic")
    result = audit()
    data = (
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as handle:
        handle.write(
            gzip.compress(data, mtime=0) if args.output.suffix == ".gz" else data
        )
    print(
        json.dumps(
            {
                "records": result["record_count"],
                "adopted": False,
                "focus_arms": result["focus"]["arms"],
                "summary": result["summaries"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
