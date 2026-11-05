"""Evaluate the current registered source corpus without historical kernels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fatebridge.core import source_annotations
from fatebridge.services.source_comparison import calculate_bazi_source_compare


def compare_direction(
    result: dict[str, Any], annotation: dict[str, Any]
) -> dict[str, Any]:
    """An explicit tie contradicts a strict source direction; absence is unknown."""
    pair = set(annotation["positions"])
    events = [
        event
        for event in result["relations"]
        if event["kind"] == "六冲" and set(event["positions"]) == pair
    ]
    if len(events) != 1:
        return {"status": "not_comparable", "matches": None}
    event = events[0]
    values = event.get("root_multipliers")
    if not values or set(values) != pair:
        return {
            "status": "not_comparable",
            "event_status": event["status"],
            "matches": None,
        }
    tied = len(set(values.values())) == 1
    weaker = None if tied else min(values, key=values.__getitem__)
    return {
        "status": "compared",
        "weaker_position": weaker,
        "model_direction": "tied" if tied else "unequal",
        "matches": weaker == annotation["weaker_position"],
        "root_multipliers": values,
    }


def compare_application(
    result: dict[str, Any], annotation: dict[str, Any]
) -> dict[str, Any]:
    events = [
        e
        for e in result["relations"]
        if e["kind"] == "六冲" and set(e["positions"]) == set(annotation["positions"])
    ]
    if len(events) != 1 or events[0]["status"] not in {
        "active",
        "resolved_by_combination",
    }:
        return {"matches": None, "status": "not_comparable"}
    event = events[0]
    applied = event["status"] == "active"
    return {
        "matches": applied == (annotation["expected_clash_effect"] == "applied"),
        "status": "compared_application_flag_only",
        "model_event_status": event["status"],
        "root_damage_magnitude_adjudicated": False,
        "source_reason_adjudicated": False,
    }


def audit() -> dict[str, Any]:
    """Report current matches, unknowns and source conflicts separately."""
    path = (
        Path(source_annotations.__file__).resolve().parents[1]
        / "data/reference/bazi-source-annotations.json"
    )
    data = json.loads(path.read_text())
    # The public reader verifies the complete current documentary dataset.
    source_annotations._index()
    rows = []
    lookup = {}
    disagreements: dict[tuple[str, ...], list[dict[str, object]]] = {}
    for record in data["records"]:
        result = calculate_bazi_source_compare(*record["pillars"])
        if "error" in result:
            raise ValueError(result["error"])
        current = result["current_calculation"]
        expected = record["retained_strength_annotation"]
        row = {
            "group": record["group"],
            "id": record["case_id"],
            "pillars": record["pillars"],
            "expected_strength": expected,
            "actual_strength": current["strength_level"],
            "matches": (
                None if expected is None else current["strength_level"] == expected
            ),
            "assessment": current["assessment"],
        }
        rows.append(row)
        lookup[record["reference_id"]] = row
        if row["matches"] is False:
            disagreements.setdefault(tuple(row["pillars"]), []).append(
                {
                    "group": row["group"],
                    "id": row["id"],
                    "expected_strength": expected,
                    "actual_strength": row["actual_strength"],
                }
            )
    claims = []
    for source_claim in data["local_comparison_claims"]:
        annotation = source_claim["annotation"]
        key = source_claim["group"] + ":" + annotation["case_id"]
        row = lookup[key]
        if source_claim["kind"] == "local_clash_labels":
            compared = compare_direction(row["assessment"], annotation)
        elif source_claim["kind"] == "clash_application_conditions":
            compared = compare_application(row["assessment"], annotation)
        else:
            compared = {
                "status": "forbidden_body_labels_only",
                "matches": row["actual_strength"]
                not in annotation["forbidden_strengths"],
            }
        claims.append({**source_claim, **compared})
    constraints = [
        {
            "constraint_id": constraint["constraint_id"],
            "reference_id": constraint["reference_id"],
            "forbidden_strengths": constraint["forbidden_strengths"],
            "actual_strength": lookup[constraint["reference_id"]]["actual_strength"],
            "matches": lookup[constraint["reference_id"]]["actual_strength"]
            not in constraint["forbidden_strengths"],
        }
        for constraint in data["strength_constraints"]
    ]
    return {
        "current_strength_method_id": rows[0]["assessment"]["method_id"],
        "record_count": len(rows),
        "distinct_inputs": len({tuple(row["pillars"]) for row in rows}),
        "unknown_strength_records": sum(
            row["expected_strength"] is None for row in rows
        ),
        "all_distinct_disagreements": [
            {"pillars": list(p), "source_observations": observations}
            for p, observations in disagreements.items()
        ],
        "local_and_negative_claims": claims,
        "bounded_strength_constraints": constraints,
        "bounded_strength_constraint_violations": [
            c for c in constraints if not c["matches"]
        ],
        "rows": rows,
        "classical_acceptance_passed": False,
        "independent_external_review": "not_completed",
        "new_independent_cases": 0,
        "reality_prediction_efficacy": "not_tested",
        "overall_score": None,
        "scope": "Current exposed source records; source groups overlap. Unknown source grades are not matches. Numerical policy is not a full classical-force judgment, independent expert certification or real-world prediction.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require-full",
        action="store_true",
        help="专业验收未通过时退出1；保留全部原记录及集合约束",
    )
    args = parser.parse_args()
    result = audit()
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "records": result["record_count"],
                "distinct_inputs": result["distinct_inputs"],
                "unknown": result["unknown_strength_records"],
                "disagreements": len(result["all_distinct_disagreements"]),
                "classical_acceptance_passed": False,
            },
            ensure_ascii=False,
        )
    )
    return 1 if args.require_full and not result["classical_acceptance_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
