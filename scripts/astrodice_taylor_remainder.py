"""Interval high derivatives of a declared source model, never a service oracle.

Normalized coefficients enclose f^(k)(t)/k! for every t in a whole interval.
The original observational LP, TT conversion and production gates are unchanged.
"""

import argparse
import hashlib
import json
import sys
from fractions import Fraction as Q
from itertools import product
from pathlib import Path

from scripts.astrodice_clock_interval import I, Reader
from scripts.astrodice_source_slope_bounds import pi_bounds

DESIGN_SHA = "d601da17f122bf78d63eccd0f0905087ce31efa004ebc5157688cde44096c2e8"
K = Q(149597870700, 299792458 * 86400)
SRS = Q("0.0000000197412574336")


class J:
    """Fixed-order normalized interval Taylor algebra."""

    def __init__(self, coefficients):
        if not coefficients:
            raise ValueError("Empty Taylor jet")
        self.c = tuple(I.cast(v) for v in coefficients)

    @classmethod
    def constant(cls, value, order):
        return cls([value] + [0] * order)

    def cast(self, value):
        if isinstance(value, J):
            if len(value.c) != len(self.c):
                raise ValueError("Mixed Taylor orders")
            return value
        return J.constant(value, len(self.c) - 1)

    def __neg__(self):
        return J([-v for v in self.c])

    def __add__(self, value):
        value = self.cast(value)
        return J([a + b for a, b in zip(self.c, value.c)])

    __radd__ = __add__

    def __sub__(self, value):
        return self + -self.cast(value)

    def __rsub__(self, value):
        return self.cast(value) - self

    def __mul__(self, value):
        value = self.cast(value)
        return J(
            [
                sum((self.c[k] * value.c[n - k] for k in range(n + 1)), I())
                for n in range(len(self.c))
            ]
        )

    __rmul__ = __mul__

    def reciprocal(self):
        result = [1 / self.c[0]]
        for n in range(1, len(self.c)):
            result.append(
                -sum((self.c[k] * result[n - k] for k in range(1, n + 1)), I())
                / self.c[0]
            )
        return J(result)

    def __truediv__(self, value):
        return self * self.cast(value).reciprocal()

    def __rtruediv__(self, value):
        return self.cast(value) * self.reciprocal()

    def sqrt(self):
        first = self.c[0].sqrt()
        if len(self.c) > 1 and first.bounds()[0] <= 0:
            raise ValueError("Nonsmooth Taylor square root")
        result = [first]
        for n in range(1, len(self.c)):
            middle = sum((result[k] * result[n - k] for k in range(1, n)), I())
            result.append((self.c[n] - middle) / (2 * first))
        return J(result)

    def derivative(self):
        if len(self.c) < 2:
            raise ValueError("No next derivative available")
        return J([(k + 1) * self.c[k + 1] for k in range(len(self.c) - 1)])

    def truncate(self, order):
        if order >= len(self.c):
            raise ValueError("Taylor truncation cannot invent derivatives")
        return J(self.c[: order + 1])


def dot(a, b):
    return sum((x * y for x, y in zip(a, b)), a[0].cast(0))


def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def add(a, b):
    return [x + y for x, y in zip(a, b)]


def scale(a, b):
    return [x * b for x in a]


def norm(a):
    return dot(a, a).sqrt()


def unit(a):
    return scale(a, 1 / norm(a))


def cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def segment_clearance(earth_sun, ray):
    direction = unit(ray)
    projected = -dot(earth_sun, direction).c[0]
    distance = norm(ray).c[0]
    lo, hi = projected.bounds()
    a, b = distance.bounds()
    if hi <= 0:
        return norm(earth_sun).c[0], "observer_endpoint"
    if lo >= b:
        return norm(add(earth_sun, ray)).c[0], "source_endpoint"
    if 0 <= lo <= hi <= a:
        return norm(cross(direction, earth_sun)).c[0], "interior"
    raise ValueError("Finite-segment closest-point branch unresolved")


class TaylorSource(Reader):
    """Direct Chebyshev composition; Reader supplies only original source words."""

    def group(self, epoch, group):
        low, high = epoch.c[0].bounds()
        record = next(
            (r for r in self.records if Q(r[0]) <= low <= high < Q(r[1])), None
        )
        if record is None:
            raise ValueError("Taylor source support crosses a record")
        offset, count, parts = self.pointers[group]
        width = (Q(record[1]) - Q(record[0])) / parts
        part = (low - Q(record[0])) // width
        if not 0 <= part < parts or high >= Q(record[0]) + (part + 1) * width:
            raise ValueError("Taylor source support crosses a cell")
        self.cells.add((group, record[0], part))
        x = 2 * (epoch - Q(record[0]) - part * width) / width - 1
        basis, deriv = [epoch.cast(1), x], [epoch.cast(0), epoch.cast(1)]
        for n in range(2, count):
            basis.append(2 * x * basis[n - 1] - basis[n - 2])
            deriv.append(2 * basis[n - 1] + 2 * x * deriv[n - 1] - deriv[n - 2])
        position, velocity = [], []
        for axis in range(3):
            begin = offset - 1 + (part * 3 + axis) * count
            coefficients = list(map(Q, record[begin : begin + count]))
            position.append(
                sum((c * v for c, v in zip(coefficients, basis)), epoch.cast(0))
                / self.au
            )
            velocity.append(
                sum((c * v for c, v in zip(coefficients, deriv)), epoch.cast(0))
                * 2
                / width
                / self.au
            )
        return position + velocity

    def state(self, epoch, body):
        if body == "Earth":
            return sub(
                self.group(epoch, 2), scale(self.group(epoch, 9), 1 / (1 + self.emrat))
            )
        if body not in ("Sun", "Venus"):
            raise ValueError("Unplanned Taylor body")
        return self.group(epoch, {"Sun": 10, "Venus": 1}[body])


def interval_record(value):
    return list(map(str, value.bounds()))


def jet_record(value):
    return [interval_record(v) for v in value.c]


def uniform_root(source, reception, plan):
    low, high = reception.bounds()
    initial = I(low - Q(plan["initial_emitter_margin_days"]), high)
    earth = source.state(J([reception]), "Earth")[:3]
    target = source.state(J([initial]), "Venus")
    contraction = norm(target[3:]).c[0].absolute_upper() * K
    if contraction >= 1:
        raise ValueError("Uniform emission map is not contractive")

    def image(emission):
        ray = sub(source.state(J([emission]), "Venus")[:3], earth)
        return reception - K * norm(ray).c[0]

    first = image(initial)
    a, b = initial.bounds()
    u, v = first.bounds()
    if not a <= u <= v <= b:
        raise ValueError("Uniform emission map is not invariant")
    proof = {
        "initial": interval_record(initial),
        "initial_image": interval_record(first),
        "contraction_upper": str(contraction),
        "iterations": [],
    }
    current = initial
    for _ in range(plan["root_iterations"]):
        proposed = image(current)
        a, b = current.bounds()
        u, v = proposed.bounds()
        result = I(max(a, u), min(b, v))
        proof["iterations"].append(
            {
                "input": interval_record(current),
                "image": interval_record(proposed),
                "next": interval_record(result),
            }
        )
        current = result
    proof["root"] = interval_record(current)
    return current, proof


def emission_jet(source, reception, root, plan):
    order = len(reception.c) - 1
    target = source.state(J([root]), "Venus")
    earth = source.state(J([reception.c[0]]), "Earth")
    direction = unit(sub(target[:3], earth[:3]))
    denominator = 1 + K * dot(direction, target[3:]).c[0]
    if denominator.bounds()[0] <= Q(plan["minimum_implicit_denominator"]):
        raise ValueError("Implicit Taylor denominator unqualified")
    coefficients = [root]
    history = []
    for k in range(1, order + 1):
        emitted = J(coefficients + [I()])
        received = reception.truncate(k)
        ray = sub(
            source.state(emitted, "Venus")[:3], source.state(received, "Earth")[:3]
        )
        residual = emitted + K * norm(ray) - received
        coefficient = -residual.c[k] / denominator
        coefficients.append(coefficient)
        history.append(
            {
                "order": k,
                "residual_with_highest_zero": interval_record(residual.c[k]),
                "coefficient": interval_record(coefficient),
            }
        )
    return J(coefficients), {
        "denominator": interval_record(denominator),
        "recurrences": history,
    }


def apparent_models(source, reception, emission, plan):
    earth, target, sun, emitted_sun = [
        source.state(t, b)
        for t, b in (
            (reception, "Earth"),
            (emission, "Venus"),
            (reception, "Sun"),
            (emission, "Sun"),
        )
    ]
    ray = sub(target[:3], earth[:3])
    p = unit(ray)
    earth_sun = sub(earth[:3], sun[:3])
    re, e = norm(earth_sun), unit(earth_sun)
    beta = scale(earth[3:], K)
    b2 = dot(beta, beta)
    if b2.c[0].bounds()[1] >= Q(plan["maximum_beta_squared"]):
        raise ValueError("Taylor observer beta outside the fixed domain")
    clearance, clearance_branch = segment_clearance(earth_sun, ray)
    if clearance.bounds()[0] <= Q(plan["minimum_light_segment_clearance_AU"]):
        raise ValueError("Taylor finite-ray clearance not established")
    suns = {
        "exact_emission": emitted_sun[:3],
        "linearized_emission": sub(sun[:3], scale(sun[3:], reception - emission)),
    }
    for sr, sun_epoch, potential in product(
        ("full_Lorentz", "normalized_second_order"), suns, (0, 1)
    ):
        q = unit(sub(target[:3], suns[sun_epoch]))
        denominator = dot(q, add(q, e))
        if denominator.c[0].bounds()[0] <= Q(plan["minimum_deflection_denominator"]):
            raise ValueError("Taylor deflection denominator unqualified")
        natural = unit(add(p, scale(cross(p, cross(e, q)), SRS / re / denominator)))
        pb = dot(natural, beta)
        if sr == "full_Lorentz":
            bm1 = (1 - b2).sqrt()
            result = add(scale(natural, bm1), scale(beta, 1 + pb / (1 + bm1)))
        else:
            result = add(
                scale(natural, 1 - pb + pb * pb - b2 / 2), scale(beta, 1 - pb / 2)
            )
        result = unit(
            add(result, scale(sub(beta, scale(natural, pb)), potential * SRS / re))
        )
        yield (
            [sr, sun_epoch, potential],
            result,
            denominator.c[0],
            clearance,
            clearance_branch,
        )


def angular_rates(vector, plan):
    dx, dy, dz = [v.derivative() for v in vector]
    x, y, z = [v.truncate(len(v.c) - 2) for v in vector]
    rho2 = x * x + y * y
    if rho2.c[0].bounds()[0] <= Q(plan["minimum_rho_squared"]):
        raise ValueError("Taylor angular chart crosses a pole")
    rho = rho2.sqrt()
    drho = (x * dx + y * dy) / rho
    factor = Q(648000) / I(*pi_bounds())
    return [
        (x * dy - y * dx) / rho2 * factor,
        (rho * dz - z * drho) / (rho2 + z * z) * factor,
    ]


def analyze(plan, entry):
    center, radius = (
        Q(entry["receiver_TDB_JD"]),
        Q(plan["maximum_receiver_radius_seconds"], 86400),
    )
    support = I(center - radius, center + radius)
    source = TaylorSource(Path(plan["source_fixture"]), entry["source_window"])
    root, root_proof = uniform_root(source, support, plan)
    reception = J([support, 1] + [0] * (plan["maximum_order"] - 1))
    emission, implicit = emission_jet(source, reception, root, plan)
    models = []
    for identity, vector, denominator, clearance, clearance_branch in apparent_models(
        source, reception, emission, plan
    ):
        rates = angular_rates(vector, plan)
        bounds = []
        for window, degree in product(
            plan["windows_seconds"], plan["full_polynomial_degrees"]
        ):
            h = Q(window, 86400)
            derivative_constants = [r.c[degree].absolute_upper() for r in rates]
            position = [
                v * h ** (degree + 1) / (degree + 1) for v in derivative_constants
            ]
            speed = [v * h**degree for v in derivative_constants]
            bounds.append(
                {
                    "window_seconds": window,
                    "full_degree": degree,
                    "position_remainder_arcsec": list(map(str, position)),
                    "derivative_remainder_arcsec_per_source_day": list(map(str, speed)),
                    "joint_position_bound_squared": str(
                        sum((v * v for v in position), Q())
                    ),
                    "joint_rate_bound_squared": str(sum((v * v for v in speed), Q())),
                }
            )
        models.append(
            {
                "model": identity,
                "direction_normalized_coefficients": [jet_record(v) for v in vector],
                "angular_rate_normalized_coefficients": [jet_record(v) for v in rates],
                "deflection_denominator": interval_record(denominator),
                "ray_clearance_lower_bound": interval_record(clearance),
                "ray_clearance_branch": clearance_branch,
                "all_window_remainders": bounds,
            }
        )
    if len(models) != 8:
        raise ValueError("A declared source profile was omitted")
    center_root, center_proof = uniform_root(source, I(center), plan)
    center_receiver = J([center, 1] + [0] * (plan["maximum_order"] - 1))
    center_emission, center_implicit = emission_jet(
        source, center_receiver, center_root, plan
    )
    center_models = []
    for identity, vector, denominator, clearance, clearance_branch in apparent_models(
        source, center_receiver, center_emission, plan
    ):
        rates = angular_rates(vector, plan)
        center_models.append(
            {
                "model": identity,
                "direction_normalized_coefficients": [jet_record(v) for v in vector],
                "angular_rate_normalized_coefficients": [jet_record(v) for v in rates],
                "angular_offset_Taylor_coefficients": [
                    [interval_record(I())]
                    + [
                        interval_record(rate.c[k - 1] / k)
                        for k in range(1, plan["maximum_order"] + 1)
                    ]
                    for rate in rates
                ],
                "deflection_denominator": interval_record(denominator),
                "ray_clearance_lower_bound": interval_record(clearance),
                "ray_clearance_branch": clearance_branch,
            }
        )
    return {
        "entry": entry,
        "receiver_support": interval_record(support),
        "uniform_root_proof": root_proof,
        "emission_normalized_coefficients": jet_record(emission),
        "implicit_recurrences": implicit,
        "source_cells": [
            [g, str(Q(start)), int(part)] for g, start, part in sorted(source.cells)
        ],
        "models": models,
        "center_receiver": interval_record(I(center)),
        "center_uniform_root_proof": center_proof,
        "center_emission_normalized_coefficients": jet_record(center_emission),
        "center_implicit_recurrences": center_implicit,
        "center_models": center_models,
        "declared_model_Taylor_remainder_computed": True,
        "physical_remainder_certified": False,
        "physical_service_model_equivalence_certified": False,
        "physical_TT_time_model_certified": False,
        "original_results_regraded": False,
        "old_reference_quality_replaced": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    raw = (a.run / "design-before-development.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != DESIGN_SHA:
        raise ValueError("Frozen remainder design changed")
    plan = json.loads(raw)
    source = Path(plan["source_fixture"])
    raw_manifest = (source / "manifest.json").read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest() != plan["source_manifest_sha256"]:
        raise ValueError("Original source manifest changed")
    if any(
        hashlib.sha256((source / p).read_bytes()).hexdigest() != digest
        for p, digest in json.loads(raw_manifest)["files"].items()
    ):
        raise ValueError("Original source fixture changed")
    entry = next(e for e in plan["development"] + plan["fresh"] if e["id"] == a.context)
    status = 0
    try:
        result = analyze(plan, entry)
    except (ValueError, ZeroDivisionError, StopIteration) as error:
        status = 2
        result = {
            "entry": entry,
            "status": "unqualified_declared_model_bound",
            "error": repr(error),
            "required_models": 8,
            "declared_model_Taylor_remainder_computed": False,
            "physical_remainder_certified": False,
            "original_results_regraded": False,
            "production_acceptance_exit_code": 2,
            "retained_overall_numeric_gate_exit_code": 1,
            "full_goal_complete": False,
        }
    with a.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(
        a.context,
        "all eight source Taylor profiles computed" if not status else result["error"],
        flush=True,
    )
    sys.exit(status)


if __name__ == "__main__":
    main()
