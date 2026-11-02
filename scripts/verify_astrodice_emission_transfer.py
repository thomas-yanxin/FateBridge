"""Separate source, interval differentials and root replay for transfer bounds.

No transfer producer, its interval/AD code, or its source evaluator is imported.
This proves only the named mathematical models, never service equivalence.
"""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal
from fractions import Fraction as Q
from functools import cache
from itertools import product
from pathlib import Path

from scripts.verify_astrodice_observer_clock import (
    Source,
    add,
    cover,
    divide,
    independent_pi,
    length,
    mul,
    neg,
    parse,
    root,
    rounded,
    square,
    sub,
)

K = Q(149597870700, 299792458 * 86400)
SRS = Q("0.0000000197412574336")


class D:
    def __init__(self, value=0, differential=0):
        self.p = rounded(*value) if isinstance(value, tuple) else rounded(value)
        self.t = (
            rounded(*differential)
            if isinstance(differential, tuple)
            else rounded(differential)
        )

    @staticmethod
    def cast(value):
        return value if isinstance(value, D) else D(value)

    def __add__(self, other):
        other = D.cast(other)
        return D(add(self.p, other.p), add(self.t, other.t))

    __radd__ = __add__

    def __neg__(self):
        return D(neg(self.p), neg(self.t))

    def __sub__(self, other):
        return self + -D.cast(other)

    def __rsub__(self, other):
        return D.cast(other) - self

    def __mul__(self, other):
        other = D.cast(other)
        return D(mul(self.p, other.p), add(mul(self.t, other.p), mul(self.p, other.t)))

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = D.cast(other)
        return D(
            divide(self.p, other.p),
            sub(divide(self.t, other.p), divide(mul(self.p, other.t), square(other.p))),
        )

    def __rtruediv__(self, other):
        return D.cast(other) / self

    def sqrt(self):
        value = root(self.p)
        return D(value, divide(self.t, mul(rounded(2), value)))


def total(values):
    return sum(values, D())


def dot(a, b):
    return total([x * y for x, y in zip(a, b)])


def vector_sub(a, b):
    return [x - y for x, y in zip(a, b)]


def scale(a, coefficient):
    return [x * coefficient for x in a]


def norm(a):
    value = length([v.p for v in a])
    differential = rounded(0)
    for v in a:
        differential = add(differential, mul(v.p, v.t))
    return D(value, divide(differential, value))


def unit(a):
    return scale(a, 1 / norm(a))


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def source_state(source, epoch, body, changing=False):
    raw = source.group(epoch, 10) if body == "Sun" else source.state(epoch, body)
    return [D(p, v if changing else 0) for p, v in zip(raw[:3], raw[3:])] + [
        D(v) for v in raw[3:]
    ]


def model_derivatives(source, reception, support, sr, solar_epoch, potential):
    e = source_state(source, rounded(reception, scale=1 << 256), "Earth")
    v = source_state(source, rounded(*support, scale=1 << 256), "Venus", True)
    sun = source_state(source, rounded(reception, scale=1 << 256), "Sun")
    emitted_sun = source_state(source, rounded(*support, scale=1 << 256), "Sun", True)
    ray = vector_sub(v[:3], e[:3])
    p = unit(ray)
    eh = vector_sub(e[:3], sun[:3])
    re = norm(eh)
    direction = unit(eh)
    elapsed = D(reception) - D(support, 1)
    solar = (
        emitted_sun[:3]
        if solar_epoch == "exact_emission"
        else vector_sub(sun[:3], scale(sun[3:], elapsed))
    )
    q = unit(vector_sub(v[:3], solar))
    denominator = dot(q, [a + b for a, b in zip(q, direction)])
    if denominator.p[0] <= Q(1, 100):
        raise ValueError("Independent deflection domain not qualified")
    change = scale(cross(p, cross(direction, q)), SRS / re / denominator)
    natural = unit([a + b for a, b in zip(p, change)])
    beta = scale(e[3:], K)
    b2, pb = dot(beta, beta), dot(natural, beta)
    if b2.p[1] >= Q(1, 10000):
        raise ValueError("Independent velocity domain not qualified")
    if sr == "full_Lorentz":
        bm1 = (1 - b2).sqrt()
        aa = scale(natural, bm1)
        bb = scale(beta, 1 + pb / (1 + bm1))
    elif sr == "normalized_second_order":
        aa = scale(natural, 1 - pb + pb * pb - b2 / 2)
        bb = scale(beta, 1 - pb / 2)
    else:
        raise ValueError("Independent SR model changed")
    extra = scale(vector_sub(beta, scale(natural, pb)), potential * SRS / re)
    proper = unit([a + b + c for a, b, c in zip(aa, bb, extra)])
    x, y, z = proper
    rho2 = add(square(x.p), square(y.p))
    if rho2[0] <= Q(1, 10**8):
        raise ValueError("Independent coordinate pole not qualified")
    rho = root(rho2)
    ra = divide(sub(mul(x.p, y.t), mul(y.p, x.t)), rho2)
    drho = divide(add(mul(x.p, x.t), mul(y.p, y.t)), rho)
    dec = divide(sub(mul(rho, z.t), mul(z.p, drho)), add(rho2, square(z.p)))
    factor = divide(rounded(648000), independent_pi())
    return [mul(ra, factor), mul(dec, factor)], denominator.p


def root_proof(source, reception, emission, saved, plan):
    radius = Q(plan["initial_emitter_radius_seconds"]) / 86400
    expected = rounded(emission - radius, emission + radius, scale=1 << 256)
    initial = parse(saved["initial_JD"])
    if initial != expected:
        raise ValueError("Fixed root support changed")
    earth = source.state(rounded(reception, scale=1 << 256), "Earth")[:3]
    broad = source.state(initial, "Venus")
    q_upper = length(broad[3:])[1] * K
    if not q_upper <= Q(saved["contraction_upper"]) < 1:
        raise ValueError("Emission contraction not independently certified")

    def image(epoch):
        target = source.state(epoch, "Venus")[:3]
        ray = [sub(v, e) for v, e in zip(target, earth)]
        return sub(rounded(reception), mul(rounded(K), length(ray)))

    cover(image(initial), saved["initial_image_JD"])
    first = parse(saved["initial_image_JD"])
    if not initial[0] <= first[0] <= first[1] <= initial[1]:
        raise ValueError("Initial emission domain not invariant")
    if len(saved["history"]) != plan["photon_root_iterations"]:
        raise ValueError("Fixed root iteration population changed")
    epoch = initial
    for item in saved["history"]:
        if parse(item["input_JD"]) != epoch:
            raise ValueError("Root trace input changed")
        cover(image(epoch), item["image_JD"])
        proposed = parse(item["image_JD"])
        following = max(epoch[0], proposed[0]), min(epoch[1], proposed[1])
        if following[0] > following[1] or following != parse(item["next_JD"]):
            raise ValueError("Root intersection lost a possible root")
        epoch = following
    if (
        parse(saved["root_JD"]) != epoch
        or not saved["conditional_unique_Newtonian_root_proved"]
        or saved["physical_service_emission_algorithm_certified"]
    ):
        raise ValueError("Root scope or result changed")
    return epoch


def clearance_proof(source, reception, support, saved, plan):
    earth = source.state(rounded(reception, scale=1 << 256), "Earth")[:3]
    sun = source.group(rounded(reception, scale=1 << 256), 10)[:3]
    venus = source.state(rounded(*support, scale=1 << 256), "Venus")[:3]
    eh = [sub(e, s) for e, s in zip(earth, sun)]
    ray = [sub(v, e) for v, e in zip(venus, earth)]
    distance = length(ray)
    p = [divide(v, distance) for v in ray]
    dot_e = rounded(0)
    for e, u in zip(eh, p):
        dot_e = add(dot_e, mul(e, u))
    projected = neg(dot_e)
    if projected[1] <= 0:
        value, branch = length(eh), "observer_endpoint"
    elif projected[0] >= distance[1]:
        value, branch = length([add(e, r) for e, r in zip(eh, ray)]), "source_endpoint"
    elif 0 <= projected[0] <= projected[1] <= distance[0]:
        values = [
            sub(mul(p[1], eh[2]), mul(p[2], eh[1])),
            sub(mul(p[2], eh[0]), mul(p[0], eh[2])),
            sub(mul(p[0], eh[1]), mul(p[1], eh[0])),
        ]
        value, branch = length(values), "interior"
    else:
        raise ValueError("Independent closest-point branch unqualified")
    cover(value, saved["finite_light_segment_clearance_AU"])
    if branch != saved["clearance_branch"] or Q(
        saved["finite_light_segment_clearance_AU"][0]
    ) <= Q(plan["solar_ray_segment_minimum_distance_AU"]):
        raise ValueError("Point-Sun domain changed")


def check_row(native, case, observation, pair, saved, plan, checking):
    reception, emission = [2451545 + Q(float.fromhex(v)) / 86400 for v in pair]
    if (
        saved["case_id"] != case["id"]
        or saved["offset_seconds"] != case["offset_seconds"]
        or saved["receiver_hex"] != pair[0]
        or saved["emitter_hex"] != pair[1]
        or Q(saved["reception_JD"]) != reception
        or Q(saved["emission_JD"]) != emission
    ):
        raise ValueError("Native pair or node changed")
    if (
        saved["physical_service_model_equivalence_certified"]
        or saved["physical_TT_time_model_certified"]
        or saved["original_reference_results_regraded"]
    ):
        raise ValueError("Conditional transfer promoted")
    source = Source(native / "source-records", case["window_index"])
    # The same independent epoch boxes recur in eight models. Cache only exact
    # arguments/results; no geometry, interval endpoint, or tolerance changes.
    source.group = cache(source.group)
    source.state = cache(source.state)
    root_epoch = root_proof(source, reception, emission, saved["root_proof"], plan)
    support = min(root_epoch[0], emission), max(root_epoch[1], emission)
    support = rounded(*support, scale=1 << 256)
    if support != parse(saved["derivative_support_JD"]):
        raise ValueError("Derivative support changed")
    clearance_proof(source, reception, support, saved, plan)
    variants = list(
        product(plan["SR_models"], plan["sun_epoch_models"], plan["potential_terms"])
    )
    if [
        (r["SR_model"], r["sun_epoch_model"], r["potential_term"])
        for r in saved["models"]
    ] != variants:
        raise ValueError("A model variant was dropped")
    for (sr, sun_epoch, potential), model in zip(variants, saved["models"]):
        results = []
        denominators = []
        n = checking["independent_derivative_subintervals"]
        for k in range(n):
            a = support[0] + (support[1] - support[0]) * k / n
            b = support[0] + (support[1] - support[0]) * (k + 1) / n
            rates, denominator = model_derivatives(
                source, reception, (a, b), sr, sun_epoch, potential
            )
            results.append(rates)
            denominators.append(denominator)
        cover(
            (min(d[0] for d in denominators), max(d[1] for d in denominators)),
            model["deflection_denominator"],
        )
        for axis in (0, 1):
            bound = min(r[axis][0] for r in results), max(r[axis][1] for r in results)
            cover(bound, model["derivative_arcsec_per_emission_day"][axis])
            difference = sub(root_epoch, rounded(emission))
            cover(
                mul(
                    parse(model["derivative_arcsec_per_emission_day"][axis]), difference
                ),
                model["correction_arcsec"][axis],
            )
    for axis, printed in enumerate(observation["apparent_angles"]):
        union = (
            min(Q(m["correction_arcsec"][axis][0]) for m in saved["models"]),
            max(Q(m["correction_arcsec"][axis][1]) for m in saved["models"]),
        )
        if union != parse(saved["union_correction_arcsec"][axis]) or max(
            map(abs, union)
        ) >= Q(1, 1000):
            raise ValueError("Union or small-branch condition changed")
        center = Q(printed) * 3600
        noise = Q(10) ** Decimal(printed).as_tuple().exponent * 3600
        original = rounded(center - noise, center + noise, scale=1 << 256)
        if original != parse(saved["original_printing_interval_arcsec"][axis]):
            raise ValueError("Original printing uncertainty changed")
        expected = rounded(
            original[0] + union[0], original[1] + union[1], scale=1 << 256
        )
        if expected != parse(saved["corrected_observation_interval_arcsec"][axis]):
            raise ValueError("Corrected interval is not the full propagated interval")


def check_task(arguments):
    check_row(*arguments)


def verify(native, design, cohort, path, workers=1):
    plan = json.loads((design / "design-before-development.json").read_text())
    checking = json.loads(
        (design / "checking-plan-before-development.json").read_text()
    )
    if (
        checking["design_sha256"]
        != hashlib.sha256(
            (design / "design-before-development.json").read_bytes()
        ).hexdigest()
        or checking["independent_derivative_subintervals"] != 16
        or not checking["original_lines_unchanged"]
        or plan["photon_root_iterations"] != 24
        or plan["SR_models"] != ["full_Lorentz", "normalized_second_order"]
        or plan["sun_epoch_models"] != ["exact_emission", "linearized_emission"]
        or plan["potential_terms"] != [0, 1]
        or Q(plan["SRS_exact_decimal"]) != SRS
    ):
        raise ValueError("Frozen checking plan or declared model family changed")
    data = json.loads(path.read_text())
    source_path = native / (cohort + "-first-analysis.json")
    source_data = json.loads(source_path.read_text())
    source_proof = json.loads(
        (native / (cohort + "-independent-clock-first.json")).read_text()
    )
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if (
        source_proof["clock_analysis_sha256"] != source_hash
        or source_proof["primary_nodes"] != 577
        or data["native_analysis_sha256"] != source_hash
        or data["design_sha256"]
        != hashlib.sha256(
            (design / "design-before-development.json").read_bytes()
        ).hexdigest()
        or data["cohort"] != cohort
    ):
        raise ValueError("Native proof or transfer input changed")
    if (
        any(
            data[k]
            for k in (
                "new_candidate_holdouts",
                "physical_service_model_equivalence_certified",
                "physical_TT_time_model_certified",
                "original_reference_results_regraded",
                "full_goal_complete",
            )
        )
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Transfer scope promoted")
    source_plan = json.loads((native / "plan-before-queries.json").read_text())
    for name, digest in source_plan["inputs_sha256"].items():
        if hashlib.sha256((native / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Frozen native source changed")
    cases = {
        c["id"]: c
        for q in source_plan["queries"]
        if q["cohort"] == cohort
        for c in q["cases"]
    }
    observations = {
        r["observation"]["case_id"]: r
        for q in source_data["queries"]
        for r in q["rows"]
    }
    if [r["offset_seconds"] for r in data["rows"]] != plan["primary_offsets_seconds"]:
        raise ValueError("Full original transfer population required")
    tasks = []
    for row in data["rows"]:
        case = cases[row["case_id"]]
        record = observations[case["id"]]
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
                    or not record["observation"]["original_label_budget_pass"]
                ):
                    raise ValueError("Full common native clock population unqualified")
                pairs.append(values[0])
        if any(p != pairs[0] for p in pairs):
            raise ValueError("Native ambiguity discarded")
        tasks.append(
            (native, case, record["observation"], pairs[0], row, plan, checking)
        )
    if workers not in (1, 4):
        raise ValueError("Unplanned worker count")
    if workers == 1:
        results = map(check_task, tasks)
        for index, _ in enumerate(results, 1):
            if index % 18 == 0:
                print(cohort, "independent transfer rows", index, flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            for index, _ in enumerate(executor.map(check_task, tasks), 1):
                if index % 18 == 0:
                    print(cohort, "independent transfer rows", index, flush=True)
    return {
        "cohort": cohort,
        "rows_checked": 577,
        "model_derivative_enclosures_checked": 577 * 8 * 2,
        "source_root_iterations_checked": 577 * plan["photon_root_iterations"],
        "transfer_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "physical_service_model_equivalence_certified": False,
        "physical_TT_time_model_certified": False,
        "original_reference_results_regraded": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--native", required=True, type=Path)
    p.add_argument("--design", required=True, type=Path)
    p.add_argument("--cohort", required=True, choices=("A", "B"))
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--workers", type=int, choices=(1, 4), default=1)
    args = p.parse_args()
    result = verify(args.native, args.design, args.cohort, args.input, args.workers)
    with args.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
