"""Posthoc finite-emission sampling bound; no changes to reference intervals.

The bound concerns the astrometric source ray. Apparent-angle deflection and
aberration propagation and physical TT conversion remain separate premises.
"""

import argparse
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_observer_clock import (
    Source,
    add,
    independent_pi,
    length,
    root,
    rounded,
    sub,
)

K = Q(149597870700, 299792458 * 86400)


def load(run, name):
    return json.loads((run / name).read_text())


def diagnose(run, cohort):
    plan = load(run, "plan-before-queries.json")
    for name, digest in plan["inputs_sha256"].items():
        if hashlib.sha256((run / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Original source seal changed")
    data_path = run / (cohort + "-first-analysis.json")
    digest = hashlib.sha256(data_path.read_bytes()).hexdigest()
    data = load(run, cohort + "-first-analysis.json")
    proof = load(run, cohort + "-independent-clock-first.json")
    if proof["clock_analysis_sha256"] != digest or proof["primary_nodes"] != 577:
        raise ValueError("Full native clock proof not available or changed")
    cases = {
        c["id"]: c for q in plan["queries"] if q["cohort"] == cohort for c in q["cases"]
    }
    pairs = {}
    windows = set()
    for group in data["queries"]:
        for record in group["rows"]:
            observation = record["observation"]
            case = cases[observation["case_id"]]
            if case["role"] == "auxiliary_not_primary":
                continue
            found = []
            for profile in ("printing_only", "printing_plus_64_ULP_hypothesis"):
                model = record["inference"]["profiles"][profile][
                    "seconds_from_J2000_binary64"
                ]
                for hypothesis in ("one_round_source_norm", "two_round_source_norm"):
                    values = model["qualified_pairs_by_hypothesis"][hypothesis]
                    if (
                        model["status"] != "complete"
                        or len(values) != 1
                        or not observation["original_label_budget_pass"]
                    ):
                        raise ValueError(
                            "Full common native population is not qualified"
                        )
                    found.append(values[0])
            if any(v != found[0] for v in found):
                raise ValueError("No common model: retain ambiguity rather than choose")
            tr, te = found[0]
            model = record["inference"]["profiles"]["printing_only"][
                "seconds_from_J2000_binary64"
            ]
            candidate = next(
                c
                for c in model["candidates"]
                if [c["receiver_hex"], c["emitter_hex"]] == [tr, te]
            )
            squared_delay = Q(candidate["delay_raw_squared"])
            residual = add(
                rounded(Q(float.fromhex(te)) - Q(float.fromhex(tr))),
                root(rounded(squared_delay)),
            )
            pairs[case["offset_seconds"]] = {
                "offset_seconds": case["offset_seconds"],
                "receiver_hex": tr,
                "emitter_hex": te,
                "emission_equation_residual_seconds": list(map(str, residual)),
            }
            windows.add(case["window_index"])
    if sorted(pairs) != list(range(-1440, 1441, 5)) or len(windows) != 1:
        raise ValueError("Full single-context 577-node population required")
    receivers = [
        Q(float.fromhex(v["receiver_hex"])) / 86400 + 2451545 for v in pairs.values()
    ]
    emitters = [
        Q(float.fromhex(v["emitter_hex"])) / 86400 + 2451545 for v in pairs.values()
    ]
    receiver_box = min(receivers), max(receivers)
    emission_box = min(emitters) - Q(2, 86400), max(emitters) + Q(2, 86400)
    source = Source(run / "source-records", windows.pop())
    earth = source.state(rounded(*receiver_box), "Earth")
    venus = source.state(rounded(*emission_box), "Venus")
    speed = length(venus[3:])[1]
    distance = length([sub(v, e) for v, e in zip(venus[:3], earth[:3])])[0]
    contraction = K * speed
    if distance <= 0 or contraction >= 1:
        raise ValueError("Declared source domain cannot certify the bound")
    residual = max(
        abs(Q(v))
        for row in pairs.values()
        for v in row["emission_equation_residual_seconds"]
    )
    continuous_root_error = residual / (1 - contraction)
    if continuous_root_error > 2:
        raise ValueError("Continuous-root bound exceeds fixed two-second source domain")
    angular = (
        speed
        * (continuous_root_error / 86400)
        / distance
        * (180 * 3600 / independent_pi()[0])
    )
    return {
        "cohort": cohort,
        "native_clock_analysis_sha256": digest,
        "primary_nodes": 577,
        "scope": "Posthoc conditional Newtonian source-ray sampling bound; not a heldout accuracy acceptance.",
        "receiver_JD_support": list(map(str, receiver_box)),
        "emission_JD_support_including_fixed_2_seconds": list(map(str, emission_box)),
        "Venus_velocity_AU_per_day_bounds": [list(map(str, v)) for v in venus[3:]],
        "Venus_speed_upper_AU_per_day": str(speed),
        "source_ray_distance_lower_AU": str(distance),
        "light_time_contraction_upper": str(contraction),
        "maximum_emission_equation_residual_seconds": str(residual),
        "continuous_emission_root_error_upper_seconds": str(continuous_root_error),
        "astrometric_sampling_angle_upper_arcsec": str(angular),
        "rows": [pairs[o] for o in sorted(pairs)],
        "apparent_angle_quantization_bound_certified": False,
        "physical_TT_time_model_certified": False,
        "reference_error_budget_changed": False,
        "original_reference_results_regraded": False,
        "new_candidate_holdouts": 0,
        "full_goal_complete": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--cohort", required=True, choices=("A", "B"))
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    result = diagnose(args.run, args.cohort)
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
