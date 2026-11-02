"""Check observed strata and input links without calling the calculation engine.

The original plan's IDs declare targets, not official expected chart answers.
Every supplied row is retained, including duplicates and malformed observations.
This guard adds no aliases and cannot award full professional acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLAN_SHA256 = "ea4e0cd15bd228a3002bd055aaeaae28264b5edf0d51505af1828c29e78ce143"
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
PROFILES = {
    "1/3",
    "1/4",
    "2/4",
    "2/5",
    "3/5",
    "3/6",
    "4/6",
    "4/1",
    "5/1",
    "5/2",
    "6/2",
    "6/3",
}
IDENTIFIER = re.compile(r"profile-(\d{2})-([1-6])-([1-6])")
ACTIVATION = re.compile(r"([1-9]|[1-5]\d|6[0-4])\.([1-6])")


def target(identifier: str) -> tuple[int, str]:
    match = IDENTIFIER.fullmatch(identifier)
    if match is None:
        raise ValueError("Invalid original target ID")
    gate = int(match[1])
    profile = f"{match[2]}/{match[3]}"
    if not 1 <= gate <= 64 or profile not in PROFILES:
        raise ValueError("Invalid original target stratum")
    return gate, profile


def check_observed_strata(
    plan: dict[str, Any], cohort: dict[str, Any]
) -> dict[str, Any]:
    planned = plan["cases"]
    expected = {row["id"]: row for row in planned}
    targets = [target(row["id"]) for row in planned]
    if len(expected) != len(planned) or len(set(targets)) != len(targets):
        raise ValueError("Duplicate original plan identity or target")
    supplied = cohort["cases"]
    ids = [row.get("id") for row in supplied]
    counts = Counter(ids)
    missing_ids = [identifier for identifier in expected if identifier not in counts]
    unexpected_ids = [identifier for identifier in counts if identifier not in expected]
    duplicate_ids = [identifier for identifier, count in counts.items() if count > 1]
    original_order = ids == list(expected)[: len(ids)]
    order_ok = tuple(cohort.get("planet_order", [])) == ORDER
    checks = []
    actual_counts: Counter[tuple[int, str]] = Counter()
    for row in supplied:
        identifier = row.get("id")
        source = expected.get(identifier)
        errors = []
        observed_gate, observed_profile = None, None
        if source is None:
            errors.append("unplanned_id")
        elif row.get("birth_input") != source["birth_input"]:
            errors.append("birth_input_differs_from_original_plan")
        if not order_ok:
            errors.append("source_body_order_changed")
        try:
            observed_profile = row["properties"]["Profile"]
            if observed_profile not in PROFILES:
                errors.append("unsupported_observed_profile")
            positions = {}
            for side in ("personality", "design"):
                values = row["columns"][side]
                if len(values) != len(ORDER):
                    raise ValueError("Incomplete source activation column")
                parsed = [ACTIVATION.fullmatch(value) for value in values]
                if any(value is None for value in parsed):
                    raise ValueError("Invalid source gate.line")
                positions[side] = [(int(value[1]), int(value[2])) for value in parsed]
                if positions[side][0][1] != positions[side][1][1]:
                    errors.append(f"{side}_sun_earth_line_disagreement")
            observed_gate = positions["personality"][0][0]
            displayed_from_suns = (
                f"{positions['personality'][0][1]}/{positions['design'][0][1]}"
            )
            if observed_profile != displayed_from_suns:
                errors.append("profile_disagrees_with_observed_solar_lines")
            if source is not None and (observed_gate, observed_profile) != target(
                identifier
            ):
                errors.append("observed_stratum_differs_from_original_target")
            actual_counts[(observed_gate, observed_profile)] += 1
        except (KeyError, IndexError, TypeError, ValueError) as error:
            errors.append(f"invalid_source_shape:{type(error).__name__}")
        if source is not None:
            try:
                actual_utc = datetime.fromisoformat(row["displayed_birth_utc"])
                original_utc = datetime.fromisoformat(source["engine_utc"])
                if actual_utc.utcoffset() != timedelta(0):
                    errors.append("displayed_utc_has_nonzero_or_missing_offset")
                if actual_utc != original_utc:
                    errors.append("displayed_utc_differs_from_original_plan")
            except (KeyError, TypeError, ValueError):
                errors.append("invalid_source_utc")
        checks.append(
            {
                "id": identifier,
                "observed_sun_gate": observed_gate,
                "observed_profile": observed_profile,
                "status": "matched" if not errors else "mismatched",
                "errors": errors,
            }
        )
    missing_strata = [pair for pair in targets if pair not in actual_counts]
    duplicate_strata = [
        {"gate": pair[0], "profile": pair[1], "count": count}
        for pair, count in sorted(actual_counts.items())
        if count > 1
    ]
    unexpected_strata = [pair for pair in actual_counts if pair not in set(targets)]
    actual_complete = not (missing_ids or unexpected_ids or duplicate_ids) and len(
        ids
    ) == len(expected)
    metadata_ok = (
        type(cohort.get("planned_case_count")) is int
        and cohort["planned_case_count"] == len(expected)
        and type(cohort.get("observed_case_count")) is int
        and cohort["observed_case_count"] == len(supplied)
        and cohort.get("missing_planned_ids") == missing_ids
        and cohort.get("collection_status")
        == ("complete" if actual_complete else "incomplete")
    )
    passed = (
        not (
            missing_ids
            or unexpected_ids
            or duplicate_ids
            or missing_strata
            or duplicate_strata
            or unexpected_strata
        )
        and original_order
        and metadata_ok
        and all(row["status"] == "matched" for row in checks)
    )
    return {
        "method_id": "observed_human_design_profile_strata_and_input_links_v1",
        "status": (
            "observed_strata_and_input_links_matched" if passed else "not_achieved"
        ),
        "expected_target_count": len(targets),
        "supplied_case_count": len(supplied),
        "matched_expected_strata": sum(pair in actual_counts for pair in targets),
        "missing_ids": missing_ids,
        "unexpected_ids": unexpected_ids,
        "duplicate_ids": duplicate_ids,
        "missing_strata": missing_strata,
        "unexpected_strata": unexpected_strata,
        "duplicate_strata": duplicate_strata,
        "ids_follow_original_prefix": original_order,
        "collection_metadata_consistent": metadata_ok,
        "all_supplied_rows_retained": len(checks) == len(supplied),
        "cases": checks,
        "all_three_axes_full_marks": False,
        "all_four_axes_full_marks": False,
        "authority_certified": False,
        "real_world_sample_size": 0,
        "scope": "Observed Sun gate/Profile cells, displayed solar-line coherence and original input/UTC links only. Plan targets are not independent astronomical expected answers. Stored UTC agreement is not historical clock truth. No aliases, calculation calls, PDF diagram re-transcription, whole-calendar/source/model/prediction certification, or regrading of old failures.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        type=Path,
        default=ROOT / "tests/fixtures/human-design-profile-coverage-plan.json",
    )
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan_raw, raw = args.plan.read_bytes(), args.cohort.read_bytes()
    if hashlib.sha256(plan_raw).hexdigest() != PLAN_SHA256:
        raise ValueError("Original768 plan changed")
    plan = json.loads(plan_raw)
    if len(plan["cases"]) != 768 or set(
        map(target, (row["id"] for row in plan["cases"]))
    ) != {(gate, profile) for gate in range(1, 65) for profile in PROFILES}:
        raise ValueError("Original64by12 target matrix changed")
    report = check_observed_strata(plan, json.loads(raw))
    report["original_plan_sha256"] = PLAN_SHA256
    report["cohort_sha256"] = hashlib.sha256(raw).hexdigest()
    report["checker_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "status",
                    "expected_target_count",
                    "supplied_case_count",
                    "matched_expected_strata",
                    "all_supplied_rows_retained",
                )
            }
        )
    )
    raise SystemExit(report["status"] != "observed_strata_and_input_links_matched")


if __name__ == "__main__":
    main()
