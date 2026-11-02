"""Replay apparent reference positions without its AD or Clenshaw code.

Original records are evaluated through direct Chebyshev basis recurrences;
deflection uses the scalar dot-product identity. Exact Lagrange weights check
the recorded derivatives. Shared source physics is not observational truth.
"""

import argparse
import hashlib
import json
import math
import re
import struct
from decimal import Decimal as N
from decimal import localcontext
from fractions import Fraction as F
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vec_dot(a, b):
    return sum((x * y for x, y in zip(a, b)), N(0))


def magnitude(a):
    return vec_dot(a, a).sqrt()


def normalized(a):
    size = magnitude(a)
    if not size:
        raise ValueError("Scalar source ray is singular")
    return [x / size for x in a]


def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def coefficient_state(record, pointer, epoch):
    data = struct.unpack("<1018d", record)
    start, end = N.from_float(data[0]), N.from_float(data[1])
    offset, count, parts = pointer
    width = (end - start) / parts
    part = int((epoch - start) // width)
    if not start <= epoch < end or not 0 <= part < parts:
        raise ValueError("Scalar source epoch outside record")
    x = 2 * (epoch - start - part * width) / width - 1
    basis, derivative = [N(1), x], [N(0), N(1)]
    for _ in range(2, count):
        derivative.append(2 * basis[-1] + 2 * x * derivative[-1] - derivative[-2])
        basis.append(2 * x * basis[-1] - basis[-2])
    position, velocity = [], []
    for axis in range(3):
        first = offset - 1 + (3 * part + axis) * count
        values = [N.from_float(v) for v in data[first : first + count]]
        position.append(sum((a * b for a, b in zip(values, basis)), N(0)))
        velocity.append(
            sum((a * b for a, b in zip(values, derivative)), N(0)) * 2 / width
        )
    return position + velocity


class ScalarReader:
    def __init__(self, fixture, window):
        header = (fixture / "header.bin").read_bytes()
        self.au, self.emrat = map(N.from_float, struct.unpack_from("<2d", header, 2680))
        self.pointers = [
            struct.unpack_from("<3i", header, 2696 + i * 12) for i in range(12)
        ]
        data = (fixture / f"record-responses/case-{window:02}.bin").read_bytes()
        self.records = [data[i : i + 8144] for i in range(0, len(data), 8144)]
        self.cache = {}

    def group(self, epoch, group):
        for record in self.records:
            lo, hi = map(N.from_float, struct.unpack_from("<2d", record))
            if lo <= epoch < hi:
                return coefficient_state(record, self.pointers[group], epoch)
        raise ValueError("Scalar epoch outside original window")

    def state(self, epoch, body):
        key = (epoch, body)
        if key not in self.cache:
            if body == "Earth":
                state = [
                    a - b / (1 + self.emrat)
                    for a, b in zip(self.group(epoch, 2), self.group(epoch, 9))
                ]
            else:
                state = self.group(epoch, {"Mercury": 0, "Venus": 1, "Sun": 10}[body])
            self.cache[key] = [x / self.au for x in state]
        return self.cache[key]


def direction(reader, body, epoch, profile):
    earth, sun, initial = [reader.state(epoch, name) for name in ("Earth", "Sun", body)]
    au, c, day = N(149597870700), N(299792458), N(86400)
    delay = N(0)
    rough = initial[:3]
    for _ in range(2):
        delay = magnitude(sub(rough, earth[:3])) * au / c / day
        rough = [p - v * delay for p, v in zip(initial[:3], initial[3:])]
    emitted = reader.state(epoch - delay, body)
    ray = sub(emitted[:3], earth[:3])
    distance = magnitude(ray)
    u = normalized(ray)
    e_ray = sub(earth[:3], sun[:3])
    solar_distance, e = magnitude(e_ray), normalized(e_ray)
    solar_retarded = [p - v * delay for p, v in zip(sun[:3], sun[3:])]
    q = normalized(sub(emitted[:3], solar_retarded))
    cross = [
        u[1] * e[2] - u[2] * e[1],
        u[2] * e[0] - u[0] * e[2],
        u[0] * e[1] - u[1] * e[0],
    ]
    impact = (
        magnitude(cross)
        * solar_distance
        / N.from_float((959.63 / 3600) * (math.pi / 180))
    )
    if impact >= 1:
        mass = N(1)
    elif impact <= 0:
        mass = N(0)
    else:
        for (r0, m0), (r1, m1) in zip(profile, profile[1:]):
            if r1 <= impact <= r0:
                mass = m0 + (impact - r0) * (m1 - m0) / (r1 - r0)
                break
        else:
            raise ValueError("Scalar solar profile does not bracket impact")
    strength = (
        2 * N.from_float(1.32712440017987e20) * mass / c / c / au / solar_distance
    )
    denominator = (
        vec_dot([a + b for a, b in zip(q, e)], [a + b for a, b in zip(q, e)]) / 2
    )
    uq, ue = vec_dot(u, q), vec_dot(u, e)
    deflected = [
        distance * (p + strength / denominator * (uq * ee - ue * qq))
        for p, ee, qq in zip(u, e, q)
    ]
    beta = [v * au / c / day for v in earth[3:]]
    length = magnitude(deflected)
    gamma_inverse = (1 - vec_dot(beta, beta)).sqrt()
    projection = vec_dot(deflected, beta) / length
    apparent = [
        (gamma_inverse * p + (1 + projection / (1 + gamma_inverse)) * length * v)
        / (1 + projection)
        for p, v in zip(deflected, beta)
    ]
    return normalized(apparent)


def lagrange_weights(nodes):
    result = []
    for j in nodes:
        value = F(1)
        for k in nodes:
            if k != j:
                value *= F(-k, j - k)
        result.append(value * sum((F(-1, k) for k in nodes if k != j), F(0)))
    return result


def audit(run, fixture, reference_path):
    manifest = fixture / "manifest.json"
    if (
        digest(manifest)
        != "96f8c9b6a8b2fde8f5f11b43316928fc2694fb90ab89c7d438bc7d4ef5aa9d30"
    ):
        raise ValueError("Frozen original record manifest changed")
    for name, expected in json.loads(manifest.read_text())["files"].items():
        if digest(fixture / name) != expected:
            raise ValueError("Frozen original coefficient source changed")
    protocol_path = run / "protocol-before-development.json"
    protocol = json.loads(protocol_path.read_text())
    if (
        protocol.get("position_line_arcsec") != 0.02
        or protocol.get("rate_line_arcsec_per_day") != 0.002
        or protocol.get("reference_precisions") != [70, 100]
        or protocol.get("reference_precision_component_line") != "1e-45"
        or protocol.get("reference_fd_steps_days") != ["1/1048576", "1/2097152"]
        or protocol.get("reference_fd_order") != 6
        or protocol.get("reference_fd_vs_AD_line_arcsec_per_day") != 1e-7
        or protocol.get("require_same_mass_and_polynomial_cells") is not True
    ):
        raise ValueError("Frozen source-reference qualification policy changed")
    reference = json.loads(reference_path.read_text())
    if (
        reference["protocol_sha256"] != digest(protocol_path)
        or reference["candidate_imported"]
    ):
        raise ValueError("Reference protocol or independent-source identity changed")
    cases = protocol[reference["group"]]
    if [r["id"] for r in reference["rows"]] != [c["id"] for c in cases]:
        raise ValueError("Reference condition population changed")
    for name, expected in protocol["source_artifact_sha256"].items():
        if digest(run / name) != expected:
            raise ValueError("Pinned physical model source changed")
    # A self-consistent parameter file is not evidence that it matches the
    # named author. Re-extract the table directly from the pinned source.
    if (
        digest(run / "sweph.c")
        != "80761ccfae7cd7207a33559d8898b9c5386cced609cfaebbbbf050f7a80ddc4f"
        or digest(run / "sweph.h")
        != "8e44b9c00d23a0b583581f17fc6798ea376649d2517abbb556ee1b1aff6a138a"
    ):
        raise ValueError("Unverified named native-source version")
    source_table = re.search(
        r"static const struct meff_ele eff_arr\[\] = \{(.*?)\n\};",
        (run / "sweph.c").read_text(),
        re.S,
    )
    if source_table is None:
        raise ValueError("Missing author solar-mass table")
    pairs = [
        list(pair)
        for pair in re.findall(r"\{([0-9.]+),\s*([0-9.]+)\}", source_table.group(1))
    ]
    declared_profile = json.loads((run / "source-solar-profile.json").read_text())
    if (
        len(pairs) != 101
        or pairs != declared_profile["radius_mass_pairs"]
        or declared_profile["source_sha256"] != digest(run / "sweph.c")
    ):
        raise ValueError("Declared solar-mass parameters differ from named source")
    if (
        protocol["source_GM_binary64"] != float(1.32712440017987e20).hex()
        or protocol["source_Sun_radius_binary64"]
        != ((959.63 / 3600) * (math.pi / 180)).hex()
    ):
        raise ValueError("Declared source constants changed")
    profile = [
        (N.from_float(float(r)), N.from_float(float(m)))
        for r, m in json.loads((run / "source-solar-profile.json").read_text())[
            "radius_mass_pairs"
        ]
    ]
    weights = lagrange_weights((-3, -2, -1, 1, 2, 3))
    max_position, max_rate = N(0), 0.0
    total_points = 0
    for row, case in zip(reference["rows"], cases):
        if any(row[k] != case[k] for k in ("date_tdb", "body", "window_index", "role")):
            raise ValueError("Reference condition fields changed")
        if (
            row["position_status"] != "qualified_under_declared_source_position_model"
            or row["status"] != "qualified_under_declared_continuous_source_model"
        ):
            raise ValueError("This frozen replay has an unqualified source row")
        if row.get("same_profile_and_polynomial_cells") is not True:
            raise ValueError("Qualified reference lost its source-cell checks")
        reader = ScalarReader(fixture, case["window_index"])
        with localcontext() as context:
            context.prec = 100
            epoch = N.from_float(row["native_numeric_argument"])
            center = direction(reader, case["body"], epoch, profile)
            for saved in row["position_centers"] + row["centers"]:
                difference = max(
                    abs(a - N(b)) for a, b in zip(center, saved["direction_icrf"])
                )
                max_position = max(max_position, difference)
                if difference > N(protocol["reference_precision_component_line"]):
                    raise ValueError("Independent scalar apparent position differs")
            expected_offsets = [
                str(k * F(h))
                for h in protocol["reference_fd_steps_days"]
                for k in (-3, -2, -1, 1, 2, 3)
            ]
            if [
                p["offset_days"] for p in row["finite_difference_samples"]
            ] != expected_offsets:
                raise ValueError("Reference derivative probe plan changed")
            probes = []
            for probe in row["finite_difference_samples"]:
                offset = F(probe["offset_days"])
                point = direction(
                    reader,
                    case["body"],
                    epoch + N(offset.numerator) / N(offset.denominator),
                    profile,
                )
                difference = max(
                    abs(a - N(b))
                    for a, b in zip(point, probe["sample"]["direction_icrf"])
                )
                max_position = max(max_position, difference)
                if difference > N(protocol["reference_precision_component_line"]):
                    raise ValueError("Independent scalar stencil position differs")
                probes.append(point)
            gradient = list(map(N, row["centers"][-1]["derivative_per_day"]))
            for index, h in enumerate(protocol["reference_fd_steps_days"]):
                h = F(h)
                step = N(h.numerator) / N(h.denominator)
                estimates = [
                    sum(
                        (
                            (N(w.numerator) / N(w.denominator)) * point[axis]
                            for w, point in zip(
                                weights, probes[index * 6 : index * 6 + 6]
                            )
                        ),
                        N(0),
                    )
                    / step
                    for axis in range(3)
                ]
                difference = math.hypot(
                    *(float(a - b) for a, b in zip(estimates, gradient))
                ) * (180 * 3600 / math.pi)
                max_rate = max(max_rate, difference)
                if difference > protocol["reference_fd_vs_AD_line_arcsec_per_day"]:
                    raise ValueError("Independent scalar derivative differs from AD")
            total_points += 13
    return {
        "method_id": "independent_scalar_basis_apparent_source_replay_v1",
        "exit_code": 0,
        "group": reference["group"],
        "rows": len(cases),
        "planned_center_and_probe_evaluations": total_points,
        "maximum_direction_component_difference": str(max_position),
        "maximum_scalar_FD_vs_AD_arcsec_per_day": max_rate,
        "reference_population_or_grades_changed": False,
        "full_goal_complete": False,
        "scope": "Independent scalar replay of the declared continuous source model and local derivative checks. Shared dynamics, source correction definition and native display frame remain explicit; no TT conversion or observations are certified.",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "fixture", "reference", "output"):
        p.add_argument("--" + name, required=True, type=Path)
    args = p.parse_args()
    result = audit(args.run, args.fixture, args.reference)
    with args.output.open("x") as file:
        file.write(json.dumps(result, indent=2) + "\n")
    print(result)
