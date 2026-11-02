"""All-577 OBSERVER-native source clocks and conditional polynomial references."""

import argparse
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_geocentric_meanvalue import FAMILIES, HYPOTHESES, infer
from scripts.astrodice_nonuniform_reference import (
    DEGREES,
    WINDOWS,
    fit,
    observer_angles,
    quality,
)
from scripts.astrodice_observer_clock import parse_observer
from scripts.astrodice_vector_clock import check_inputs, save
from scripts.verify_astrodice_earth_clock import wire


def claims(cohort, digest):
    return {
        "cohort": cohort,
        "plan_sha256": digest,
        "monotone_pair_partition": True,
        "receiver_enclosure_method": "uniform_mean_value_necessary_enclosure_v1",
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "numerical_tubes_certified": False,
        "physical_time_model_certified": False,
        "internal_algorithm_certified": False,
        "TT_derivative_certified": False,
        "physical_remainder_certified": False,
        "original_odd_polynomial_gate_replaced": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


def clocks(run, cohort):
    plan, digest = check_inputs(run)
    output = claims(cohort, digest) | {"queries": []}
    folder = run / "query-results"
    folder.mkdir(exist_ok=True)
    for query in plan["queries"]:
        if query["cohort"] != cohort:
            continue
        raw, receipt = wire(run, query)
        if receipt["status"] != 200:
            raise ValueError("Observer source unavailable; full cohort incomplete")
        rows = parse_observer(raw, query, query["cases"], plan)
        record = {"id": query["id"], "encoding": query["encoding"], "rows": []}
        for row in rows:
            case = next(c for c in query["cases"] if c["id"] == row["case_id"])
            record["rows"].append(
                {
                    "observation": row,
                    "inference": infer(run / "source-records", case, row, plan),
                }
            )
        save(folder / (query["id"] + "-first.json"), record)
        output["queries"].append(record)
        print(query["id"], "source rows", len(rows), flush=True)
    primary(run, plan, output)
    return output


def primary(run, plan, data):
    """Full fixed population, never a passing subset or a window-selected set."""
    records = {}
    queries = {q["id"]: q for q in plan["queries"]}
    for group in data["queries"]:
        query = queries[group["id"]]
        for record in group["rows"]:
            row = record["observation"]
            case = next(c for c in query["cases"] if c["id"] == row["case_id"])
            if case["role"] == "auxiliary_not_primary":
                continue
            offset = case["offset_seconds"]
            if offset in records:
                raise ValueError("Primary node repeated")
            records[offset] = record
    if sorted(records) != list(range(-1440, 1441, 5)):
        raise ValueError("All 577 primary nodes required")
    return records


def model_population(records, profile, family, hypothesis):
    rows = []
    epochs = {}
    for offset, record in sorted(records.items()):
        model = record["inference"]["profiles"][profile][family]
        pairs = model["qualified_pairs_by_hypothesis"][hypothesis]
        qualified = (
            model["status"] == "complete"
            and len(pairs) == 1
            and record["observation"]["original_label_budget_pass"]
        )
        rows.append(
            {
                "offset_seconds": offset,
                "status": model["status"],
                "label_budget_pass": record["observation"][
                    "original_label_budget_pass"
                ],
                "qualified_pairs": pairs,
                "qualified": qualified,
            }
        )
        if qualified:
            raw = Q(float.fromhex(pairs[0][0]))
            epochs[offset] = raw * 86400 if family == FAMILIES[0] else raw
    return rows, epochs


def references(run, cohort):
    plan, digest = check_inputs(run)
    data = json.loads((run / (cohort + "-first-analysis.json")).read_text())
    if data["plan_sha256"] != digest:
        raise ValueError("Clock output identity changed")
    records = primary(run, plan, data)
    angles = {o: r["observation"]["apparent_angles"] for o, r in records.items()}
    result = claims(cohort, digest) | {
        "primary_nodes": 577,
        "models": [],
        "fits_by_input_sha256": {},
    }
    for profile in plan["numerical_tube_profiles"]:
        for family in FAMILIES:
            for hypothesis in HYPOTHESES:
                rows, epochs = model_population(records, profile, family, hypothesis)
                entry = {
                    "profile": profile,
                    "coordinate_family": family,
                    "rounding_hypothesis": hypothesis,
                    "population": rows,
                }
                if len(epochs) != 577:
                    entry.update(
                        status="full_clock_population_unqualified",
                        required_nodes=577,
                        qualified_nodes=len(epochs),
                    )
                else:
                    payload = json.dumps(
                        {
                            "angles": angles,
                            "source_seconds": {
                                o: str(t) for o, t in sorted(epochs.items())
                            },
                        },
                        sort_keys=True,
                    ).encode()
                    key = hashlib.sha256(payload).hexdigest()
                    if key not in result["fits_by_input_sha256"]:
                        fits = [
                            fit(angles, epochs, w, d) for w in WINDOWS for d in DEGREES
                        ]
                        result["fits_by_input_sha256"][key] = {
                            "all_windows": fits,
                            "quality": quality(fits),
                        }
                    entry.update(
                        status="conditional_native_source_fit",
                        required_nodes=577,
                        qualified_nodes=577,
                        fit_input_sha256=key,
                    )
                result["models"].append(entry)
    if all(r["observation"]["original_label_budget_pass"] for r in records.values()):
        nominal = {o: Q(o) for o in records}
        fitted = [fit(angles, nominal, w, d) for w in WINDOWS for d in DEGREES]
        for window in fitted:
            for axis in window["axes"]:
                old = "derivative_interval_arcsec_per_TDB_day"
                if old in axis:
                    axis["derivative_interval_arcsec_per_nominal_TT_day"] = axis.pop(
                        old
                    )
        # The quality test is coordinate-arithmetic only; rename values back in
        # a temporary view so the fixed, previously declared rule is identical.
        temporary = json.loads(json.dumps(fitted))
        for window in temporary:
            for axis in window["axes"]:
                old = "derivative_interval_arcsec_per_nominal_TT_day"
                if old in axis:
                    axis["derivative_interval_arcsec_per_TDB_day"] = axis.pop(old)
        nominal_quality = quality(temporary)
        nominal_quality.pop("TDB_day_not_certified_TT_day")
        nominal_quality["requested_TT_axis_not_internal_time_certified"] = True
        result["nominal_same_order_control"] = {
            "all_windows": fitted,
            "quality": nominal_quality,
            "physical_TT_derivative_certified": False,
        }
    else:
        result["nominal_same_order_control"] = {
            "status": "full_observer_label_population_unqualified",
            "required_nodes": 577,
        }
    if cohort == "A":
        original = {}
        old_queries = json.loads(
            (run / "retained/old-A-observer-queries.json").read_text()
        )
        current = {q["id"]: q for q in plan["queries"] if q["cohort"] == "A"}
        for query in old_queries:
            corresponding = current["NATIVE-" + query["id"]]
            for key in (
                "TIME_TYPE",
                "CAL_TYPE",
                "TIME_DIGITS",
                "CAL_FORMAT",
                "TLIST_TYPE",
                "TLIST",
            ):
                if query["parameters"][key] != corresponding["parameters"][key]:
                    raise ValueError("Original A time batch changed")
            raw = (run / "old-A-responses" / (query["id"] + ".raw")).read_bytes()
            receipt = json.loads(
                (run / "old-A-responses" / (query["id"] + ".receipt.json")).read_text()
            )
            if (
                receipt["status"] != 200
                or hashlib.sha256(raw).hexdigest() != receipt["raw_sha256"]
            ):
                raise ValueError("Original observer response changed")
            original.update(
                {int(o): v for o, v in observer_angles(raw, query, plan).items()}
            )
        if set(original) != set(angles):
            raise ValueError("Old A population changed")
        result["old_A_apparent_angle_comparison"] = [
            {
                "offset_seconds": o,
                "old": original[o],
                "native": angles[o],
                "exact_text_match": original[o] == angles[o],
            }
            for o in sorted(angles)
        ]
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--cohort", required=True, choices=("A", "B"))
    p.add_argument("--stage", required=True, choices=("clocks", "fit"))
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    save(
        args.output,
        (clocks if args.stage == "clocks" else references)(args.run, args.cohort),
    )


if __name__ == "__main__":
    main()
