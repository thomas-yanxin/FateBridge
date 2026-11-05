"""Independent raw-derivative/Bernstein proof replay of named-model remainders.

Imports no normalized Taylor producer, its AD algebra or Chebyshev evaluator.
Every saved coefficient must cover this separate higher-derivative recurrence.
"""

import argparse
import hashlib
import json
import math
import struct
from fractions import Fraction as Q
from itertools import product
from pathlib import Path

from scripts.verify_astrodice_observer_clock import (
    K,
    Source,
    add,
    cover,
    divide,
    independent_pi,
    mul,
    neg,
    parse,
    root,
    rounded,
    square,
    sub,
)
from scripts.verify_astrodice_vector_clock import bernstein_bounds, derivative

DESIGN_SHA = "654e43fed5db8f17f57adecf9c1e339e8c42ea2e1a6b2166cd7a91840eb6a63d"
SRS = Q("0.0000000197412574336")


class R:
    """Unnormalized derivatives using explicit binomial Leibniz rules."""

    def __init__(self, derivatives):
        if not derivatives:
            raise ValueError("Empty raw derivative sequence")
        self.v = tuple(x if isinstance(x, tuple) else rounded(x) for x in derivatives)

    def cast(self, value):
        if isinstance(value, R):
            if len(value.v) != len(self.v):
                raise ValueError("Independent derivative order mismatch")
            return value
        return R([value] + [0] * (len(self.v) - 1))

    def __neg__(self):
        return R([neg(x) for x in self.v])

    def __add__(self, other):
        other = self.cast(other)
        return R([add(a, b) for a, b in zip(self.v, other.v)])

    __radd__ = __add__

    def __sub__(self, other):
        return self + -self.cast(other)

    def __rsub__(self, other):
        return self.cast(other) - self

    def __mul__(self, other):
        other = self.cast(other)
        result = []
        for n in range(len(self.v)):
            total = rounded(0)
            for k in range(n + 1):
                term = (
                    square(self.v[k])
                    if self is other and k == n - k
                    else mul(self.v[k], other.v[n - k])
                )
                total = add(total, mul(rounded(math.comb(n, k)), term))
            result.append(total)
        return R(result)

    __rmul__ = __mul__

    def reciprocal(self):
        values = [divide(rounded(1), self.v[0])]
        for n in range(1, len(self.v)):
            total = rounded(0)
            for k in range(1, n + 1):
                total = add(
                    total, mul(rounded(math.comb(n, k)), mul(self.v[k], values[n - k]))
                )
            values.append(divide(neg(total), self.v[0]))
        return R(values)

    def __truediv__(self, other):
        return self * self.cast(other).reciprocal()

    def __rtruediv__(self, other):
        return self.cast(other) * self.reciprocal()

    def sqrt(self):
        first = root(self.v[0])
        if len(self.v) > 1 and first[0] <= 0:
            raise ValueError("Independent nonpositive root derivative domain")
        values = [first]
        for n in range(1, len(self.v)):
            total = rounded(0)
            for k in range(1, n):
                term = (
                    square(values[k]) if k == n - k else mul(values[k], values[n - k])
                )
                total = add(total, mul(rounded(math.comb(n, k)), term))
            values.append(divide(sub(self.v[n], total), mul(rounded(2), first)))
        return R(values)

    def derivative(self):
        if len(self.v) < 2:
            raise ValueError("Independent missing derivative")
        return R(self.v[1:])

    def truncate(self, order):
        if order >= len(self.v):
            raise ValueError("Independent cannot invent derivative orders")
        return R(self.v[: order + 1])


def dot(a, b):
    total = a[0].cast(0)
    for x, y in zip(a, b):
        total = total + x * y
    return total


def subtract(a, b):
    return [x - y for x, y in zip(a, b)]


def plus(a, b):
    return [x + y for x, y in zip(a, b)]


def times(a, scalar):
    return [x * scalar for x in a]


def length(a):
    return dot(a, a).sqrt()


def normalize(a):
    return times(a, 1 / length(a))


def vector_product(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def finite_segment_clearance(earth_sun, ray):
    p = normalize(ray)
    projection = neg(dot(earth_sun, p).v[0])
    distance = length(ray).v[0]
    if projection[1] <= 0:
        return length(earth_sun).v[0], "observer_endpoint"
    if projection[0] >= distance[1]:
        return length(plus(earth_sun, ray)).v[0], "source_endpoint"
    if 0 <= projection[0] <= projection[1] <= distance[0]:
        return length(vector_product(p, earth_sun)).v[0], "interior"
    raise ValueError("Independent finite-segment branch unresolved")


class DerivativeSource(Source):
    """Source derivatives via independent power/Bernstein and Taylor composition."""

    def group_derivatives(self, epoch, group):
        Source.group(self, epoch.v[0], group)
        low, high = epoch.v[0]
        raw = next(
            r
            for r in self.records
            if Q(struct.unpack_from("<d", r)[0])
            <= low
            <= high
            < Q(struct.unpack_from("<d", r, 8)[0])
        )
        start, end = map(Q, struct.unpack_from("<2d", raw))
        width = (end - start) / self.pointers[group][2]
        part = (low - start) // width
        begin = start + part * width
        a, b = 2 * (low - begin) / width - 1, 2 * (high - begin) / width - 1
        order = len(epoch.v) - 1
        delta = R([rounded(0), *epoch.v[1:]])
        powers = [epoch.cast(1)]
        for _ in range(order):
            powers.append(powers[-1] * delta)
        output = []
        for polynomial in self.cache[(start, group, part)]:
            series = epoch.cast(0)
            current = polynomial
            for k in range(order + 1):
                lo, hi = bernstein_bounds(current, a, b) if current else (Q(), Q())
                coefficient = rounded(
                    lo * (2 / width) ** k / math.factorial(k),
                    hi * (2 / width) ** k / math.factorial(k),
                )
                series = series + powers[k] * coefficient
                current = derivative(current)
            output.append(series)
        return output

    def state_derivatives(self, epoch, body):
        if body == "Earth":
            emb, moon = [self.group_derivatives(epoch, g) for g in (2, 9)]
            return [e - m / (1 + self.emrat) for e, m in zip(emb, moon)]
        if body not in ("Venus", "Sun"):
            raise ValueError("Independent unsupported derivative body")
        return self.group_derivatives(epoch, {"Venus": 1, "Sun": 10}[body])


def from_normalized(boxes):
    return R(
        [mul(parse(pair), rounded(math.factorial(k))) for k, pair in enumerate(boxes)]
    )


def coefficient(raw, k):
    # An exact positive integer rescale needs no independently rounded reciprocal.
    factor = math.factorial(k)
    return rounded(raw.v[k][0] / factor, raw.v[k][1] / factor)


def verify_uniform_root(source, reception, stored, plan):
    a, b = reception
    expected = rounded(a - Q(plan["initial_emitter_margin_days"]), b, scale=1 << 256)
    if (
        parse(stored["initial"]) != expected
        or len(stored["iterations"]) != plan["root_iterations"]
    ):
        raise ValueError("Uniform root design changed")
    earth = source.state_derivatives(R([reception]), "Earth")[:3]
    target = source.state_derivatives(R([expected]), "Venus")
    contraction = length(target[3:]).v[0][1] * K
    declared = Q(stored["contraction_upper"])
    if not contraction <= declared < 1:
        raise ValueError("Uniform contraction proof failed")

    def image(te):
        ray = subtract(source.state_derivatives(R([te]), "Venus")[:3], earth)
        return sub(reception, mul(rounded(K), length(ray).v[0]))

    cover(image(expected), stored["initial_image"])
    initial_image = parse(stored["initial_image"])
    if not expected[0] <= initial_image[0] <= initial_image[1] <= expected[1]:
        raise ValueError("Uniform invariant set not established")
    current = expected
    for step in stored["iterations"]:
        if parse(step["input"]) != current:
            raise ValueError("Uniform root chain changed")
        cover(image(current), step["image"])
        lo, hi = parse(step["image"])
        actual = max(current[0], lo), min(current[1], hi)
        if parse(step["next"]) != actual:
            raise ValueError("Uniform root intersection changed")
        current = actual
    if current != parse(stored["root"]):
        raise ValueError("Uniform root result changed")
    return current


def verify_implicit(source, reception, root_box, data, plan):
    te = from_normalized(data["emission_normalized_coefficients"])
    if te.v[0] != root_box:
        raise ValueError("Implicit root/coefficient identity changed")
    target = source.state_derivatives(R([root_box]), "Venus")
    earth = source.state_derivatives(R([reception.v[0]]), "Earth")
    direction = normalize(subtract(target[:3], earth[:3]))
    denominator = (1 + K * dot(direction, target[3:])).v[0]
    stored = data["implicit_recurrences"]
    cover(denominator, stored["denominator"])
    if denominator[0] <= Q(plan["minimum_implicit_denominator"]):
        raise ValueError("Independent implicit denominator failed")
    if len(stored["recurrences"]) != plan["maximum_order"]:
        raise ValueError("An implicit derivative order was dropped")
    for k, step in enumerate(stored["recurrences"], 1):
        if (
            step["order"] != k
            or step["coefficient"] != data["emission_normalized_coefficients"][k]
        ):
            raise ValueError("Implicit recurrence population changed")
        emitted = R([*te.v[:k], rounded(0)])
        received = reception.truncate(k)
        ray = subtract(
            source.state_derivatives(emitted, "Venus")[:3],
            source.state_derivatives(received, "Earth")[:3],
        )
        residual = emitted + K * length(ray) - received
        normalized = coefficient(residual, k)
        cover(normalized, step["residual_with_highest_zero"])
        cover(divide(neg(normalized), denominator), step["coefficient"])
    return te


def model_directions(source, received, emitted, plan):
    earth, venus, sun, delayed_sun = [
        source.state_derivatives(t, b)
        for t, b in (
            (received, "Earth"),
            (emitted, "Venus"),
            (received, "Sun"),
            (emitted, "Sun"),
        )
    ]
    direction = normalize(subtract(venus[:3], earth[:3]))
    earth_sun = subtract(earth[:3], sun[:3])
    radius, radial = length(earth_sun), normalize(earth_sun)
    beta = times(earth[3:], K)
    beta2 = dot(beta, beta)
    if beta2.v[0][1] >= Q(plan["maximum_beta_squared"]):
        raise ValueError("Independent beta bound failed")
    clearance, branch = finite_segment_clearance(
        earth_sun, subtract(venus[:3], earth[:3])
    )
    if clearance[0] <= Q(plan["minimum_light_segment_clearance_AU"]):
        raise ValueError("Independent ray clearance failed")
    positions = {
        "exact_emission": delayed_sun[:3],
        "linearized_emission": subtract(sun[:3], times(sun[3:], received - emitted)),
    }
    for sr, sun_epoch, potential in product(
        ("full_Lorentz", "normalized_second_order"), positions, (0, 1)
    ):
        q = normalize(subtract(venus[:3], positions[sun_epoch]))
        denominator = dot(q, plus(q, radial))
        if denominator.v[0][0] <= Q(plan["minimum_deflection_denominator"]):
            raise ValueError("Independent deflection bound failed")
        deflected = normalize(
            plus(
                direction,
                times(
                    vector_product(direction, vector_product(radial, q)),
                    SRS / radius / denominator,
                ),
            )
        )
        pb = dot(deflected, beta)
        if sr == "full_Lorentz":
            gamma_inverse = (1 - beta2).sqrt()
            vec = plus(
                times(deflected, gamma_inverse),
                times(beta, 1 + pb / (1 + gamma_inverse)),
            )
        else:
            vec = plus(
                times(deflected, 1 - pb + pb * pb - beta2 / 2), times(beta, 1 - pb / 2)
            )
        proper = normalize(
            plus(
                vec,
                times(subtract(beta, times(deflected, pb)), potential * SRS / radius),
            )
        )
        yield [sr, sun_epoch, potential], proper, denominator.v[0], clearance, branch


def rate_derivatives(vector, plan):
    dx, dy, dz = [v.derivative() for v in vector]
    x, y, z = [v.truncate(len(v.v) - 2) for v in vector]
    r2 = x * x + y * y
    if r2.v[0][0] <= Q(plan["minimum_rho_squared"]):
        raise ValueError("Independent angular pole guard failed")
    rho = r2.sqrt()
    radial_rate = (x * dx + y * dy) / rho
    factor = divide(rounded(648000), independent_pi())
    return [
        (x * dy - y * dx) / r2 * factor,
        (rho * dz - z * radial_rate) / (r2 + z * z) * factor,
    ]


def verify(plan, entry, data):
    if data["entry"] != entry:
        raise ValueError("Remainder context changed")
    for field in (
        "physical_remainder_certified",
        "physical_service_model_equivalence_certified",
        "physical_TT_time_model_certified",
        "original_results_regraded",
        "old_reference_quality_replaced",
        "full_goal_complete",
    ):
        if data[field]:
            raise ValueError("Named model lemma was promoted")
    if (
        data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Original gates changed")
    center = Q(entry["receiver_TDB_JD"])
    radius = Q(plan["maximum_receiver_radius_seconds"], 86400)
    expected = rounded(center - radius, center + radius, scale=1 << 256)
    if parse(data["receiver_support"]) != expected:
        raise ValueError("The whole fixed interval was narrowed")
    source = DerivativeSource(Path(plan["source_fixture"]), entry["source_window"])
    root_box = verify_uniform_root(source, expected, data["uniform_root_proof"], plan)
    received = R([expected, 1] + [0] * (plan["maximum_order"] - 1))
    emitted = verify_implicit(source, received, root_box, data, plan)
    if len(data["models"]) != 8:
        raise ValueError("A model was omitted")
    total = 0
    for computed, saved in zip(
        model_directions(source, received, emitted, plan), data["models"], strict=True
    ):
        identity, direction, denominator, clearance, branch = computed
        if saved["model"] != identity:
            raise ValueError("Model identity/order changed")
        cover(denominator, saved["deflection_denominator"])
        cover(clearance, saved["ray_clearance_lower_bound"])
        if saved["ray_clearance_branch"] != branch:
            raise ValueError("Finite-ray clearance branch changed")
        for axis in range(3):
            if (
                len(saved["direction_normalized_coefficients"][axis])
                != plan["maximum_order"] + 1
            ):
                raise ValueError("A direction derivative order was omitted")
            for k, pair in enumerate(saved["direction_normalized_coefficients"][axis]):
                cover(coefficient(direction[axis], k), pair)
                total += 1
        rates = rate_derivatives(direction, plan)
        for axis in range(2):
            if (
                len(saved["angular_rate_normalized_coefficients"][axis])
                != plan["maximum_order"]
            ):
                raise ValueError("An angular derivative order was omitted")
            for k, pair in enumerate(
                saved["angular_rate_normalized_coefficients"][axis]
            ):
                cover(coefficient(rates[axis], k), pair)
                total += 1
        expected_windows = list(
            product(plan["windows_seconds"], plan["full_polynomial_degrees"])
        )
        if [
            (v["window_seconds"], v["full_degree"])
            for v in saved["all_window_remainders"]
        ] != expected_windows:
            raise ValueError("A window or full degree was dropped")
        for row in saved["all_window_remainders"]:
            h, degree = Q(row["window_seconds"], 86400), row["full_degree"]
            for axis in range(2):
                coefficient_bound = max(
                    map(
                        abs,
                        parse(
                            saved["angular_rate_normalized_coefficients"][axis][degree]
                        ),
                    )
                )
                pos, speed = (
                    coefficient_bound * h ** (degree + 1) / (degree + 1),
                    coefficient_bound * h**degree,
                )
                if (
                    Q(row["position_remainder_arcsec"][axis]) != pos
                    or Q(row["derivative_remainder_arcsec_per_source_day"][axis])
                    != speed
                ):
                    raise ValueError("Taylor factorial/remainder was altered")
            position = list(map(Q, row["position_remainder_arcsec"]))
            speed = list(map(Q, row["derivative_remainder_arcsec_per_source_day"]))
            if Q(row["joint_position_bound_squared"]) != sum(
                (v * v for v in position), Q()
            ) or Q(row["joint_rate_bound_squared"]) != sum((v * v for v in speed), Q()):
                raise ValueError("Joint coordinate remainder norm changed")
    center_support = rounded(center, scale=1 << 256)
    if (
        parse(data["center_receiver"]) != center_support
        or len(data["center_models"]) != 8
    ):
        raise ValueError("Center Taylor control or profile population changed")
    center_root = verify_uniform_root(
        source, center_support, data["center_uniform_root_proof"], plan
    )
    center_received = R([center_support, 1] + [0] * (plan["maximum_order"] - 1))
    center_data = {
        "emission_normalized_coefficients": data[
            "center_emission_normalized_coefficients"
        ],
        "implicit_recurrences": data["center_implicit_recurrences"],
    }
    center_emitted = verify_implicit(
        source, center_received, center_root, center_data, plan
    )
    offset_count = 0
    for computed, saved in zip(
        model_directions(source, center_received, center_emitted, plan),
        data["center_models"],
        strict=True,
    ):
        identity, direction, denominator, clearance, branch = computed
        if saved["model"] != identity:
            raise ValueError("A center source profile changed")
        cover(denominator, saved["deflection_denominator"])
        cover(clearance, saved["ray_clearance_lower_bound"])
        if saved["ray_clearance_branch"] != branch:
            raise ValueError("Center finite-ray clearance branch changed")
        for axis in range(3):
            if (
                len(saved["direction_normalized_coefficients"][axis])
                != plan["maximum_order"] + 1
            ):
                raise ValueError("Center direction derivative omitted")
            for k, pair in enumerate(saved["direction_normalized_coefficients"][axis]):
                cover(coefficient(direction[axis], k), pair)
                total += 1
        rates = rate_derivatives(direction, plan)
        for axis in range(2):
            if (
                len(saved["angular_rate_normalized_coefficients"][axis])
                != plan["maximum_order"]
                or len(saved["angular_offset_Taylor_coefficients"][axis])
                != plan["maximum_order"] + 1
            ):
                raise ValueError("Center angular derivative omitted")
            for k, pair in enumerate(
                saved["angular_rate_normalized_coefficients"][axis]
            ):
                cover(coefficient(rates[axis], k), pair)
                total += 1
            if parse(saved["angular_offset_Taylor_coefficients"][axis][0]) != (
                Q(),
                Q(),
            ):
                raise ValueError("The angular offset origin changed")
            offset_count += 1
            for k in range(1, plan["maximum_order"] + 1):
                raw_bound = rates[axis].v[k - 1]
                divisor = math.factorial(k)
                cover(
                    rounded(raw_bound[0] / divisor, raw_bound[1] / divisor),
                    saved["angular_offset_Taylor_coefficients"][axis][k],
                )
                offset_count += 1
    cells = sorted(
        [[group, str(start), int(part)] for start, group, part in source.cache]
    )
    if sorted(data["source_cells"]) != cells:
        raise ValueError("Source-cell dependency record changed")
    return {
        "context": entry["id"],
        "source_models_checked": 8,
        "normalized_direction_and_rate_coefficients_checked": total,
        "center_angular_offset_coefficients_checked": offset_count,
        "implicit_derivative_orders_checked": 2 * plan["maximum_order"],
        "root_steps_checked": 2 * plan["root_iterations"],
        "all_22_window_degree_combinations_checked": True,
        "strict_containment_used": True,
        "declared_model_Taylor_remainder_proved": True,
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
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    raw = (a.run / "design-before-development.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != DESIGN_SHA:
        raise ValueError("Frozen high derivative design changed")
    plan, data = json.loads(raw), json.loads(a.input.read_text())
    source = Path(plan["source_fixture"])
    raw_manifest = (source / "manifest.json").read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest() != plan[
        "source_manifest_sha256"
    ] or any(
        hashlib.sha256((source / p).read_bytes()).hexdigest() != h
        for p, h in json.loads(raw_manifest)["files"].items()
    ):
        raise ValueError("Independent original source identity failed")
    if not data.get("declared_model_Taylor_remainder_computed"):
        raise ValueError("Producer bound remains unqualified; retain first failure")
    entry = next(
        e for e in plan["development"] + plan["fresh"] if e["id"] == data["entry"]["id"]
    )
    result = verify(plan, entry, data)
    result["producer_sha256"] = hashlib.sha256(a.input.read_bytes()).hexdigest()
    with a.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(entry["id"], "independent raw derivative proof complete", flush=True)


if __name__ == "__main__":
    main()
