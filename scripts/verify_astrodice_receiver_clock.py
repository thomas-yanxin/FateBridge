"""Independent raw clock construction, direct-basis inverses and bit lattices.

Does not import the reception-clock producer or its emission analyzer. Existing
direct-basis/Bernstein proof code rechecks each new range inversion and lattice.
"""

import argparse
import hashlib
import json
import urllib.parse
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_emission_epoch import infer_proof
from scripts.verify_astrodice_observer_timescale import inspect
from scripts.verify_astrodice_observer_timescale import verify as verify_previous
from scripts.verify_astrodice_vector_clock import observed_bounds
from scripts.verify_astrodice_vector_clock import verify as verify_vector


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def expected_receiver(row, calibration, model, profile, plan):
    if model == "vector_TT_source_epoch":
        return {"status": "available", "calibration": calibration}
    if model != "quantity30_current_leap_hold":
        raise ValueError("Unplanned receiver")
    label = Q(row["nominal_JD"])
    if label < Q(plan["quantity30_modern_cutoff_JD"]):
        return {"status": "not_assessed_pre_1962"}
    field = row["TDB_minus_UT_seconds"]
    if field is None:
        return {"status": "time_field_unavailable"}
    delta = observed_bounds(
        field, plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
    )
    offset = Q(plan["latest_known_TAI_minus_UTC_seconds"]) + Q(
        plan["TT_minus_TAI_seconds"]
    )
    if offset != Q(plan["future_current_leap_hold_hypothesis_seconds"]):
        raise ValueError("Leap-hold sum changed")
    return {
        "status": "available",
        "calibration": {
            "status": "bracketed",
            "effective_JD": [str(label + (v - offset) / 86400) for v in delta],
            "all_six_compatible": False,
        },
    }


def verify(run, cohort):
    planraw = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(planraw)
    for name, expected in {
        **plan["inputs_sha256"],
        **json.loads((run / "implementation-before-analysis.json").read_text()),
    }.items():
        if digest((run / name).read_bytes()) != expected:
            raise ValueError("Frozen input changed: " + name)
    rawanalysis = (run / (cohort + "-first-analysis.json")).read_bytes()
    data = json.loads(rawanalysis)
    if (
        data["plan_sha256"] != digest(planraw)
        or data["cohort"] != cohort
        or any(
            data[k]
            for k in (
                "candidate_calls",
                "new_candidate_holdouts",
                "physical_time_model_certified",
                "numerical_tubes_certified",
                "internal_emission_algorithm_certified",
                "full_goal_complete",
            )
        )
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Conditional receiver experiment promoted to acceptance")
    # Recheck all original field mismatches and geometric failures; none are replaced.
    for prior_cohort in ("A", "B"):
        verify_previous(run / "controls", prior_cohort)
    specs = plan["development_groups"] if cohort == "A" else [plan["heldout_group"]]
    if cohort == "B":
        verify_vector(run / plan["heldout_group"]["calibration_root"], "B")
        for p in (run, run / plan["heldout_group"]["calibration_root"]):
            before = json.loads((p / "before-B-queries.json").read_text())
            if before["plan_sha256"] != digest(
                (p / "plan-before-queries.json").read_bytes()
            ) or before["prior_A_analysis_sha256"] != digest(
                (run / "A-first-analysis.json").read_bytes()
            ):
                raise ValueError("B phase lost its prequery plan/A binding")
            if before["collector_sha256"] != digest(
                (p / "frozen-source/scripts/astrodice_vector_clock.py").read_bytes()
            ):
                raise ValueError(
                    "B actual collector differs from frozen implementation"
                )
        if (
            run / plan["heldout_group"]["calibration_root"] / "A-first-analysis.json"
        ).read_bytes() != (run / "A-first-analysis.json").read_bytes():
            raise ValueError("Geometric B collector used a different A phase")
    expected_groups = []
    for spec in specs:
        sp = json.loads(
            (run / spec["observation_root"] / "plan-before-queries.json").read_text()
        )
        expected_groups.extend(
            (spec, q, sp)
            for q in sp["queries"]
            if q["cohort"] == spec["cohort"] and q["time_type"] == "TT"
        )
    if len(expected_groups) != len(data["groups"]):
        raise ValueError("Original observer group dropped")
    endpoints = candidates = 0
    summary = []
    for stored, (spec, query, sp) in zip(data["groups"], expected_groups):
        obsroot = run / spec["observation_root"]
        calpath = (
            run / spec["calibration_root"] / (spec["cohort"] + "-first-analysis.json")
        )
        raw = (obsroot / "responses" / (query["id"] + ".raw")).read_bytes()
        receipt = json.loads(
            (obsroot / "responses" / (query["id"] + ".receipt.json")).read_text()
        )
        if (
            any(stored[k] != spec[k] for k in spec)
            or stored["query_id"] != query["id"]
            or stored["raw_sha256"] != digest(raw)
            or receipt["raw_sha256"] != digest(raw)
            or stored["calibration_sha256"] != digest(calpath.read_bytes())
            or receipt["url"]
            != "https://ssd.jpl.nasa.gov/api/horizons.api?"
            + urllib.parse.urlencode(query["parameters"])
            or receipt["attempt"] != 1
            or receipt["verification_disabled"]
        ):
            raise ValueError("Raw request, original source, or group binding changed")
        cases = sp["cohorts"][spec["cohort"]]
        parsed = inspect(raw, receipt["status"], query, cases, sp)
        if stored["status"] != parsed["status"]:
            raise ValueError("Original response status changed")
        if parsed["status"] != "supported":
            if stored["rows"]:
                raise ValueError("Unavailable observer response promoted")
            summary.append({"query": query["id"], "status": parsed["status"]})
            continue
        calquery = next(
            q
            for q in json.loads(calpath.read_text())["queries"]
            if q["id"] == query["id"]
        )
        calibrations = {r["case_id"]: r for r in calquery["rows"]}
        if len(stored["rows"]) != len(parsed["rows"]):
            raise ValueError("Original primary or auxiliary row dropped")
        counts = {
            p: {
                m: {
                    "primary": 0,
                    "available": 0,
                    "not_assessed_pre_1962": 0,
                    "time_field_unavailable": 0,
                    "inferred": 0,
                    "continuous_overlap": 0,
                    "lattices": {
                        t: {"unique": 0, "refuted": 0, "multi_or_unknown": 0}
                        for t in plan["lattice_coordinate_models"]
                    },
                }
                for m in plan["receiver_models"]
            }
            for p in plan["numerical_tube_profiles"]
        }
        for row, record in zip(parsed["rows"], stored["rows"]):
            if {k: record[k] for k in row} != row:
                raise ValueError("Printed measurements or row identity changed")
            if set(record["profiles"]) != set(plan["numerical_tube_profiles"]):
                raise ValueError("Printing profile missing")
            case = next(c for c in cases if c["id"] == row["case_id"])
            primary = case["role"] != "auxiliary_not_primary"
            for profile, models in record["profiles"].items():
                if set(models) != set(plan["receiver_models"]):
                    raise ValueError("Receiver hypothesis dropped")
                for model, value in models.items():
                    expected = expected_receiver(
                        row,
                        calibrations[row["case_id"]]["profiles"][profile],
                        model,
                        profile,
                        plan,
                    )
                    if {k: v for k, v in value.items() if k != "inference"} != expected:
                        raise ValueError("Receiver clock construction differs")
                    stat = counts[profile][model]
                    stat["primary"] += primary
                    if expected["status"] != "available":
                        stat[expected["status"]] += primary
                        if "inference" in value:
                            raise ValueError(
                                "Unknown clock promoted to source inversion"
                            )
                        continue
                    stat["available"] += primary
                    inf = value["inference"]
                    if inf["status"] == "source_model_unknown":
                        raise ValueError(
                            "Unverified source failure cannot bypass independent proof"
                        )
                    n, c = infer_proof(
                        run, case, row, expected["calibration"], profile, inf, plan
                    )
                    endpoints += n
                    candidates += c
                    if inf["status"] != "inferred":
                        continue
                    stat["inferred"] += primary
                    stat["continuous_overlap"] += (
                        primary and inf["continuous_necessary_overlap"]
                    )
                    for t, grid in inf["lattices"].items():
                        s = stat["lattices"][t]
                        s["unique"] += primary and grid["unique_not_refuted"]
                        s["refuted"] += primary and grid["conditional_refuted"]
                        s["multi_or_unknown"] += primary and not (
                            grid["unique_not_refuted"] or grid["conditional_refuted"]
                        )
        summary.append(
            {"source_cohort": spec["cohort"], "query": query["id"], "profiles": counts}
        )
    return {
        "method": "independent_raw_receiver_direct_basis_inverse_bit_lattice_v1",
        "cohort": cohort,
        "analysis_sha256": digest(rawanalysis),
        "groups": summary,
        "exact_inverse_endpoint_checks": endpoints,
        "candidate_enclosure_checks": candidates,
        "exit_code": 0,
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cohort", choices=["A", "B"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with args.output.open("x") as stream:
        json.dump(verify(args.run, args.cohort), stream, indent=2)
        stream.write("\n")
