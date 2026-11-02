"""Conditional finite-emission correction, with all declared model variants.

Raw observations and their printed intervals stay intact. No result here
certifies Horizons implementation equivalence or a physical TT/TDB model.
"""

import argparse
import hashlib
import json
from decimal import Decimal
from fractions import Fraction as Q
from itertools import product
from pathlib import Path

from scripts.astrodice_clock_interval import (
    A,
    I,
    Reader,
    add,
    cross,
    dot,
    norm,
    scale,
    sub,
    unit,
)
from scripts.astrodice_source_slope_bounds import pi_bounds

K = Q(149597870700, 299792458 * 86400)
SRS = Q("0.0000000197412574336")


def box(value):
    return list(map(str, value.bounds()))


def state(reader, epoch, body, derivative=0):
    return reader.state(A(epoch, derivative), body)


def signed_rates(vector):
    x, y, z = vector
    rho2 = x.v.square() + y.v.square()
    if rho2.bounds()[0] <= Q(1, 10**8):
        raise ValueError("Apparent direction too close to coordinate pole")
    rho = rho2.sqrt()
    alpha = (x.v * y.d - y.v * x.d) / rho2
    drho = (x.v * x.d + y.v * y.d) / rho
    delta = (rho * z.d - z.v * drho) / (rho2 + z.v.square())
    factor = Q(648000) / I(*pi_bounds())
    return [alpha * factor, delta * factor]


def aberration(p, beta, re, model, potential):
    b2 = dot(beta, beta)
    if b2.v.bounds()[1] >= Q(1, 10000):
        raise ValueError("Observer speed outside declared SR domain")
    pb = dot(p, beta)
    if model == "full_Lorentz":
        bm1 = (1 - b2).sqrt()
        result = add(scale(p, bm1), scale(beta, 1 + pb / (1 + bm1)))
    elif model == "normalized_second_order":
        result = add(scale(p, 1 - pb + pb * pb - b2 / 2), scale(beta, 1 - pb / 2))
    else:
        raise ValueError("Unplanned aberration convention")
    if potential not in (0, 1):
        raise ValueError("Unplanned potential convention")
    result = add(result, scale(sub(beta, scale(p, pb)), potential * SRS / re))
    return unit(result)


def light_deflection(p, q, e, re, mass=Q(1), limiter=Q(0)):
    """ERFA finite-source ld algebra; returned vector is not normalized."""
    denominator = dot(q, add(q, e))
    lo, hi = denominator.v.bounds()
    if hi < limiter:
        denominator = A(limiter)
    elif lo < limiter:
        raise ValueError("Deflection limiter branch unresolved")
    result = add(p, scale(cross(p, cross(e, q)), mass * SRS / re / denominator))
    return result, denominator


def solar_deflection(p, q, e, re):
    result, denominator = light_deflection(p, q, e, re)
    if denominator.v.bounds()[0] <= Q(1, 100):
        raise ValueError("Deflection denominator outside declared domain")
    return unit(result), denominator


def continuous_emission(reader, reception, emission, plan):
    radius = Q(plan["initial_emitter_radius_seconds"]) / 86400
    initial = I(emission - radius, emission + radius)
    earth = state(reader, I(reception), "Earth")[:3]
    broad = state(reader, initial, "Venus")
    speed = norm(broad[3:]).v.absolute_upper()
    contraction = speed * K
    if contraction >= 1:
        raise ValueError("Newtonian emission map not certified contractive")

    def image(epoch):
        ray = sub(state(reader, epoch, "Venus")[:3], earth)
        return I(reception) - norm(ray).v * K

    first = image(initial)
    a, b = initial.bounds()
    u, v = first.bounds()
    if not a <= u <= v <= b:
        raise ValueError("Initial fixed emission domain is not invariant")
    saved = {
        "initial_JD": box(initial),
        "contraction_upper": str(contraction),
        "initial_image_JD": box(first),
        "history": [],
    }
    epoch = initial
    for _ in range(plan["photon_root_iterations"]):
        proposed = image(epoch)
        low = max(epoch.bounds()[0], proposed.bounds()[0])
        high = min(epoch.bounds()[1], proposed.bounds()[1])
        if low > high:
            raise ValueError("Certified root intersection became empty")
        next_epoch = I(low, high)
        saved["history"].append(
            {
                "input_JD": box(epoch),
                "image_JD": box(proposed),
                "next_JD": box(next_epoch),
            }
        )
        epoch = next_epoch
    saved["root_JD"] = box(epoch)
    saved["conditional_unique_Newtonian_root_proved"] = True
    saved["physical_service_emission_algorithm_certified"] = False
    return epoch, saved


def segment_clearance(earth_sun, ray):
    direction = unit(ray)
    projected = -dot(earth_sun, direction).v
    distance = norm(ray).v
    if projected.bounds()[1] <= 0:
        return norm(earth_sun).v, "observer_endpoint"
    if projected.bounds()[0] >= distance.bounds()[1]:
        return norm(add(earth_sun, ray)).v, "source_endpoint"
    if 0 <= projected.bounds()[0] <= projected.bounds()[1] <= distance.bounds()[0]:
        return norm(cross(direction, earth_sun)).v, "interior"
    raise ValueError("Finite light-segment closest-point branch unresolved")


def transfer(source, case, observation, pair, plan):
    reception, emission = [Q(2451545) + Q(float.fromhex(v)) / 86400 for v in pair]
    reader = Reader(source, case["window_index"])
    root, root_proof = continuous_emission(reader, reception, emission, plan)
    low, high = root.bounds()
    support = I(min(low, emission), max(high, emission))
    earth = state(reader, I(reception), "Earth")
    target = state(reader, support, "Venus", 1)
    sun_now = state(reader, I(reception), "Sun")
    sun_emitted = state(reader, support, "Sun", 1)
    ray = sub(target[:3], earth[:3])
    natural = unit(ray)
    earth_sun = sub(earth[:3], sun_now[:3])
    re, e = norm(earth_sun), unit(earth_sun)
    clearance, branch = segment_clearance(earth_sun, ray)
    if clearance.bounds()[0] <= Q(plan["solar_ray_segment_minimum_distance_AU"]):
        raise ValueError("Finite light segment outside point-Sun model domain")
    beta = scale(earth[3:], K)
    delay = A(I(reception)) - A(support, 1)
    delta_epoch = root - emission
    models = []
    for sr, sun_epoch, potential in product(
        plan["SR_models"], plan["sun_epoch_models"], plan["potential_terms"]
    ):
        solar = (
            sun_emitted[:3]
            if sun_epoch == "exact_emission"
            else sub(sun_now[:3], scale(sun_now[3:], delay))
        )
        q = unit(sub(target[:3], solar))
        deflected, denominator = solar_deflection(natural, q, e, re)
        proper = aberration(deflected, beta, re, sr, potential)
        derivatives = signed_rates(proper)
        correction = [d * delta_epoch for d in derivatives]
        models.append(
            {
                "SR_model": sr,
                "sun_epoch_model": sun_epoch,
                "potential_term": potential,
                "deflection_denominator": box(denominator.v),
                "derivative_arcsec_per_emission_day": [box(d) for d in derivatives],
                "correction_arcsec": [box(c) for c in correction],
            }
        )
    corrections = [
        I(
            min(Q(m["correction_arcsec"][axis][0]) for m in models),
            max(Q(m["correction_arcsec"][axis][1]) for m in models),
        )
        for axis in (0, 1)
    ]
    if max(c.absolute_upper() for c in corrections) >= Q(1, 1000):
        raise ValueError("Correction outside declared small-angle branch domain")
    original = []
    corrected = []
    for printed, correction in zip(observation["apparent_angles"], corrections):
        center = Q(printed) * 3600
        noise = Q(10) ** Decimal(printed).as_tuple().exponent * 3600
        raw = I(center - noise, center + noise)
        original.append(box(raw))
        corrected.append(box(raw + correction))
    return {
        "case_id": case["id"],
        "offset_seconds": case["offset_seconds"],
        "receiver_hex": pair[0],
        "emitter_hex": pair[1],
        "reception_JD": str(reception),
        "emission_JD": str(emission),
        "root_proof": root_proof,
        "derivative_support_JD": box(support),
        "finite_light_segment_clearance_AU": box(clearance),
        "clearance_branch": branch,
        "models": models,
        "union_correction_arcsec": [box(c) for c in corrections],
        "original_printing_interval_arcsec": original,
        "corrected_observation_interval_arcsec": corrected,
        "physical_service_model_equivalence_certified": False,
        "physical_TT_time_model_certified": False,
        "original_reference_results_regraded": False,
    }


def analyze(native, design_root, cohort):
    plan = json.loads((design_root / "design-before-development.json").read_text())
    data_path = native / (cohort + "-first-analysis.json")
    data = json.loads(data_path.read_text())
    proof = json.loads(
        (native / (cohort + "-independent-clock-first.json")).read_text()
    )
    if (
        proof["clock_analysis_sha256"]
        != hashlib.sha256(data_path.read_bytes()).hexdigest()
        or proof["primary_nodes"] != 577
    ):
        raise ValueError("Complete native clock proof binding required")
    source_plan = json.loads((native / "plan-before-queries.json").read_text())
    for name, digest in source_plan["inputs_sha256"].items():
        if hashlib.sha256((native / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen native input changed")
    cases = {
        c["id"]: c
        for q in source_plan["queries"]
        if q["cohort"] == cohort
        for c in q["cases"]
    }
    result = {
        "cohort": cohort,
        "native_analysis_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "design_sha256": hashlib.sha256(
            (design_root / "design-before-development.json").read_bytes()
        ).hexdigest(),
        "rows": [],
        "new_candidate_holdouts": 0,
        "physical_service_model_equivalence_certified": False,
        "physical_TT_time_model_certified": False,
        "original_reference_results_regraded": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    for group in data["queries"]:
        for record in group["rows"]:
            observation = record["observation"]
            case = cases[observation["case_id"]]
            if case["role"] == "auxiliary_not_primary":
                continue
            pairs = []
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
                        raise ValueError("Full common native population not qualified")
                    pairs.append(values[0])
            if any(p != pairs[0] for p in pairs):
                raise ValueError("Native-model ambiguity must be retained")
            row = transfer(native / "source-records", case, observation, pairs[0], plan)
            result["rows"].append(row)
            if len(result["rows"]) % 18 == 0:
                print(
                    cohort, "conditional transfer rows", len(result["rows"]), flush=True
                )
    if (
        sorted(r["offset_seconds"] for r in result["rows"])
        != plan["primary_offsets_seconds"]
    ):
        raise ValueError("All 577 original nodes required")
    result["rows"].sort(key=lambda r: r["offset_seconds"])
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--native", required=True, type=Path)
    p.add_argument("--design", required=True, type=Path)
    p.add_argument("--cohort", required=True, choices=("A", "B"))
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    value = analyze(args.native, args.design, args.cohort)
    with args.output.open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
