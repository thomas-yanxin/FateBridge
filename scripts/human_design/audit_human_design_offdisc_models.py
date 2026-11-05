"""Keep all24 off-disc probes and distinguish data editions from TT policies.

Target-label compatibility is a finite source observation. It cannot identify a
publisher backend, replace physical accuracy tests or complete source prose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from fatebridge.validation.human_design import verify_human_design_reading

PLAN_SHA256 = "9cc92b18370480e2d27c88c5945d50704dcef0978695dd45238ee7642cd731ee"
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
# Uniform mandala, anchored at302deg; the printed29.1/29.2 conflict remains open.
GATES = (
    41,
    19,
    13,
    49,
    30,
    55,
    37,
    63,
    22,
    36,
    25,
    17,
    21,
    51,
    42,
    3,
    27,
    24,
    2,
    23,
    8,
    20,
    16,
    35,
    45,
    12,
    15,
    52,
    39,
    53,
    62,
    56,
    31,
    33,
    7,
    4,
    29,
    59,
    40,
    64,
    47,
    6,
    46,
    18,
    48,
    57,
    32,
    50,
    28,
    44,
    1,
    43,
    14,
    34,
    9,
    5,
    26,
    11,
    10,
    58,
    38,
    54,
    61,
    60,
)


def uniform_label(longitude: float) -> str:
    if not math.isfinite(longitude) or not 0 <= longitude < 360:
        raise ValueError("Finite normalized longitude required")
    index = math.floor(((longitude - 302) % 360) * 16 / 15)
    return f"{GATES[index // 6]}.{index % 6 + 1}"


def compare_all(
    plan_raw: bytes,
    initial: dict[str, Any],
    production: dict[str, Any],
    supplement: dict[str, Any],
    cohort: dict[str, Any],
    packets: list[dict[str, Any]],
    expected_plan_sha256: str = PLAN_SHA256,
) -> dict[str, Any]:
    if hashlib.sha256(plan_raw).hexdigest() != expected_plan_sha256:
        raise ValueError("Original off-disc plan changed")
    plan = json.loads(plan_raw)
    cases = plan["cases"]
    ids = [c["id"] for c in cases]
    cells = {(c["century"], c["body"]) for c in cases}
    required_cells = {
        (century, body)
        for century in range(1800, 2400, 100)
        for body in ("Saturn", "Uranus", "Neptune", "Pluto")
    }
    if len(ids) != len(set(ids)) or len(ids) != 24 or cells != required_cells:
        raise ValueError("All original24 stratified inputs required")
    models = plan["native_models"] + plan["independent_models"]
    expected_initial = {
        (c["id"], model, clock["utc_label"]): (c, clock)
        for c in cases
        for model in models
        for clock in c["scenarios"]
        if clock["model"] == "DE441"
    }
    supplement_ids = [c["id"] for c in supplement["cases"]]
    supplements_bound = supplement_ids == ids and all(
        a["birth_input"] == b["birth_input"] for a, b in zip(cases, supplement["cases"])
    )
    expected_production = {
        (c["id"], model, clock["utc_label"]): (c, clock)
        for c in supplement["cases"]
        for model in models
        for clock in c["scenarios"]
        if clock["model"] == "DE441"
    }

    def inventory(
        data: dict[str, Any],
        expected: dict[tuple[str, str, str], tuple[dict[str, Any], dict[str, Any]]],
    ) -> dict[str, Any]:
        rows = data["rows"]
        keys = [(r["case_id"], r["model"], r["clock_utc_label"]) for r in rows]
        bad = []
        for index, (row, key) in enumerate(zip(rows, keys)):
            selected = expected.get(key)
            try:
                well_formed = bool(
                    selected is not None
                    and row["body"] == selected[0]["body"]
                    and row["jd_tt"] == selected[1]["jd_tt"]
                    and row["clock_hypotheses"] == selected[1]["clock_hypotheses"]
                    and row["uniform_gate_line"] == uniform_label(row["longitude"])
                    and row["printed2001_gate_line"] == row["uniform_gate_line"]
                )
            except (ValueError, TypeError, KeyError):
                well_formed = False
            if not well_formed:
                bad.append(index)
        return {
            "required": len(expected),
            "provided": len(rows),
            "invalid_row_indices": bad,
            "missing_keys": sorted(set(expected) - set(keys)),
            "unexpected_keys": sorted(set(keys) - set(expected)),
            "duplicate_keys": [k for k, n in Counter(keys).items() if n > 1],
            "complete_and_bound": not bad
            and len(keys) == len(expected)
            and set(keys) == set(expected),
        }

    initial_inventory = inventory(initial, expected_initial)
    production_inventory = inventory(production, expected_production)
    predictions_complete = bool(
        len(models) == len(set(models)) == 10
        and initial["source_plan_sha256"] == expected_plan_sha256
        and production["source_plan_sha256"]
        == hashlib.sha256(
            (json.dumps(supplement, indent=2) + "\n").encode()
        ).hexdigest()
        and initial_inventory["complete_and_bound"]
        and production_inventory["complete_and_bound"]
        and supplements_bound
    )
    observed_ids = [c["id"] for c in cohort["cases"]]
    unexpected = [i for i in observed_ids if i not in ids]
    duplicates = [k for k, n in Counter(observed_ids).items() if n > 1]
    by_id = {c["id"]: c for c in cases}
    source_rows_bound = bool(
        not unexpected
        and not duplicates
        and observed_ids == [i for i in ids if i in observed_ids]
        and all(
            c["birth_input"] == by_id[c["id"]]["birth_input"]
            and len(c["columns"]["personality"]) == 13
            and len(c["columns"]["design"]) == 13
            for c in cohort["cases"]
        )
    )
    missing = [i for i in ids if i not in observed_ids]
    source_complete = source_rows_bound and not missing and len(observed_ids) == 24
    metadata_consistent = bool(
        cohort.get("planned_case_count") == 24
        and cohort.get("observed_case_count") == len(observed_ids)
        and cohort.get("missing_planned_ids") == missing
        and cohort.get("collection_status")
        == ("complete" if source_complete else "incomplete")
        and cohort["source"]["plan_sha256"] == expected_plan_sha256
    )
    # The retained cohort is a transcription reference. Its ten original PDFs
    # are unavailable; past boolean binding receipts cannot verify them now.
    pdf_bound = False
    hypotheses = []
    for clock_policy in (
        "common_swiss_IANA",
        "common_swiss_pre1847_fields_as_UTC",
        "actual_production_TT",
    ):
        data = production if clock_policy == "actual_production_TT" else initial
        for model in models:
            checks = []
            for c in cases:
                observed = [r for r in cohort["cases"] if r["id"] == c["id"]]
                clocks = [s for s in c["scenarios"] if s["model"] == "DE441"]
                selected_utc = (
                    c["nominal_local_label"] + "+00:00"
                    if clock_policy == "common_swiss_pre1847_fields_as_UTC"
                    and c["birth_input"]["birth_year"] < 1847
                    else next(
                        s["utc_label"]
                        for s in clocks
                        if "IANA_fold_0" in s["clock_hypotheses"]
                    )
                )
                predicted = [
                    r
                    for r in data["rows"]
                    if (r["case_id"], r["model"], r["clock_utc_label"])
                    == (c["id"], model, selected_utc)
                ]
                actual = (
                    observed[0]["columns"]["personality"][ORDER.index(c["body"])]
                    if len(observed) == 1
                    else None
                )
                label = (
                    predicted[0]["uniform_gate_line"] if len(predicted) == 1 else None
                )
                checks.append(
                    {
                        "id": c["id"],
                        "observed": actual,
                        "predicted": label,
                        "matched": actual is not None and label == actual,
                    }
                )
            hypotheses.append(
                {
                    "model": model,
                    "clock_policy": clock_policy,
                    "cases": checks,
                    "observed_target_matches": sum(c["matched"] for c in checks),
                    "conditional_on_transcriptions_targets_compatible": bool(
                        predictions_complete
                        and source_rows_bound
                        and observed_ids
                        and all(
                            c["matched"] for c in checks if c["observed"] is not None
                        )
                    ),
                    "all_observed_targets_compatible": False,
                    "all24_required_targets_compatible": bool(
                        predictions_complete
                        and source_complete
                        and metadata_consistent
                        and pdf_bound
                        and all(c["matched"] for c in checks)
                    ),
                }
            )
    packet_ids = [r["id"] for r in packets]
    fixed_readings = []
    native_links = []
    clock_comparison = []
    for c in cases:
        rows = [r for r in packets if r["id"] == c["id"]]
        supplied = len(rows) == 1 and rows[0]["birth_input"] == c["birth_input"]
        proof = (
            verify_human_design_reading(rows[0]["run"])
            if supplied
            else {"status": "not_verified"}
        )
        fixed_readings.append(
            {
                "id": c["id"],
                "proof": proof,
            }
        )
        if not supplied:
            native_links.append({"id": c["id"], "matched": False})
            continue
        run = rows[0]["run"]
        target = next(
            a for a in run["activations"]["personality"] if a["body"] == c["body"]
        )
        predicted = [
            r
            for r in production["rows"]
            if r["case_id"] == c["id"] and r["model"] == "DE441_default"
        ]
        matches = bool(
            len(predicted) == 1
            and predicted[0]["jd_tt"] == run["time_scales"]["personality"]["jd_tt"]
            and predicted[0]["longitude"] == target["longitude"]
            and predicted[0]["uniform_gate_line"]
            == f"{target['gate']}.{target['line']}"
        )
        native_links.append({"id": c["id"], "matched": matches})
        old = next(
            s
            for s in c["scenarios"]
            if s["model"] == "DE441" and "IANA_fold_0" in s["clock_hypotheses"]
        )
        clock_comparison.append(
            {
                "id": c["id"],
                "original_common_clock_label": c["stable_expected_labels"]["DE441"],
                "actual_production_label": f"{target['gate']}.{target['line']}",
                "production_minus_original_tt_seconds": (
                    run["time_scales"]["personality"]["jd_tt"] - old["jd_tt"]
                )
                * 86400,
                "label_changed": f"{target['gate']}.{target['line']}"
                != c["stable_expected_labels"]["DE441"],
                "data_edition_discriminator_survives_production_clock": len(
                    {
                        r["uniform_gate_line"]
                        for r in production["rows"]
                        if r["case_id"] == c["id"]
                        and r["model"] in ("DE441_default", "JPL406_default")
                    }
                )
                == 2,
            }
        )
    packets_bound = packet_ids == ids and all(r["matched"] for r in native_links)
    return {
        "status": (
            "finite_source_comparison_only"
            if source_complete
            and metadata_consistent
            and pdf_bound
            and predictions_complete
            else "not_achieved"
        ),
        "required_cases": 24,
        "observed_cases": len(observed_ids),
        "missing_case_ids": missing,
        "unexpected_case_ids": unexpected,
        "duplicate_case_ids": duplicates,
        "source_rows_bound": source_rows_bound,
        "source_collection_complete": source_complete,
        "source_metadata_consistent": metadata_consistent,
        "all_obtained_pdf_text_bound": pdf_bound,
        "primary_source_status": "not_available",
        "primary_source_scope": "Ten preserved transcribed source rows; original PDFs and original raw observation file are unavailable. Model label agreement is conditional on these transcriptions, not primary-source authentication.",
        "initial_prediction_inventory": initial_inventory,
        "production_prediction_inventory": production_inventory,
        "all_required_predictions_bound": predictions_complete,
        "hypotheses": hypotheses,
        "all_supplied_prediction_rows_retained": {
            "original_common_clock": initial["rows"],
            "actual_production_clock_supplement": production["rows"],
        },
        "native_packet_links": native_links,
        "all24_native_packets_bound": packets_bound,
        "fixed_reading_checks": fixed_readings,
        "all24_fixed_readings_verified": packets_bound
        and all(
            r["proof"]["status"] == "verified_fixed_template_reading"
            for r in fixed_readings
        ),
        "clock_policy_comparison": clock_comparison,
        "original_clock_label_disagreement_ids": [
            r["id"] for r in clock_comparison if r["label_changed"]
        ],
        "data_edition_discriminator_lost_at_production_clock_ids": [
            r["id"]
            for r in clock_comparison
            if not r["data_edition_discriminator_survives_production_clock"]
        ],
        "original_predictions_replaced": False,
        "prior_failures_regraded": False,
        "source_backend_identified": False,
        "physical_accuracy_certified": False,
        "complete384_line_prose_accepted": False,
        "arbitrary_model_prose_accepted": False,
        "reality_prediction_sample_count": 0,
        "reality_prediction_status": "not_tested",
        "all_three_axes_full_marks": False,
        "all_four_axes_full_marks": False,
        "authority_certified": False,
        "scope": "All24 original off-disc inputs retained. Three global clock policies, never a best clock chosen per case. Matching obtained targets leaves all missing rows required. Fixed-template replay does not accept arbitrary prose or full384 original meanings. Neither data edition nor physical time is certified by a visible gate.line.",
    }


def current_packets(plan):
    """Run each declared input now; no archived result or proof supplies facts."""
    import os
    from unittest.mock import patch

    from fatebridge.application.execution import execute_tool
    from fatebridge.services.tool_catalog import CATALOG

    root = Path(__file__).resolve().parents[2]
    spec = next(s for s in CATALOG if s.key == "human_design")
    results = []
    with patch.dict(os.environ, {"SE_EPHE_PATH": str(root / "ephe")}):
        os.environ.pop("FATEBRIDGE_JPL_FILE", None)
        for case in plan["cases"]:
            run = execute_tool(spec, spec.request_model(**case["birth_input"]))
            results.append(
                {"id": case["id"], "birth_input": case["birth_input"], "run": run}
            )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = args.directory

    def read(name: str) -> Any:
        return json.loads((base / name).read_bytes())

    cohort = read("source-cohort.json")
    packets = current_packets(json.loads((base / "source-plan.json").read_bytes()))
    report = compare_all(
        (base / "source-plan.json").read_bytes(),
        read("model-predictions.json"),
        read("production-clock-model-predictions.json"),
        read("production-clock-supplement-plan.json"),
        cohort,
        packets,
    )
    report["input_sha256"] = {
        name: hashlib.sha256((base / name).read_bytes()).hexdigest()
        for name in (
            "source-plan.json",
            "model-predictions.json",
            "production-clock-model-predictions.json",
            "production-clock-supplement-plan.json",
            "source-cohort.json",
        )
    }
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "status",
                    "required_cases",
                    "observed_cases",
                    "all_required_predictions_bound",
                    "all24_native_packets_bound",
                    "all24_fixed_readings_verified",
                    "original_clock_label_disagreement_ids",
                )
            }
        )
    )
    raise SystemExit(report["status"] == "not_achieved")


if __name__ == "__main__":
    main()
