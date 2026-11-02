"""Compare every frozen historical candidate; retain prior failed source audit."""

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def pinned(raw: bytes, expected: str) -> Any:
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Input does not match required digest")
    return json.loads(raw)


def compare_all(
    plan_raw: bytes,
    predictions: dict[str, Any],
    prior_raw: bytes,
    trees_raw: bytes,
    expected_plan_sha: str,
) -> dict[str, Any]:
    plan = pinned(plan_raw, expected_plan_sha)
    prior = pinned(prior_raw, plan["prior_source_audit_sha256"])
    trees = pinned(trees_raw, plan["source_trees_sha256"])
    events = prior["search"]["events"]
    event_map = {e["event_id"]: e for e in plan["events"]}
    models = [m["id"] for m in plan["models"]]
    shifts = plan["clock_hypotheses_seconds_local_minus_common_ut1"]
    required = {(m, e) for m in models for e in event_map}
    keys = [(r["model"], r["event_id"]) for r in predictions["rows"]]
    source_complete = (
        prior["search"]["finite_adaptive_search_complete"]
        and prior["all_text_properties_bound"]
        and len(events) == len(event_map) == prior["search"]["required_event_count"]
        and {e["event_id"] for e in events} == set(event_map)
        and all(e["status"] == "bounded_adjacent_minute_transition" for e in events)
    )
    well_formed = True
    for row in predictions["rows"]:
        event = event_map.get(row["event_id"])
        clocks = row["clock_hypotheses"]
        root = row["root_jd_tt"]
        lo, hi = row["bracket_jd_tt"]
        well_formed = bool(
            well_formed
            and event is not None
            and row["body"] == event["body"]
            and row["boundary_longitude"] == event["boundary_longitude"]
            and lo <= root <= hi
            and 0 <= (hi - lo) * 86400 <= 0.001
            and abs(row["residual_degrees"]) <= 1e-6
            and len(clocks) == len(shifts)
            and {c["local_minus_ut1_seconds"] for c in clocks} == set(shifts)
            and all(
                datetime.fromisoformat(c["predicted_local_calendar"])
                == datetime.fromisoformat(row["common_historical_ut1_calendar"])
                + timedelta(seconds=c["local_minus_ut1_seconds"])
                for c in clocks
            )
        )
    inventory = bool(
        source_complete
        and well_formed
        and predictions["plan_sha256"] == expected_plan_sha
        and len(models) == len(set(models))
        and len(keys) == len(required)
        and set(keys) == required
    )
    results = []
    for model in models:
        for shift in shifts:
            checks = []
            for event in events:
                rows = [
                    r
                    for r in predictions["rows"]
                    if (r["model"], r["event_id"]) == (model, event["event_id"])
                ]
                clocks = [
                    c
                    for r in rows
                    for c in r["clock_hypotheses"]
                    if c["local_minus_ut1_seconds"] == shift
                ]
                predicted = (
                    clocks[0]["predicted_local_calendar"]
                    if len(rows) == len(clocks) == 1
                    else None
                )
                inside = bool(
                    predicted is not None
                    and datetime.fromisoformat(event["left_local_label"])
                    < datetime.fromisoformat(predicted)
                    <= datetime.fromisoformat(event["right_local_label"])
                )
                checks.append(
                    {
                        "event_id": event["event_id"],
                        "source_interval": [
                            event["left_local_label"],
                            event["right_local_label"],
                        ],
                        "predicted_local_calendar": predicted,
                        "within_source_minute_interval": inside,
                    }
                )
            results.append(
                {
                    "model": model,
                    "local_minus_common_ut1_seconds": shift,
                    "events": checks,
                    "all_required_intervals_compatible": bool(
                        inventory
                        and all(c["within_source_minute_interval"] for c in checks)
                    ),
                }
            )
    groups: dict[str, list[str]] = {}
    for tag in plan["nominal_tag_aliases"]:
        groups.setdefault(tag["tree"], []).append(tag["tag"])
    return {
        "plan_sha256": expected_plan_sha,
        "required_model_count": len(models),
        "required_root_count": len(required),
        "provided_root_count": len(keys),
        "all_required_predictions_present_once": inventory,
        "source_intervals_bound_to_original_audit": bool(source_complete),
        "all_supplied_prediction_rows_retained": predictions["rows"],
        "hypotheses": results,
        "compatible_execution_path_count": sum(
            r["all_required_intervals_compatible"] for r in results
        ),
        "nominal_tag_count": len(plan["nominal_tag_aliases"]),
        "unique_official_tree_count": len({v["tree"]["sha"] for v in trees}),
        "tag_tree_groups": groups,
        "distinct_historical_release_versions_authenticated": False,
        "prior_audit_status": prior["status"],
        "prior_compatible_hypothesis_count": prior["candidate_comparison"][
            "compatible_hypothesis_count"
        ],
        "prior_failures_regraded": False,
        "source_backend_identified": False,
        "native_execution_authenticated": False,
        "physical_accuracy_certified": False,
        "production_default_switched": False,
        "all_three_axes_full_marks": False,
        "authority_certified": False,
        "scope": "All declared finite execution paths, with duplicate source tags exposed. Reproduction across bindings is not independent official observations. Neither matching minute intervals nor source hashes identify the publisher backend, certify physical accuracy or complete professional acceptance.",
    }


def verify_vendor_blobs(trees_raw: bytes, directory: Path) -> list[dict[str, Any]]:
    rows = []
    for version in json.loads(trees_raw):
        for entry in version["tree"]["tree"]:
            if entry["type"] != "blob":
                continue
            if (
                Path(version["id"]).name != version["id"]
                or Path(entry["path"]).name != entry["path"]
            ):
                raise ValueError("Source identity must be a basename")
            path = directory / version["id"] / entry["path"]
            content = path.read_bytes()
            blob = hashlib.sha1(
                ("blob " + str(len(content)) + "\0").encode() + content
            ).hexdigest()
            rows.append(
                {
                    "source_id": version["id"],
                    "path": entry["path"],
                    "size_matches": len(content) == entry["size"],
                    "git_blob_matches": blob == entry["sha"],
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "plan",
        "predictions",
        "prior-audit",
        "source-trees",
        "source-directory",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-plan-sha256", required=True)
    parser.add_argument("--expected-predictions-sha256", required=True)
    args = parser.parse_args()
    trees = args.source_trees.read_bytes()
    result = compare_all(
        args.plan.read_bytes(),
        pinned(args.predictions.read_bytes(), args.expected_predictions_sha256),
        args.prior_audit.read_bytes(),
        trees,
        args.expected_plan_sha256,
    )
    blobs = verify_vendor_blobs(trees, args.source_directory)
    bound = bool(blobs) and all(
        r["size_matches"] and r["git_blob_matches"] for r in blobs
    )
    result.update(
        {
            "vendor_blob_checks": blobs,
            "all_declared_vendor_blobs_verified": bound,
            "predictions_sha256": args.expected_predictions_sha256,
        }
    )
    successful = bool(
        bound
        and result["all_required_predictions_present_once"]
        and result["compatible_execution_path_count"]
    )
    result["status"] = (
        "finite_candidate_compatibility_only" if successful else "not_achieved"
    )
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "required_models": result["required_model_count"],
                "roots": result["provided_root_count"],
                "compatible_execution_paths": result["compatible_execution_path_count"],
                "original_professional_acceptance_achieved": False,
            }
        )
    )
    raise SystemExit(0 if successful else 1)


if __name__ == "__main__":
    main()
