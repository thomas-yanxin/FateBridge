"""Joint receiver/emitter endpoint transfer on a declared uniform source clock.

Targets are defined in source coordinates. No TT clock fit is inferred, and
all previous observations, printing intervals and emission controls remain.
"""

import argparse
import hashlib
import json
from fractions import Fraction as Q
from itertools import product
from pathlib import Path

from scripts.astrodice_clock_interval import (
    A,
    I,
    Reader,
    dot,
    norm,
    scale,
    sub,
    unit,
)
from scripts.astrodice_emission_transfer import (
    K,
    aberration,
    box,
    continuous_emission,
    segment_clearance,
    signed_rates,
    solar_deflection,
)
from scripts.astrodice_observer_clock import observed_direction
from scripts.astrodice_source_slope_bounds import pi_bounds

DESIGN_SHA = "072c72e5a9f00d79107063aaf577b636fc693998316d989bb794a7463330c517"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geometry(reader, reception, emission, receiver_seed=0, emitter_seed=0):
    tr, te = A(reception, receiver_seed), A(emission, emitter_seed)
    earth = reader.state(tr, "Earth")
    target = reader.state(te, "Venus")
    sun = reader.state(tr, "Sun")
    emitted_sun = reader.state(te, "Sun")
    ray = sub(target[:3], earth[:3])
    p = unit(ray)
    es = sub(earth[:3], sun[:3])
    re, e = norm(es), unit(es)
    clearance, branch = segment_clearance(es, ray)
    if clearance.bounds()[0] <= Q(1, 100):
        raise ValueError("Receiver transfer outside fixed point-Sun domain")
    beta = scale(earth[3:], K)
    solar = {
        "exact_emission": emitted_sun[:3],
        "linearized_emission": sub(sun[:3], scale(sun[3:], tr - te)),
    }
    q = {name: unit(sub(target[:3], value)) for name, value in solar.items()}
    return p, q, re, e, beta, clearance, branch


def models(prepared, emission_design):
    p, q, re, e, beta, _, _ = prepared
    result = []
    for sr, sun_epoch, potential in product(
        emission_design["SR_models"],
        emission_design["sun_epoch_models"],
        emission_design["potential_terms"],
    ):
        deflected, denominator = solar_deflection(p, q[sun_epoch], e, re)
        proper = aberration(deflected, beta, re, sr, potential)
        result.append(((sr, sun_epoch, potential), proper, denominator))
    return result


def atan_small(ratio, plan):
    if (
        ratio.absolute_upper() >= Q(plan["maximum_absolute_atan_argument"])
        or plan["atan_terms"] != 4
    ):
        raise ValueError("Endpoint angle outside fixed small-angle domain")
    value = I()
    power = ratio
    square = ratio.square()
    for k in range(4):
        value += ((-1) ** k) * power / (2 * k + 1)
        power *= square
    remainder = ratio.absolute_upper() ** 9 / 9
    return value + I(-remainder, remainder)


def angle_change(before, after, plan):
    x0, y0, z0 = [v.v for v in before]
    x1, y1, z1 = [v.v for v in after]
    rho0, rho1 = (x0.square() + y0.square()).sqrt(), (x1.square() + y1.square()).sqrt()
    if min(rho0.square().bounds()[0], rho1.square().bounds()[0]) <= Q(
        plan["minimum_rho_squared"]
    ):
        raise ValueError("Endpoint angular chart too close to pole")
    numerators = [x0 * y1 - y0 * x1, rho0 * z1 - z0 * rho1]
    denominators = [x0 * x1 + y0 * y1, rho0 * rho1 + z0 * z1]
    if any(d.bounds()[0] <= 0 for d in denominators):
        raise ValueError("Endpoint angular lift not certified")
    factor = Q(648000) / I(*pi_bounds())
    return [atan_small(n / d, plan) * factor for n, d in zip(numerators, denominators)]


def implicit_factor(reader, reception, emission, plan):
    earth = reader.state(A(reception), "Earth")
    target = reader.state(A(emission), "Venus")
    p = unit(sub(target[:3], earth[:3]))
    numerator = 1 + dot(p, earth[3:]).v * K
    denominator = 1 + dot(p, target[3:]).v * K
    if denominator.bounds()[0] <= Q(
        plan["minimum_implicit_emission_derivative_denominator"]
    ):
        raise ValueError("Implicit emission derivative domain unqualified")
    return numerator / denominator, denominator


def transfer(source, case, observation, old, center_receiver, plan, emission_design):
    reception = Q(old["reception_JD"])
    discrete = Q(old["emission_JD"])
    target_receiver = center_receiver + Q(case["offset_seconds"], 86400)
    shift = (target_receiver - reception) * 86400
    if abs(shift) >= Q(plan["maximum_receiver_shift_seconds"]):
        raise ValueError("Receiver shift exceeds fixed domain")
    reader = Reader(source, case["window_index"])
    target_emission, root_proof = continuous_emission(
        reader, target_receiver, discrete, emission_design
    )
    original_geometry = geometry(reader, I(reception), I(discrete))
    target_geometry = geometry(reader, I(target_receiver), target_emission)
    original_models = models(original_geometry, emission_design)
    target_models = models(target_geometry, emission_design)
    observed = [A(v) for v in observed_direction(observation["apparent_angles"], 0, 80)]
    rates = None
    factor = denominator = None
    if case["offset_seconds"] == 0:
        factor, denominator = implicit_factor(
            reader, I(target_receiver), target_emission, plan
        )
        rate_geometry = geometry(reader, I(target_receiver), target_emission, 1, factor)
        rates = models(rate_geometry, emission_design)
    changes = []
    for i, ((identity, before, db), (identity2, after, da)) in enumerate(
        zip(original_models, target_models)
    ):
        if identity != identity2:
            raise ValueError("Endpoint model identity changed")
        correction = angle_change(before, after, plan)
        residual = angle_change(observed, before, plan)
        item = {
            "SR_model": identity[0],
            "sun_epoch_model": identity[1],
            "potential_term": identity[2],
            "original_direction": [box(v.v) for v in before],
            "target_direction": [box(v.v) for v in after],
            "original_deflection_denominator": box(db.v),
            "target_deflection_denominator": box(da.v),
            "total_correction_arcsec": [box(v) for v in correction],
            "model_minus_observed_arcsec": [box(v) for v in residual],
            "source_model_position_line_met": all(
                v.absolute_upper() <= Q(plan["source_model_position_line_arcsec"])
                for v in residual
            ),
        }
        if rates is not None:
            if rates[i][0] != identity:
                raise ValueError("Rate model identity changed")
            item["rate_arcsec_per_source_day"] = [
                box(v) for v in signed_rates(rates[i][1])
            ]
        changes.append(item)
    union = [
        I(
            min(Q(m["total_correction_arcsec"][a][0]) for m in changes),
            max(Q(m["total_correction_arcsec"][a][1]) for m in changes),
        )
        for a in (0, 1)
    ]
    if any(
        v.absolute_upper() >= Q(plan["angular_transfer_domain_guard_arcsec"])
        for v in union
    ):
        raise ValueError("Total transfer exceeds fixed angular branch domain")
    result = {
        "case_id": case["id"],
        "offset_seconds": case["offset_seconds"],
        "original_receiver_hex": old["receiver_hex"],
        "original_emitter_hex": old["emitter_hex"],
        "original_receiver_JD": str(reception),
        "original_emitter_JD": str(discrete),
        "target_receiver_JD": str(target_receiver),
        "receiver_shift_seconds": str(shift),
        "target_emitter_root_proof": root_proof,
        "original_finite_segment_clearance_AU": box(original_geometry[-2]),
        "original_clearance_branch": original_geometry[-1],
        "target_finite_segment_clearance_AU": box(target_geometry[-2]),
        "target_clearance_branch": target_geometry[-1],
        "models": changes,
        "union_total_correction_arcsec": [box(v) for v in union],
        "original_printing_interval_arcsec": old["original_printing_interval_arcsec"],
        "total_corrected_observation_interval_arcsec": [
            box(I(*map(Q, raw)) + delta)
            for raw, delta in zip(old["original_printing_interval_arcsec"], union)
        ],
        "physical_service_model_equivalence_certified": False,
        "physical_TT_time_model_certified": False,
        "original_results_regraded": False,
    }
    if factor is not None:
        result["implicit_emitter_derivative"] = box(factor)
        result["implicit_emitter_derivative_denominator"] = box(denominator)
    return result


def analyze(native, design, cohort, emission_path, proof_path):
    if sha(design / "design-before-development.json") != DESIGN_SHA:
        raise ValueError("Receiver design changed")
    plan = json.loads((design / "design-before-development.json").read_text())
    emission_design = json.loads((design / "emission-design-original.json").read_text())
    data, proof = [json.loads(p.read_text()) for p in (emission_path, proof_path)]
    if proof["transfer_sha256"] != sha(emission_path) or proof["rows_checked"] != 577:
        raise ValueError("Full prior emission proof binding required")
    original_plan = json.loads((native / "plan-before-queries.json").read_text())
    for p, h in original_plan["inputs_sha256"].items():
        if sha(native / p) != h:
            raise ValueError("Frozen native input changed")
    original_path = native / (cohort + "-first-analysis.json")
    if data["native_analysis_sha256"] != sha(original_path):
        raise ValueError("Prior native analysis changed")
    observations = {
        r["observation"]["case_id"]: r["observation"]
        for g in json.loads(original_path.read_text())["queries"]
        for r in g["rows"]
    }
    cases = {
        c["id"]: c
        for q in original_plan["queries"]
        if q["cohort"] == cohort
        for c in q["cases"]
    }
    if [r["offset_seconds"] for r in data["rows"]] != plan["primary_offsets_seconds"]:
        raise ValueError("All 577 original nodes required")
    center = Q(
        next(r["reception_JD"] for r in data["rows"] if r["offset_seconds"] == 0)
    )
    output = {
        "cohort": cohort,
        "design_sha256": DESIGN_SHA,
        "emission_transfer_sha256": sha(emission_path),
        "independent_emission_proof_sha256": sha(proof_path),
        "native_analysis_sha256": sha(original_path),
        "center_receiver_JD": str(center),
        "rows": [],
        "new_candidate_holdouts": 0,
        "physical_service_model_equivalence_certified": False,
        "physical_TT_time_model_certified": False,
        "physical_remainder_certified": False,
        "original_results_regraded": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    for index, old in enumerate(data["rows"], 1):
        case = cases[old["case_id"]]
        output["rows"].append(
            transfer(
                native / "source-records",
                case,
                observations[case["id"]],
                old,
                center,
                plan,
                emission_design,
            )
        )
        if index % 18 == 0:
            print(cohort, "joint endpoint rows", index, flush=True)
    return output


def main():
    parser = argparse.ArgumentParser()
    for name in ("native", "design", "emission", "proof", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--cohort", choices=("A", "B"), required=True)
    args = parser.parse_args()
    result = analyze(args.native, args.design, args.cohort, args.emission, args.proof)
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
