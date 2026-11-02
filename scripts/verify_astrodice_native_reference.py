"""Independent full-577 source and all-point polynomial certificate replay."""

import argparse
import csv
import hashlib
import json
from fractions import Fraction as Q
from itertools import combinations
from pathlib import Path

from scripts.verify_astrodice_earth_clock import wire
from scripts.verify_astrodice_geocentric_meanvalue import (
    FAMILIES,
    HYPOTHESES,
    check_inference,
    raw_rows,
)
from scripts.verify_astrodice_nonuniform_reference import (
    bound_proof,
    independent_system,
)


def load(root, name):
    return json.loads((root / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(run, cohort, name):
    plan = load(run, "plan-before-queries.json")
    if plan["windows_seconds"] != [
        1440,
        1080,
        810,
        600,
        450,
        330,
        240,
        180,
        130,
        90,
        60,
    ] or plan["original_lines"] != {
        "position_arcsec": "0.02",
        "daily_rate_arcsec_per_day": "0.002",
        "reference_quality_arcsec_per_day": "0.002",
    }:
        raise ValueError("Original fixed windows or error lines changed")
    if {
        k: v["extra_binary64_ULPs"] for k, v in plan["numerical_tube_profiles"].items()
    } != {"printing_only": 0, "printing_plus_64_ULP_hypothesis": 64}:
        raise ValueError("Numerical tube population changed")
    for p, digest in plan["inputs_sha256"].items():
        if sha(run / p) != digest:
            raise ValueError("Frozen input changed: " + p)
    data = load(run, name)
    if data["cohort"] != cohort or data["plan_sha256"] != sha(
        run / "plan-before-queries.json"
    ):
        raise ValueError("Cohort or plan changed")
    false_fields = (
        "candidate_calls",
        "new_candidate_holdouts",
        "numerical_tubes_certified",
        "physical_time_model_certified",
        "internal_algorithm_certified",
        "TT_derivative_certified",
        "physical_remainder_certified",
        "original_odd_polynomial_gate_replaced",
        "full_goal_complete",
    )
    if (
        any(data[k] for k in false_fields)
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Conditional evidence promoted")
    if (
        not data["monotone_pair_partition"]
        or data["receiver_enclosure_method"]
        != "uniform_mean_value_necessary_enclosure_v1"
    ):
        raise ValueError("Native source method changed")
    return plan, data


def clocks(run, cohort):
    plan, data = inputs(run, cohort, cohort + "-first-analysis.json")
    queries = [q for q in plan["queries"] if q["cohort"] == cohort]
    if [q["id"] for q in queries] != [g["id"] for g in data["queries"]]:
        raise ValueError("Query coverage changed")
    folder = run / "query-proofs"
    folder.mkdir(exist_ok=True)
    endpoints = candidates = population = excluded = row_count = 0
    offsets = []
    for query, group in zip(queries, data["queries"]):
        raw, receipt = wire(run, query)
        if receipt["status"] != 200:
            raise ValueError("Observer source unavailable")
        rows = raw_rows(raw, query, plan)
        if len(rows) != len(group["rows"]):
            raise ValueError("Observer rows dropped")
        if load(run, "query-results/" + query["id"] + "-first.json") != group:
            raise ValueError("First query output changed")
        ge = gp = gc = gx = 0
        for row, record in zip(rows, group["rows"]):
            if row != record["observation"]:
                raise ValueError("Observer values changed")
            case = next(c for c in query["cases"] if c["id"] == row["case_id"])
            if case["role"] != "auxiliary_not_primary":
                offsets.append(case["offset_seconds"])
            e, p = check_inference(run, case, row, record["inference"], plan)
            ge += e
            gp += p
            for models in record["inference"]["profiles"].values():
                for model in models.values():
                    gc += model.get("enumerated_pair_count", 0)
                    gx += model.get("partition", {}).get("excluded_pair_count", 0)
        result = {
            "id": query["id"],
            "rows_checked": len(rows),
            "source_enclosure_endpoint_checks": ge,
            "retained_source_pairs_checked": gp,
            "complete_pair_population": gc,
            "pairs_excluded_by_monotone_certificate": gx,
        }
        with (folder / (query["id"] + "-first.json")).open("x") as f:
            json.dump(result, f, indent=2)
            f.write("\n")
        endpoints += ge
        candidates += gp
        population += gc
        excluded += gx
        row_count += len(rows)
        print(query["id"], "independent rows", len(rows), flush=True)
    if sorted(offsets) != list(range(-1440, 1441, 5)):
        raise ValueError("Complete 577-node population required")
    return {
        "cohort": cohort,
        "clock_analysis_sha256": sha(run / (cohort + "-first-analysis.json")),
        "primary_nodes": 577,
        "raw_rows_checked": row_count,
        "source_enclosure_endpoint_checks": endpoints,
        "retained_source_pairs_checked": candidates,
        "complete_pair_population": population,
        "pairs_excluded_by_monotone_certificate": excluded,
        "physical_time_model_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


def fit_proof(angles, epochs, saved, windows, nominal=False):
    if [(w["window_seconds"], w["full_degree"]) for w in saved["all_windows"]] != [
        (w, d) for w in windows for d in (5, 7)
    ]:
        raise ValueError("Fixed windows/degrees changed")
    count = 0
    key = (
        "derivative_interval_arcsec_per_nominal_TT_day"
        if nominal
        else "derivative_interval_arcsec_per_TDB_day"
    )
    for window in saved["all_windows"]:
        w, d = window["window_seconds"], window["full_degree"]
        if len(window["axes"]) != 2:
            raise ValueError("An angular axis was dropped")
        for axis, record in enumerate(window["axes"]):
            a, b, base, scale = independent_system(angles, epochs, w, d, axis)
            if (
                record["axis"] != axis
                or record["baseline"] != list(map(str, base))
                or Q(record["scale_arcsec"]) != scale
                or record["points_used"] != len(a) // 2
            ):
                raise ValueError("All-point polynomial input changed")
            certs = record["certificates"]
            if len(certs) != 2:
                raise ValueError("Certificate population changed")
            if all(c["status"] == "exact_primal_dual_optimum" for c in certs):
                if [c["objective_sign"] for c in certs] != [1, -1]:
                    raise ValueError("LP objective directions changed")
                low = (base[1] + scale * bound_proof(a, b, certs[0])) * 86400 / w
                high = (base[1] - scale * bound_proof(a, b, certs[1])) * 86400 / w
                if record[key] != list(map(str, (low, high))):
                    raise ValueError("Exact derivative bounds changed")
                count += 2
            elif key in record:
                raise ValueError("Unresolved certificate promoted")
        valid = all(key in r for r in window["axes"])
        if (
            window["status"]
            != (
                "conditional_exact_polynomial_interval"
                if valid
                else "polynomial_reference_unresolved"
            )
            or window["physical_remainder_certified"]
        ):
            raise ValueError("Polynomial claim promoted")
    lookup = {(r["window_seconds"], r["full_degree"]): r for r in saved["all_windows"]}
    checks = []
    selected = None
    for i in range(len(windows) - 2):
        triple = windows[i : i + 3]
        records = [lookup[w, d] for w in triple for d in (5, 7)]
        complete = all(
            r["status"] == "conditional_exact_polynomial_interval" for r in records
        )
        spread = radius = None
        if complete:
            bounds = [[tuple(map(Q, axis[key])) for axis in r["axes"]] for r in records]
            mids = [[(a + b) / 2 for a, b in box] for box in bounds]
            spread = max(
                sum(((a - b) ** 2 for a, b in zip(u, v)), Q())
                for u, v in combinations(mids, 2)
            )
            radius = max(
                sum((((b - a) / 2) ** 2 for a, b in box), Q()) for box in bounds
            )
        accepted = complete and spread <= Q(1, 500) ** 2 and radius <= Q(1, 500) ** 2
        checks.append(
            {
                "windows_seconds": triple,
                "complete_exact_certificates": complete,
                "maximum_coordinate_midpoint_distance_squared": (
                    str(spread) if complete else None
                ),
                "maximum_coordinate_radius_squared": str(radius) if complete else None,
                "conditional_quality_met": accepted,
            }
        )
        if accepted and selected is None:
            selected = {"window_seconds": triple[1], "full_degree": 7}
    expected = {
        "status": (
            "conditional_quality_met" if selected else "reference_quality_unresolved"
        ),
        "selected": selected,
        "all_window_checks": checks,
        "fixed_line_arcsec_per_day": "0.002",
        "coordinate_norm_conservative_for_tangent_direction": True,
        "production_reference_qualified": False,
    }
    expected[
        (
            "requested_TT_axis_not_internal_time_certified"
            if nominal
            else "TDB_day_not_certified_TT_day"
        )
    ] = True
    if saved["quality"] != expected:
        raise ValueError("Fixed-line quality rule changed")
    return count


def references(run, cohort):
    plan, fitted = inputs(run, cohort, cohort + "-native-reference-first.json")
    _, data = inputs(run, cohort, cohort + "-first-analysis.json")
    source_proof = load(run, cohort + "-independent-clock-first.json")
    if (
        source_proof["clock_analysis_sha256"]
        != sha(run / (cohort + "-first-analysis.json"))
        or source_proof["primary_nodes"] != 577
    ):
        raise ValueError("Native clock proof binding changed")
    records = {}
    for group in data["queries"]:
        query = next(q for q in plan["queries"] if q["id"] == group["id"])
        raw, _ = wire(run, query)
        original = raw_rows(raw, query, plan)
        for row, record in zip(original, group["rows"]):
            if row != record["observation"]:
                raise ValueError("Source observation changed after clock proof")
            case = next(c for c in query["cases"] if c["id"] == row["case_id"])
            if case["role"] != "auxiliary_not_primary":
                if case["offset_seconds"] in records:
                    raise ValueError("Repeated primary node")
                records[case["offset_seconds"]] = record
    if sorted(records) != list(range(-1440, 1441, 5)) or fitted["primary_nodes"] != 577:
        raise ValueError("Full polynomial population required")
    angles = {o: r["observation"]["apparent_angles"] for o, r in records.items()}
    expected_models = [
        (p, f, h)
        for p in plan["numerical_tube_profiles"]
        for f in FAMILIES
        for h in HYPOTHESES
    ]
    if [
        (m["profile"], m["coordinate_family"], m["rounding_hypothesis"])
        for m in fitted["models"]
    ] != expected_models:
        raise ValueError("A profile, grid or rounding model was dropped")
    required_fits = {}
    for entry, (profile, family, hypothesis) in zip(fitted["models"], expected_models):
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
                value = Q(float.fromhex(pairs[0][0]))
                epochs[offset] = value * 86400 if family == FAMILIES[0] else value
        if (
            rows != entry["population"]
            or entry["required_nodes"] != 577
            or entry["qualified_nodes"] != len(epochs)
        ):
            raise ValueError("Native model population changed")
        if len(epochs) != 577:
            if (
                entry["status"] != "full_clock_population_unqualified"
                or "fit_input_sha256" in entry
            ):
                raise ValueError("Partial population promoted to a fit")
            continue
        payload = json.dumps(
            {
                "angles": angles,
                "source_seconds": {o: str(t) for o, t in sorted(epochs.items())},
            },
            sort_keys=True,
        ).encode()
        key = hashlib.sha256(payload).hexdigest()
        if (
            entry["status"] != "conditional_native_source_fit"
            or entry["fit_input_sha256"] != key
        ):
            raise ValueError("Source epoch binding changed")
        required_fits[key] = epochs
    if set(fitted["fits_by_input_sha256"]) != set(required_fits):
        raise ValueError("Extra or omitted fit population")
    certified = sum(
        fit_proof(
            angles, epochs, fitted["fits_by_input_sha256"][key], plan["windows_seconds"]
        )
        for key, epochs in required_fits.items()
    )
    control = fitted["nominal_same_order_control"]
    if all(r["observation"]["original_label_budget_pass"] for r in records.values()):
        certified += fit_proof(
            angles, {o: Q(o) for o in records}, control, plan["windows_seconds"], True
        )
        if control["physical_TT_derivative_certified"]:
            raise ValueError("Nominal coordinate promoted to physical clock")
    elif control != {
        "status": "full_observer_label_population_unqualified",
        "required_nodes": 577,
    }:
        raise ValueError("Invalid nominal full-population control")
    if cohort == "A":
        old_angles = {}
        for query in load(run, "retained/old-A-observer-queries.json"):
            payload = json.loads(
                (run / "old-A-responses" / (query["id"] + ".raw")).read_bytes()
            )
            text = payload["result"].split("$$SOE")[1].split("$$EOE")[0]
            for values in csv.reader(text.strip().splitlines()):
                c = [v.strip() for v in values]
                matches = [
                    case
                    for case in query["cases"]
                    if abs(Q(c[1]) - Q(case["nominal_JD"])) <= Q(1, 10**9)
                ]
                if len(c) != 7 or len(matches) != 1:
                    raise ValueError("Old A raw binding changed")
                case = matches[0]
                if case["role"] != "auxiliary_not_primary":
                    old_angles[case["offset_seconds"]] = c[4:6]
        expected = [
            {
                "offset_seconds": o,
                "old": old_angles[o],
                "native": angles[o],
                "exact_text_match": old_angles[o] == angles[o],
            }
            for o in sorted(angles)
        ]
        if fitted["old_A_apparent_angle_comparison"] != expected:
            raise ValueError("Old apparent reference comparison changed")
    return {
        "cohort": cohort,
        "primary_nodes": 577,
        "independent_native_clock_proof_sha256": sha(
            run / (cohort + "-independent-clock-first.json")
        ),
        "reference_analysis_sha256": sha(
            run / (cohort + "-native-reference-first.json")
        ),
        "distinct_full_source_fit_inputs": len(required_fits),
        "exact_LP_certificates_checked": certified,
        "physical_remainder_certified": False,
        "TT_derivative_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--cohort", required=True, choices=("A", "B"))
    p.add_argument("--stage", required=True, choices=("clocks", "fit"))
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    value = (clocks if args.stage == "clocks" else references)(args.run, args.cohort)
    with args.output.open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
