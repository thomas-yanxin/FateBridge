"""Independent source endpoint, half-angle and implicit-rate transfer replay.

No receiver producer, its interval implementation or source evaluator imported.
This checks the declared source model only and preserves its physical limits.
"""

import argparse
import hashlib
import json
import struct
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as Q
from functools import cache
from itertools import product
from pathlib import Path

from scripts.verify_astrodice_emission_transfer import (
    SRS,
    D,
    clearance_proof,
    cross,
    dot,
    norm,
    root_proof,
    scale,
    unit,
    vector_sub,
)
from scripts.verify_astrodice_observer_clock import (
    K,
    Source,
    add,
    cover,
    divide,
    independent_pi,
    length,
    mul,
    observed_direction,
    parse,
    root,
    rounded,
    square,
    sub,
)
from scripts.verify_astrodice_vector_clock import bernstein_bounds, derivative

DESIGN_SHA = "072c72e5a9f00d79107063aaf577b636fc693998316d989bb794a7463330c517"


def acceleration_group(source, epoch, group):
    source.group(epoch, group)
    low, high = epoch
    raw = next(
        r
        for r in source.records
        if Q(struct.unpack_from("<d", r)[0])
        <= low
        <= high
        < Q(struct.unpack_from("<d", r, 8)[0])
    )
    start, end = map(Q, struct.unpack_from("<2d", raw))
    _, _, parts = source.pointers[group]
    width = (end - start) / parts
    piece = (low - start) // width
    begin = start + piece * width
    a, b = 2 * (low - begin) / width - 1, 2 * (high - begin) / width - 1
    return [
        rounded(*bernstein_bounds([v * 2 / width for v in derivative(p)], a, b))
        for p in source.cache[(start, group, piece)][3:]
    ]


def state(source, epoch, body, seed=0):
    raw = source.group(epoch, 10) if body == "Sun" else source.state(epoch, body)
    coefficient = seed if isinstance(seed, tuple) else rounded(seed)
    if coefficient != rounded(0) and body in ("Earth", "Sun"):
        if body == "Sun":
            acc = acceleration_group(source, epoch, 10)
        else:
            emb, moon = (
                acceleration_group(source, epoch, 2),
                acceleration_group(source, epoch, 9),
            )
            acc = [
                sub(a, divide(b, rounded(source.emrat + 1))) for a, b in zip(emb, moon)
            ]
    else:
        acc = [rounded(0)] * 3
    return [D(p, mul(v, coefficient)) for p, v in zip(raw[:3], raw[3:])] + [
        D(v, mul(a, coefficient)) for v, a in zip(raw[3:], acc)
    ]


def geometry(source, reception, emission, receiver_seed=0, emitter_seed=0):
    tr = rounded(reception, scale=1 << 256)
    te = rounded(*emission, scale=1 << 256)
    earth, target, sun, emitted_sun = (
        state(source, tr, "Earth", receiver_seed),
        state(source, te, "Venus", emitter_seed),
        state(source, tr, "Sun", receiver_seed),
        state(source, te, "Sun", emitter_seed),
    )
    ray = vector_sub(target[:3], earth[:3])
    es = vector_sub(earth[:3], sun[:3])
    p, re, e = unit(ray), norm(es), unit(es)
    delay = D(tr, receiver_seed) - D(te, emitter_seed)
    suns = {
        "exact_emission": emitted_sun[:3],
        "linearized_emission": vector_sub(sun[:3], scale(sun[3:], delay)),
    }
    qs = {name: unit(vector_sub(target[:3], v)) for name, v in suns.items()}
    return p, qs, re, e, scale(earth[3:], K)


def proper_model(prepared, sr, sun_epoch, potential):
    p, qs, re, e, beta = prepared
    q = qs[sun_epoch]
    denominator = dot(q, [a + b for a, b in zip(q, e)])
    if denominator.p[0] <= Q(1, 100):
        raise ValueError("Independent deflection domain failed")
    natural = unit(
        [a + b for a, b in zip(p, scale(cross(p, cross(e, q)), SRS / re / denominator))]
    )
    b2, pb = dot(beta, beta), dot(natural, beta)
    if b2.p[1] >= Q(1, 10000):
        raise ValueError("Independent velocity domain failed")
    if sr == "full_Lorentz":
        bm1 = (1 - b2).sqrt()
        aa = scale(natural, bm1)
        bb = scale(beta, 1 + pb / (1 + bm1))
    elif sr == "normalized_second_order":
        aa = scale(natural, 1 - pb + pb * pb - b2 / 2)
        bb = scale(beta, 1 - pb / 2)
    else:
        raise ValueError("Unplanned independent SR model")
    extra = scale(vector_sub(beta, scale(natural, pb)), potential * SRS / re)
    return unit([a + b + c for a, b, c in zip(aa, bb, extra)]), denominator.p


def half_angle(numerator, denominator, plan):
    if denominator[0] <= 0:
        raise ValueError("Independent angular branch unqualified")
    direct = divide(numerator, denominator)
    if max(map(abs, direct)) >= Q(plan["maximum_absolute_atan_argument"]):
        raise ValueError("Independent ratio domain failed")
    half = divide(
        numerator, add(root(add(square(numerator), square(denominator))), denominator)
    )
    result = rounded(0)
    for k in range(4):
        power = rounded(1)
        for _ in range(2 * k + 1):
            power = mul(power, half)
        result = add(result, mul(power, rounded(Q((-1) ** k, 2 * k + 1))))
    tail = max(map(abs, half)) ** 9 / 9
    result = mul(add(result, rounded(-tail, tail)), rounded(2))
    return mul(result, divide(rounded(648000), independent_pi()))


def direct_angle(numerator, denominator, plan):
    if denominator[0] <= 0:
        raise ValueError("Independent residual angular branch failed")
    ratio = divide(numerator, denominator)
    if max(map(abs, ratio)) >= Q(plan["maximum_absolute_atan_argument"]):
        raise ValueError("Independent residual ratio domain failed")
    power, result = ratio, rounded(0)
    squared = square(ratio)
    for k in range(4):
        result = add(result, mul(power, rounded(Q((-1) ** k, 2 * k + 1))))
        power = mul(power, squared)
    tail = max(map(abs, ratio)) ** 9 / 9
    return mul(
        add(result, rounded(-tail, tail)), divide(rounded(648000), independent_pi())
    )


def angle_change(before, after, plan, residual=False):
    x0, y0, z0 = [v.p for v in before]
    x1, y1, z1 = [v.p for v in after]
    r0sq, r1sq = add(square(x0), square(y0)), add(square(x1), square(y1))
    if min(r0sq[0], r1sq[0]) <= Q(plan["minimum_rho_squared"]):
        raise ValueError("Independent endpoint pole guard failed")
    r0, r1 = root(r0sq), root(r1sq)
    numerators = [sub(mul(x0, y1), mul(y0, x1)), sub(mul(r0, z1), mul(z0, r1))]
    denominators = [add(mul(x0, x1), mul(y0, y1)), add(mul(r0, r1), mul(z0, z1))]
    evaluator = direct_angle if residual else half_angle
    return [evaluator(n, d, plan) for n, d in zip(numerators, denominators)]


def observed(source_angles):
    # Separate 288-bit Taylor recurrence and full original printing interval.
    return [D(v) for v in observed_direction(source_angles, 0)]


def rate(vector):
    x, y, z = vector
    r2 = add(square(x.p), square(y.p))
    r = root(r2)
    ra = divide(sub(mul(x.p, y.t), mul(y.p, x.t)), r2)
    dr = divide(add(mul(x.p, x.t), mul(y.p, y.t)), r)
    dec = divide(sub(mul(r, z.t), mul(z.p, dr)), add(r2, square(z.p)))
    factor = divide(rounded(648000), independent_pi())
    return [mul(ra, factor), mul(dec, factor)]


def implicit_factor(source, reception, emission, plan):
    earth = source.state(rounded(reception, scale=1 << 256), "Earth")
    target = source.state(rounded(*emission, scale=1 << 256), "Venus")
    ray = [sub(v, e) for v, e in zip(target[:3], earth[:3])]
    distance = length(ray)
    direction = [divide(v, distance) for v in ray]
    dots = []
    for velocity in (earth[3:], target[3:]):
        value = rounded(0)
        for u, v in zip(direction, velocity):
            value = add(value, mul(u, v))
        dots.append(add(rounded(1), mul(rounded(K), value)))
    if dots[1][0] <= Q(plan["minimum_implicit_emission_derivative_denominator"]):
        raise ValueError("Independent implicit derivative denominator failed")
    return divide(dots[0], dots[1]), dots[1]


def check_row(native, case, observation, old, saved, center, plan, emission_design):
    reception, discrete = Q(old["reception_JD"]), Q(old["emission_JD"])
    target = center + Q(case["offset_seconds"], 86400)
    shift = (target - reception) * 86400
    if (
        saved["case_id"] != case["id"]
        or saved["offset_seconds"] != case["offset_seconds"]
        or saved["original_receiver_hex"] != old["receiver_hex"]
        or saved["original_emitter_hex"] != old["emitter_hex"]
        or Q(saved["original_receiver_JD"]) != reception
        or Q(saved["original_emitter_JD"]) != discrete
        or Q(saved["target_receiver_JD"]) != target
        or Q(saved["receiver_shift_seconds"]) != shift
        or abs(shift) >= Q(plan["maximum_receiver_shift_seconds"])
    ):
        raise ValueError("Fixed target or native identity changed")
    if any(
        saved[k]
        for k in (
            "physical_service_model_equivalence_certified",
            "physical_TT_time_model_certified",
            "original_results_regraded",
        )
    ):
        raise ValueError("Joint endpoint result promoted")
    source = Source(native / "source-records", case["window_index"])
    source.group = cache(source.group)
    source.state = cache(source.state)
    emitted = root_proof(
        source, target, discrete, saved["target_emitter_root_proof"], emission_design
    )
    for prefix, tr, te in (
        ("original", reception, (discrete, discrete)),
        ("target", target, emitted),
    ):
        clearance_proof(
            source,
            tr,
            te,
            {
                "finite_light_segment_clearance_AU": saved[
                    prefix + "_finite_segment_clearance_AU"
                ],
                "clearance_branch": saved[prefix + "_clearance_branch"],
            },
            emission_design,
        )
    variants = list(
        product(
            emission_design["SR_models"],
            emission_design["sun_epoch_models"],
            emission_design["potential_terms"],
        )
    )
    if [
        (v["SR_model"], v["sun_epoch_model"], v["potential_term"])
        for v in saved["models"]
    ] != variants:
        raise ValueError("A fixed model variant was dropped")
    raw_geometry = geometry(source, reception, (discrete, discrete))
    target_geometry = geometry(source, target, emitted)
    obs = observed(observation["apparent_angles"])
    derivative_geometry = None
    if case["offset_seconds"] == 0:
        factor, denominator = implicit_factor(source, target, emitted, plan)
        cover(factor, saved["implicit_emitter_derivative"])
        cover(denominator, saved["implicit_emitter_derivative_denominator"])
        derivative_geometry = geometry(
            source, target, emitted, 1, parse(saved["implicit_emitter_derivative"])
        )
    for identity, model in zip(variants, saved["models"]):
        before, db = proper_model(raw_geometry, *identity)
        after, da = proper_model(target_geometry, *identity)
        for declared, actual in (
            (model["original_direction"], before),
            (model["target_direction"], after),
        ):
            if len(declared) != 3:
                raise ValueError("Direction component dropped")
            for pair, v in zip(declared, actual):
                cover(v.p, pair)
        cover(db, model["original_deflection_denominator"])
        cover(da, model["target_deflection_denominator"])
        for got, expected in zip(
            angle_change(before, after, plan), model["total_correction_arcsec"]
        ):
            cover(got, expected)
        # A same-form, separately implemented atan interval also certifies the
        # full printed-direction residual tube. Overlap alone is insufficient.
        residual = angle_change(obs, before, plan, residual=True)
        for computed, declared in zip(residual, model["model_minus_observed_arcsec"]):
            cover(computed, declared)
        declared_pass = all(
            max(map(abs, parse(v))) <= Q(plan["source_model_position_line_arcsec"])
            for v in model["model_minus_observed_arcsec"]
        )
        if model["source_model_position_line_met"] != declared_pass:
            raise ValueError("Source position line result changed")
        independent_pass = all(
            max(map(abs, v)) <= Q(plan["source_model_position_line_arcsec"])
            for v in residual
        )
        if declared_pass and not independent_pass:
            raise ValueError("Model-level position pass not independently supported")
        if derivative_geometry is not None:
            differentiated, _ = proper_model(derivative_geometry, *identity)
            for got, expected in zip(
                rate(differentiated), model["rate_arcsec_per_source_day"]
            ):
                cover(got, expected)
        elif "rate_arcsec_per_source_day" in model:
            raise ValueError("Unplanned derivative point")
    if (
        saved["original_printing_interval_arcsec"]
        != old["original_printing_interval_arcsec"]
    ):
        raise ValueError("Original raw printing interval changed")
    for axis in (0, 1):
        united = (
            min(Q(m["total_correction_arcsec"][axis][0]) for m in saved["models"]),
            max(Q(m["total_correction_arcsec"][axis][1]) for m in saved["models"]),
        )
        if united != parse(saved["union_total_correction_arcsec"][axis]) or max(
            map(abs, united)
        ) >= Q(plan["angular_transfer_domain_guard_arcsec"]):
            raise ValueError("Full endpoint union changed")
        original = parse(old["original_printing_interval_arcsec"][axis])
        expected = rounded(
            original[0] + united[0], original[1] + united[1], scale=1 << 256
        )
        if expected != parse(
            saved["total_corrected_observation_interval_arcsec"][axis]
        ):
            raise ValueError(
                "Total observation interval is not the full original interval plus union"
            )


def check_task(args):
    try:
        check_row(*args)
    except Exception as error:
        raise ValueError("Joint row " + args[1]["id"] + ": " + str(error)) from error


def verify(native, design, cohort, path, emission_path, proof_path, workers=4):
    if (
        hashlib.sha256(
            (design / "design-before-development.json").read_bytes()
        ).hexdigest()
        != DESIGN_SHA
    ):
        raise ValueError("Frozen receiver design changed")
    plan = json.loads((design / "design-before-development.json").read_text())
    emission_design = json.loads((design / "emission-design-original.json").read_text())
    data, old, proof = [
        json.loads(p.read_text()) for p in (path, emission_path, proof_path)
    ]

    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    if (
        data["design_sha256"] != DESIGN_SHA
        or data["emission_transfer_sha256"] != sha(emission_path)
        or data["independent_emission_proof_sha256"] != sha(proof_path)
        or proof["transfer_sha256"] != sha(emission_path)
        or proof["rows_checked"] != 577
        or data["cohort"] != cohort
    ):
        raise ValueError("Prior emission proof or endpoint binding changed")
    if (
        any(
            data[k]
            for k in (
                "new_candidate_holdouts",
                "physical_service_model_equivalence_certified",
                "physical_TT_time_model_certified",
                "physical_remainder_certified",
                "original_results_regraded",
                "full_goal_complete",
            )
        )
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Conditional endpoint scope promoted")
    nplan = json.loads((native / "plan-before-queries.json").read_text())
    for name, digest in nplan["inputs_sha256"].items():
        if sha(native / name) != digest:
            raise ValueError("Native frozen input changed")
    npath = native / (cohort + "-first-analysis.json")
    if data["native_analysis_sha256"] != sha(npath) or old[
        "native_analysis_sha256"
    ] != sha(npath):
        raise ValueError("Native data binding changed")
    cases = {
        c["id"]: c
        for q in nplan["queries"]
        if q["cohort"] == cohort
        for c in q["cases"]
    }
    obs = {
        r["observation"]["case_id"]: r["observation"]
        for g in json.loads(npath.read_text())["queries"]
        for r in g["rows"]
    }
    if [r["offset_seconds"] for r in data["rows"]] != plan[
        "primary_offsets_seconds"
    ] or [r["offset_seconds"] for r in old["rows"]] != plan["primary_offsets_seconds"]:
        raise ValueError("Complete old and new 577 populations required")
    center = Q(next(r["reception_JD"] for r in old["rows"] if r["offset_seconds"] == 0))
    if Q(data["center_receiver_JD"]) != center:
        raise ValueError("Uniform source anchor changed")
    tasks = [
        (
            native,
            cases[a["case_id"]],
            obs[a["case_id"]],
            a,
            b,
            center,
            plan,
            emission_design,
        )
        for a, b in zip(old["rows"], data["rows"])
    ]
    if workers not in (1, 4):
        raise ValueError("Unsupported worker count")
    if workers == 1:
        for index, _ in enumerate(map(check_task, tasks), 1):
            if index % 18 == 0:
                print(cohort, "independent endpoint rows", index, flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for index, _ in enumerate(pool.map(check_task, tasks), 1):
                if index % 18 == 0:
                    print(cohort, "independent endpoint rows", index, flush=True)
    return {
        "cohort": cohort,
        "receiver_transfer_sha256": sha(path),
        "rows_checked": 577,
        "endpoint_models_checked": 577 * 8,
        "target_root_iterations_checked": 577 * 24,
        "source_rate_models_checked": 8,
        "source_model_position_failures": sum(
            not m["source_model_position_line_met"]
            for r in data["rows"]
            for m in r["models"]
        ),
        "physical_service_model_equivalence_certified": False,
        "physical_TT_time_model_certified": False,
        "physical_remainder_certified": False,
        "original_results_regraded": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


def main():
    parser = argparse.ArgumentParser()
    for name in ("native", "design", "input", "emission", "proof", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--cohort", choices=("A", "B"), required=True)
    parser.add_argument("--workers", type=int, choices=(1, 4), default=4)
    args = parser.parse_args()
    result = verify(
        args.native,
        args.design,
        args.cohort,
        args.input,
        args.emission,
        args.proof,
        args.workers,
    )
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
