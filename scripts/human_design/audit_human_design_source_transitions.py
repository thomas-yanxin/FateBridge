"""Replay a frozen adaptive source search without dropping failed hypotheses.

This verifies finite visible-source observations, not source internals, physical
accuracy, full line meanings, or professional acceptance. PDFs independently
bind text properties only; activation columns come from the saved visible SVG.
"""

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from scripts.human_design.read_human_design_official_pdf import visible_properties

ORDER = (
    "Sun",
    "Earth",
    "Moon",
    "NorthNode",
    "SouthNode",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
)


def pinned_json(raw: bytes, expected: str) -> dict[str, Any]:
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Plan does not match required digest")
    return cast(dict[str, Any], json.loads(raw))


def next_step(
    plan: dict[str, Any], cache: dict[int, dict[str, Any]]
) -> tuple[int | None, list[dict[str, Any]]]:
    """Pure replay of the declared endpoint/midpoint procedure."""
    cases = plan["cases"]
    by_id = {c["id"]: i for i, c in enumerate(cases)}
    events: list[dict[str, Any]] = []
    for case_id in plan["mandatory_repeat_case_ids"]:
        if by_id[case_id] not in cache:
            return by_id[case_id], events
    for event in plan["events"]:
        lo, hi = event["left_case_index"], event["right_case_index"]
        if hi - lo != 30:
            raise ValueError("Expected the original31minute event window")
        for index in (lo, hi):
            if index not in cache:
                return index, events

        def label(index: int) -> str:
            return cast(
                str,
                cache[index]["facts"]["columns"]["personality"][
                    ORDER.index(event["body"])
                ],
            )

        before, after = event["source_before_label"], event["source_after_label"]
        status = "bounded_adjacent_minute_transition"
        trace = []
        if label(lo) != before or label(hi) != after:
            status = "not_bracketed"
        else:
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if mid not in cache:
                    return mid, events
                observed = label(mid)
                trace.append({"left": lo, "right": hi, "mid": mid, "label": observed})
                if observed == before:
                    lo = mid
                elif observed == after:
                    hi = mid
                else:
                    status = "unexpected_source_label"
                    break
        events.append(
            {
                "event_id": event["event_id"],
                "body": event["body"],
                "boundary_longitude": event["boundary_longitude"],
                "status": status,
                "left_id": cases[lo]["id"],
                "right_id": cases[hi]["id"],
                "left_local_label": cases[lo]["nominal_local_label"],
                "right_local_label": cases[hi]["nominal_local_label"],
                "left_label": label(lo),
                "right_label": label(hi),
                "trace": trace,
            }
        )
    return None, events


def repeat_checks(
    plan: dict[str, Any], observations: list[dict[str, Any]], prior: dict[str, Any]
) -> list[dict[str, Any]]:
    checks = []
    for case_id in plan["mandatory_repeat_case_ids"]:
        case = next(c for c in plan["cases"] if c["id"] == case_id)
        old = [c for c in prior["cases"] if c["birth_input"] == case["birth_input"]]
        new = [r for r in observations if r["id"] == case_id]
        fields = {}
        if len(old) == len(new) == 1:
            facts = new[0]["facts"]
            for field in ("columns", "defined_centers", "defined_channel_render_ids"):
                fields[field] = facts[field] == old[0][field]

            def normalize(p):
                return {k: " ".join(v.split()) for k, v in p.items() if k != "Name"}

            fields["all12_other_properties"] = normalize(
                facts["properties"]
            ) == normalize(old[0]["properties"])
        checks.append(
            {
                "id": case_id,
                "prior_id": old[0]["id"] if len(old) == 1 else None,
                "fields": fields,
                "stable_except_declared_name": len(fields) == 4
                and all(fields.values()),
            }
        )
    return checks


def adaptive_checks(
    plan_raw: bytes,
    observations: list[dict[str, Any]],
    expected_sha: str,
    prior_raw: bytes,
    expected_prior_sha: str,
) -> dict[str, Any]:
    plan = pinned_json(plan_raw, expected_sha)
    prior = pinned_json(prior_raw, expected_prior_sha)
    cases = plan["cases"]
    ids = [c["id"] for c in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate planned case identity")
    cache: dict[int, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for row in observations:
        expected_index, _ = next_step(plan, cache)
        index = ids.index(row["id"]) if row["id"] in ids else None
        valid = index is not None and index not in cache and index == expected_index
        properties = row["facts"]["properties"]
        try:
            local = datetime.strptime(
                properties["Date and Time (Local)"], "%B %d, %Y, %H:%M"
            ).isoformat()
        except (ValueError, KeyError):
            local = None
        input_matched = bool(
            index is not None
            and local == cases[index]["nominal_local_label"]
            and properties["Location"] == plan["city"]
        )
        columns = row["facts"]["columns"]
        columns_valid = set(columns) == {"design", "personality"} and all(
            len(values) == 13
            and all(
                re.fullmatch(r"(?:[1-9]|[1-5][0-9]|6[0-4])\.[1-6]", value)
                for value in values
            )
            for values in columns.values()
        )
        rows.append(
            {
                "id": row["id"],
                "expected_id": (
                    ids[expected_index] if expected_index is not None else None
                ),
                "original_decision_order_matched": valid,
                "planned_local_input_matched": input_matched,
                "visible_activation_columns_well_formed": columns_valid,
            }
        )
        if index is not None:
            # Retain and report duplicates; never overwrite the first observation.
            cache.setdefault(index, row)
    request, events = next_step(plan, cache)
    repeats = repeat_checks(plan, observations, prior)
    complete = (
        bool(rows)
        and all(
            all(
                r[k]
                for k in (
                    "original_decision_order_matched",
                    "planned_local_input_matched",
                    "visible_activation_columns_well_formed",
                )
            )
            for r in rows
        )
        and len(rows) <= plan["maximum_distinct_queries"]
        and request is None
        and len(events) == len(plan["events"])
        and all(e["status"] == "bounded_adjacent_minute_transition" for e in events)
        and all(r["stable_except_declared_name"] for r in repeats)
    )
    return {
        "plan_sha256": expected_sha,
        "prior_observations_sha256": expected_prior_sha,
        "repeat_control_checks": repeats,
        "potential_query_count": len(cases),
        "observations_supplied": len(observations),
        "observations_unique": len(cache),
        "required_event_count": len(plan["events"]),
        "events": events,
        "next_required_id": ids[request] if request is not None else None,
        "observation_order_checks": rows,
        "finite_adaptive_search_complete": complete,
        "all_supplied_observations_retained": True,
        "continuous_transition_behavior_certified": False,
    }


def hypothesis_checks(
    model_plan_raw: bytes,
    predictions: dict[str, Any],
    search: dict[str, Any],
    expected_sha: str,
) -> dict[str, Any]:
    model_plan = pinned_json(model_plan_raw, expected_sha)
    models = model_plan["native_models"] + model_plan["independent_models"]
    shifts = model_plan["clock_hypotheses_seconds_local_minus_common_ut1"]
    events = search["events"]
    wanted = {(m, e["event_id"]) for m in models for e in events}
    supplied = [(r["model"], r["event_id"]) for r in predictions["rows"]]
    by_event = {e["event_id"]: e for e in events}
    inventory_ok = (
        search["finite_adaptive_search_complete"]
        and len(events) == search["required_event_count"]
        and len(supplied) == len(wanted)
        and set(supplied) == wanted
        and predictions["plan_sha256"] == expected_sha
        and all(
            len(r["clock_hypotheses"]) == len(shifts)
            and {c["local_minus_ut1_seconds"] for c in r["clock_hypotheses"]}
            == set(shifts)
            for r in predictions["rows"]
        )
        and all(
            r["body"] == by_event[r["event_id"]]["body"]
            and r["boundary_longitude"] == by_event[r["event_id"]]["boundary_longitude"]
            and all(
                datetime.fromisoformat(c["predicted_local_calendar"])
                == datetime.fromisoformat(r["common_historical_ut1_calendar"])
                + timedelta(seconds=c["local_minus_ut1_seconds"])
                for c in r["clock_hypotheses"]
            )
            for r in predictions["rows"]
        )
    )
    results = []
    for model in models:
        for shift in shifts:
            checks = []
            for event in events:
                matching = [
                    r
                    for r in predictions["rows"]
                    if (r["model"] == model and r["event_id"] == event["event_id"])
                ]
                clocks = [
                    c
                    for r in matching
                    for c in r["clock_hypotheses"]
                    if (c["local_minus_ut1_seconds"] == shift)
                ]
                left = datetime.fromisoformat(event["left_local_label"])
                right = datetime.fromisoformat(event["right_local_label"])
                predicted = (
                    datetime.fromisoformat(clocks[0]["predicted_local_calendar"])
                    if len(matching) == len(clocks) == 1
                    else None
                )
                checks.append(
                    {
                        "event_id": event["event_id"],
                        "source_local_interval_open_left_closed_right": [
                            event["left_local_label"],
                            event["right_local_label"],
                        ],
                        "predicted_local_calendar": (
                            predicted.isoformat() if predicted else None
                        ),
                        "within_observed_minute_interval": bool(
                            event["status"] == "bounded_adjacent_minute_transition"
                            and predicted is not None
                            and left < predicted <= right
                        ),
                    }
                )
            results.append(
                {
                    "model": model,
                    "local_minus_common_ut1_seconds": shift,
                    "events": checks,
                    "all_required_intervals_compatible": bool(
                        inventory_ok
                        and all(c["within_observed_minute_interval"] for c in checks)
                    ),
                }
            )
    return {
        "model_plan_sha256": expected_sha,
        "required_model_count": len(models),
        "required_clock_hypotheses": shifts,
        "all_declared_prediction_rows_present_once": bool(inventory_ok),
        "all_supplied_prediction_rows_retained": predictions["rows"],
        "hypotheses": results,
        "compatible_hypothesis_count": sum(
            r["all_required_intervals_compatible"] for r in results
        ),
        "source_backend_identified": False,
        "physical_accuracy_certified": False,
    }


def pdf_bindings(
    observations: list[dict[str, Any]], directory: Path
) -> list[dict[str, Any]]:
    result = []
    for row in observations:
        source = row["source"]
        name = source["pdf_filename"]
        if Path(name).name != name or Path(row["id"]).name != row["id"]:
            raise ValueError("PDF identity must be a basename")
        path = directory / row["id"] / "pdfs" / name
        raw = path.read_bytes()
        text = visible_properties(path)

        def normalized(values):
            return {k: " ".join(v.split()) for k, v in values.items()}

        result.append(
            {
                "id": row["id"],
                "sha256_matches": hashlib.sha256(raw).hexdigest()
                == source["pdf_sha256"],
                "size_matches": len(raw) == source["pdf_bytes"],
                "all13_text_properties_match": len(text) == 13
                and normalized(text) == normalized(row["facts"]["properties"]),
                "pdf_activation_image_independently_transcribed": False,
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in (
        "plan",
        "prior-observations",
        "observations",
        "pdf-directory",
        "model-plan",
        "predictions",
        "output",
    ):
        parser.add_argument("--" + arg, type=Path, required=True)
    parser.add_argument("--expected-plan-sha256", required=True)
    parser.add_argument("--expected-prior-sha256", required=True)
    parser.add_argument("--expected-model-plan-sha256", required=True)
    parser.add_argument("--expected-predictions-sha256", required=True)
    args = parser.parse_args()
    observations = json.loads(args.observations.read_text())
    search = adaptive_checks(
        args.plan.read_bytes(),
        observations,
        args.expected_plan_sha256,
        args.prior_observations.read_bytes(),
        args.expected_prior_sha256,
    )
    hypotheses = hypothesis_checks(
        args.model_plan.read_bytes(),
        pinned_json(args.predictions.read_bytes(), args.expected_predictions_sha256),
        search,
        args.expected_model_plan_sha256,
    )
    bindings = pdf_bindings(observations, args.pdf_directory)
    bound = bool(bindings) and all(
        all(
            r[k]
            for k in ("sha256_matches", "size_matches", "all13_text_properties_match")
        )
        for r in bindings
    )
    explained = bool(
        bound
        and search["finite_adaptive_search_complete"]
        and hypotheses["compatible_hypothesis_count"]
    )
    result = {
        "status": (
            "finite_candidate_compatibility_only" if explained else "not_achieved"
        ),
        "search": search,
        "pdf_bindings": bindings,
        "all_text_properties_bound": bound,
        "candidate_comparison": hypotheses,
        "observations_sha256": hashlib.sha256(
            args.observations.read_bytes()
        ).hexdigest(),
        "predictions_sha256": args.expected_predictions_sha256,
        "original_professional_acceptance_reclassified": False,
        "all_three_axes_full_marks": False,
        "all_four_axes_full_marks": False,
        "authority_certified": False,
        "scope": "Finite source minute intervals under declared continuous forward-crossing models; neither continuous source behavior, clock truth, backend identity, physical accuracy, full prose nor professional acceptance is certified.",
    }
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "observations": len(observations),
                "finite_search_complete": search["finite_adaptive_search_complete"],
                "compatible_hypotheses": hypotheses["compatible_hypothesis_count"],
            }
        )
    )
    raise SystemExit(0 if explained else 1)


if __name__ == "__main__":
    main()
