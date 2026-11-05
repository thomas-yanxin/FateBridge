"""Independent source identities, integer blossom bounds and 288-bit replay.

Does not import the curve producer, its power conversion, subdivision or metric
implementation. Source polynomials remain a declared model, not observations.
"""

import argparse
import hashlib
import json
import math
import struct
from fractions import Fraction as Q
from functools import lru_cache
from pathlib import Path

from scripts.astrodice_de441_records import clenshaw_with_derivative
from scripts.verify_astrodice_observer_clock import (
    add,
    divide,
    mul,
    neg,
    root,
    rounded,
    square,
)
from scripts.verify_astrodice_swe_coefficients import unpack as decode_swe

PLAN_SHA = "fea80095836a3d5235a340fe4858ba901e78dfda6736e72cba921442d4b725e3"
RAW_SHA = "8aedd6aa3f2cdabbe345fd915f94dc2a57dfa8adbe879d599e912da347daa9aa"


class B:
    def __init__(self, value=0):
        self.v = value if isinstance(value, tuple) else rounded(value)

    @staticmethod
    def cast(x):
        return x if isinstance(x, B) else B(x)

    def __add__(self, x):
        return B(add(self.v, self.cast(x).v))

    __radd__ = __add__

    def __neg__(self):
        return B(neg(self.v))

    def __sub__(self, x):
        return self + -self.cast(x)

    def __mul__(self, x):
        return self.square() if self is x else B(mul(self.v, self.cast(x).v))

    __rmul__ = __mul__

    def __truediv__(self, x):
        return B(divide(self.v, self.cast(x).v))

    def __rtruediv__(self, x):
        return self.cast(x) / self

    def square(self):
        return B(square(self.v))

    def sqrt(self):
        return B(root(self.v))


@lru_cache(maxsize=1)
def independent_pi():
    def series(n, terms):
        value = Q()
        for k in range(terms):
            value += Q((-1) ** k, (2 * k + 1) * n ** (2 * k + 1))
        next_value = value + Q((-1) ** terms, (2 * terms + 1) * n ** (2 * terms + 1))
        return B(rounded(min(value, next_value), max(value, next_value)))

    return 16 * series(5, 96) - 4 * series(239, 40)


def vector_metrics(q, w, e, f, scales):
    if len(scales) != 4 or any(Q(x) <= 0 for x in scales):
        raise ValueError("Independent positive norm scaling missing")
    iterator = iter(map(Q, scales))

    def length(v):
        scale = next(iterator)
        v = [x / scale for x in v]
        return sum((x.square() for x in v), B()).sqrt() * scale

    def dot(a, b):
        return sum((x * y for x, y in zip(a, b)), B())

    p = [x + y for x, y in zip(q, e)]
    rp, rq = length(p), length(q)
    ip, iq = 1 / rp, 1 / rq
    dr = (2 * dot(q, e) + dot(e, e)) / (rp + rq)
    di = -dr / (rp * rq)
    d3 = di * (ip.square() + ip * iq + iq.square())
    a = dot(q, w)
    da = dot(q, f) + dot(e, w) + dot(e, f)
    cube = ip.square() * ip
    delta = [x * ip + y * di for x, y in zip(e, q)]
    velocity = [
        ff * ip + ww * di - ee * (a + da) * cube - qq * (da * cube + a * d3)
        for qq, ww, ee, ff in zip(q, w, e, f)
    ]
    return [
        length(delta) * (648000 / independent_pi()),
        length(velocity) * (648000 / independent_pi()),
    ]


@lru_cache(maxsize=1024)
def blossom_matrix(n, leaf, depth):
    step = 2**depth
    left, right = leaf, leaf + 1
    result = []
    for i in range(n + 1):
        row = []
        for j in range(n + 1):
            total = 0
            for k in range(max(0, j - (n - i)), min(i, j) + 1):
                total += (
                    math.comb(i, k)
                    * math.comb(n - i, j - k)
                    * left ** (j - k)
                    * (step - left) ** (n - i - j + k)
                    * right**k
                    * (step - right) ** (i - k)
                )
            row.append(total)
        if sum(row) != step**n:
            raise ValueError("Independent blossom weights not a partition of unity")
        result.append(row)
    return result


@lru_cache(maxsize=1024)
def leaf_hulls(coefficients, depth):
    degree = len(coefficients) - 1
    denominator = math.lcm(*(x.denominator for x in coefficients))
    numerators = [x.numerator * (denominator // x.denominator) for x in coefficients]
    out = []
    for leaf in range(2**depth):
        controls = [
            sum(a * b for a, b in zip(row, numerators))
            for row in blossom_matrix(degree, leaf, depth)
        ]
        divisor = denominator * (2**depth) ** degree
        out.append((Q(min(controls), divisor), Q(max(controls), divisor)))
    return out


def bernstein_at(coefficients, u):
    n = len(coefficients) - 1
    return sum(
        (
            c * math.comb(n, i) * u**i * (1 - u) ** (n - i)
            for i, c in enumerate(coefficients)
        ),
        Q(),
    )


def bernstein_velocity(coefficients, width):
    n = len(coefficients) - 1
    return [n * (b - a) / width for a, b in zip(coefficients, coefficients[1:])] or [
        Q()
    ]


def binary64(q):
    q = Q(q)
    if not q:
        return Q()
    if q < 0:
        return -binary64(-q)
    exponent = q.numerator.bit_length() - q.denominator.bit_length()
    while Q(2) ** exponent > q:
        exponent -= 1
    while Q(2) ** (exponent + 1) <= q:
        exponent += 1
    unit = Q(2) ** (exponent - 52)
    quotient = q / unit
    integer, remainder = divmod(quotient.numerator, quotient.denominator)
    integer += 2 * remainder > quotient.denominator or (
        2 * remainder == quotient.denominator and integer % 2 == 1
    )
    return integer * unit


def swe_chebyshev(coefficients, x):
    # A polynomial remains defined when the separately rounded native origin
    # puts an exact header-grid endpoint microscopically outside[-1,1].
    t0, t1, d0, d1 = Q(1), x, Q(), Q(1)
    value = coefficients[0]
    velocity = Q()
    for k, c in enumerate(coefficients[1:], 1):
        if k > 1:
            t0, t1, d0, d1 = t1, 2 * x * t1 - t0, d1, 2 * t1 + 2 * x * d1 - d0
        value += c * t1
        velocity += c * d1
    return value, velocity


def descriptors(path):
    data = path.read_bytes()
    lines = data.split(b"\r\n", 3)
    offset = sum(len(x) + 2 for x in lines[:3])
    marker = data[offset : offset + 4]
    endian = {b"cba\0": "<", b"\0abc": ">"}[marker]
    offset += 4

    def read(fmt):
        nonlocal offset
        value = struct.unpack_from(endian + fmt, data, offset)
        offset += struct.calcsize(endian + fmt)
        return value

    _, edition, _, _, count = read("ii2dh")
    if edition != 441:
        raise ValueError("Independent source edition differs")
    ids = read(("i" if count > 256 else "h") * (count % 256))
    read("I5d")
    result = {}
    for body in ids:
        _, flags, ncoef, _ = read("iBBi")
        parameters = read("10d")
        if flags & 4:
            read(str(2 * ncoef) + "d")
        result[body] = {"flags": flags, "ncoef": ncoef, "parameters": parameters}
    return result


class IndependentSources:
    def __init__(self, run, case, segments):
        self.case, self.segments = case, segments
        self.paths = {
            body: Path(case["moon_file"] if body == 1 else case["planet_file"])
            for body in (1, 10, 2, 3)
        }
        self.descriptors = {
            body: descriptors(path)[body] for body, path in self.paths.items()
        }
        self.header = (run / "raw-source/header.bin").read_bytes()
        self.records = [
            p.read_bytes()
            for p in sorted((run / "raw-source" / case["id"]).glob("record-*.bin"))
        ]
        self.validated = set()

    def partition(self, low, high):
        points = {low, high}
        for desc in self.descriptors.values():
            start, end, width, *_ = map(Q, desc["parameters"])
            if low < start or high > end:
                raise ValueError("Independent source coverage missing")
            i = int((low - start) // width)
            while start + i * width < high:
                t = start + i * width
                if low < t < high:
                    points.add(t)
                i += 1
        for raw in self.records:
            a, b = map(Q, struct.unpack_from("<2d", raw))
            for group in (0, 1, 2, 9):
                parts = struct.unpack_from("<3i", self.header, 2696 + 12 * group)[2]
                for i in range(parts + 1):
                    t = a + (b - a) * i / parts
                    if low < t < high:
                        points.add(t)
        points = sorted(points)
        return list(zip(points, points[1:]))

    def sweep_segment(self, mid, body):
        path = self.paths[body]
        desc = self.descriptors[body]
        origin, _, span, *_ = map(Q, desc["parameters"])
        index = int((mid - origin) // span)
        key = f"{hashlib.sha256(path.read_bytes()).hexdigest()}:{body}:{index}"
        s = self.segments[key]
        if key not in self.validated:
            decoded = decode_swe(path, float(origin + (index + Q(1, 2)) * span), body)
            expected_start = binary64(origin + binary64(index * span))
            if (
                Q(s["segment_start"]) != expected_start
                or Q(s["span"]) != span
                or any(
                    s[k] != decoded[k]
                    for k in (
                        "ncoef",
                        "flags",
                        "last_significant_index",
                        "segment_index",
                        "packed_sizes",
                    )
                )
            ):
                raise ValueError("Independent SWE descriptor/normalizer differs")
            for a, b in zip(
                s["decoded_coefficients"], decoded["decoded_exact_coefficients"]
            ):
                if any(abs(Q(x) - y) > 8 * Q(math.ulp(x)) for x, y in zip(a, b)):
                    raise ValueError("Independent integer-packed input differs")
            if (
                max(
                    abs(x - float(y))
                    for a, b in zip(
                        s["rotated_coefficients"],
                        decoded["rotated_decimal_coefficients"],
                    )
                    for x, y in zip(a, b)
                )
                > 1e-14
            ):
                raise ValueError("Independent high precision rotation differs")
            self.validated.add(key)
        return key, s

    def swi(self, mid, t, body, profile):
        key, s = self.sweep_segment(mid, body)
        count = (
            s["ncoef"]
            if profile == "all_coefficients" or not s["flags"] & 2
            else s["last_significant_index"] + (profile == "index_plus_one")
        )
        x = 2 * (t - Q(s["segment_start"])) / Q(s["span"]) - 1
        out = []
        vel = []
        for c in s["rotated_coefficients"]:
            coefficients = list(map(Q, c[:count]))
            coefficients[0] /= 2
            p, v = swe_chebyshev(coefficients, x)
            out.append(p)
            vel.append(v * 2 / Q(s["span"]))
        return out + vel, key, count - 1

    def candidate(self, mid, t, body, profile):
        moon, mk, md = self.swi(mid, t, 1, profile)
        if body == "Moon":
            return moon, [mk], md
        target, tk, td = self.swi(mid, t, {"Mercury": 2, "Venus": 3}[body], profile)
        sun, sk, sd = self.swi(mid, t, 10, profile)
        denominator = Q((1 / 0.0123000383) + 1)
        return (
            [a - b + c / denominator for a, b, c in zip(target, sun, moon)],
            [mk, sk, tk],
            max(md, td, sd),
        )

    def group(self, mid, t, group):
        raw = next(
            r
            for r in self.records
            if Q(struct.unpack_from("<d", r)[0])
            <= mid
            < Q(struct.unpack_from("<d", r, 8)[0])
        )
        start, end = map(Q, struct.unpack_from("<2d", raw))
        offset, n, parts = struct.unpack_from("<3i", self.header, 2696 + group * 12)
        width = (end - start) / parts
        part = int((mid - start) // width)
        begin = start + part * width
        x = 2 * (t - begin) / width - 1
        if not -1 <= x <= 1:
            raise ValueError("Independent JPL source cell mismatch")
        values = struct.unpack("<1018d", raw)
        p = []
        v = []
        au = Q(struct.unpack_from("<d", self.header, 2680)[0])
        for axis in range(3):
            first = offset - 1 + (part * 3 + axis) * n
            value, velocity = clenshaw_with_derivative(
                list(map(Q, values[first : first + n])), x
            )
            p.append(value / au)
            v.append(velocity * 2 / width / au)
        return p + v, n - 1

    def reference(self, mid, t, body):
        moon, md = self.group(mid, t, 9)
        if body == "Moon":
            return moon, md
        target, td = self.group(mid, t, {"Mercury": 0, "Venus": 1}[body])
        emb, ed = self.group(mid, t, 2)
        denominator = 1 + Q(struct.unpack_from("<d", self.header, 2688)[0])
        return [a - b + c / denominator for a, b, c in zip(target, emb, moon)], max(
            md, td, ed
        )


def cover(pair, reported):
    for actual, declared in zip(pair, reported):
        lo, hi = map(Q, declared)
        if not lo <= actual.v[0] <= actual.v[1] <= hi:
            raise ValueError("Independent288bit result not contained")


def verify(run, path):
    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    if (
        sha(run / "plan-before-analysis.json") != PLAN_SHA
        or sha(run / "raw-source-before-evaluation.json") != RAW_SHA
    ):
        raise ValueError("Independent immutable plan/source receipt changed")
    plan = json.loads((run / "plan-before-analysis.json").read_text())
    report = json.loads(path.read_text())
    raw = json.loads((run / "raw-source-before-evaluation.json").read_text())
    for name, item in raw["records"].items():
        if sha(Path(name)) != item["sha256"]:
            raise ValueError("Original raw record changed")
    if sha(run / "raw-source/header.bin") != raw["full_header_sha256"]:
        raise ValueError("Original header changed")
    if report.get("status") == "evidence_unavailable":
        raise ValueError("Original unavailable condition remains unavailable")
    split, index = report["split"], report["case_index"]
    case = plan["cases"][split][index]
    if (
        report["protocol_sha256"] != PLAN_SHA
        or report["case"] != case
        or report["old_gates"] != {"production": 2, "overall": 1}
        or any(
            report[x] is not False
            for x in (
                "native_rounding_or_cache_selector_derivative_certified",
                "physical_TT_TDB_equivalence_certified",
                "original_failures_regraded",
            )
        )
    ):
        raise ValueError("Original source curve binding/claim changed")
    source = IndependentSources(run, case, report["segments"])
    low, high = Q(case["domain_start_exact"]), Q(case["domain_end_exact"])
    partition = source.partition(low, high)
    if [(Q(c["start_exact"]), Q(c["end_exact"])) for c in report["cells"]] != partition:
        raise ValueError("Complete full-domain population changed")
    root_identities = leaf_proofs = point_proofs = 0
    for ci, cell in enumerate(report["cells"]):
        a, b = partition[ci]
        mid = (a + b) / 2
        width = b - a
        if cell["cell_index"] != ci or list(cell["bodies"]) != plan["bodies"]:
            raise ValueError("Body/cell population changed")
        for body, profiles in cell["bodies"].items():
            if list(profiles) != plan["profiles"]:
                raise ValueError("Retention profile population changed")
            for profile, data in profiles.items():
                q = [[Q(x) for x in axis] for axis in data["q_bernstein"]]
                e = [[Q(x) for x in axis] for axis in data["error_bernstein"]]
                if (
                    len(q) != 3
                    or len(e) != 3
                    or any(not 1 <= len(c) <= 41 for c in q + e)
                ):
                    raise ValueError("Invalid source polynomial degree/axis")
                _, ids, pdegree = source.candidate(mid, mid, body, profile)
                _, qdegree = source.reference(mid, mid, body)
                if ids != data["source_segment_ids"]:
                    raise ValueError("Selected physical source segment changed")
                degree = max(pdegree, qdegree, max(map(len, q + e)) - 1)
                w = [bernstein_velocity(c, width) for c in q]
                f = [bernstein_velocity(c, width) for c in e]
                for k in range(degree + 1):
                    u = Q(k, degree) if degree else Q()
                    t = a + width * u
                    expected_p, _, _ = source.candidate(mid, t, body, profile)
                    expected_q, _ = source.reference(mid, t, body)
                    actual_q = [bernstein_at(c, u) for c in q] + [
                        bernstein_at(c, u) for c in w
                    ]
                    actual_e = [bernstein_at(c, u) for c in e] + [
                        bernstein_at(c, u) for c in f
                    ]
                    if (
                        actual_q != expected_q
                        or [x + y for x, y in zip(actual_q, actual_e)] != expected_p
                    ):
                        raise ValueError(
                            "Exact full-polynomial identity with original source failed"
                        )
                    root_identities += 6
                fields = {"q": q, "w": w, "e": e, "f": f}
                depth = plan["bernstein_bisection_depth"]
                if [x["leaf_index"] for x in data["leaves"]] != list(range(2**depth)):
                    raise ValueError("Complete fixed leaf population changed")
                hulls = {
                    k: [leaf_hulls(tuple(c), depth) for c in axes]
                    for k, axes in fields.items()
                }
                for j, leaf in enumerate(data["leaves"]):
                    box = {
                        k: [B(axis[j]) for axis in axes] for k, axes in hulls.items()
                    }
                    cover(
                        vector_metrics(
                            **box, scales=leaf["enclosure_normalization_scales"]
                        ),
                        leaf["enclosure"],
                    )
                    leaf_proofs += 1
                    u = Q(2 * j + 1, 2 ** (depth + 1))
                    point = {
                        k: [B(bernstein_at(c, u)) for c in axes]
                        for k, axes in fields.items()
                    }
                    cover(
                        vector_metrics(
                            **point, scales=leaf["midpoint_normalization_scales"]
                        ),
                        leaf["midpoint"],
                    )
                    point_proofs += 1
                expected_anchor = (Q(case["anchor_exact"]) - a) / width
                if len(data["anchors"]) != int(0 <= expected_anchor <= 1):
                    raise ValueError("Frozen anchor removed/added")
                for anchor in data["anchors"]:
                    if Q(anchor["u_exact"]) != expected_anchor:
                        raise ValueError("Frozen source anchor shifted")
                    point = {
                        k: [B(bernstein_at(c, expected_anchor)) for c in axes]
                        for k, axes in fields.items()
                    }
                    cover(
                        vector_metrics(**point, scales=anchor["normalization_scales"]),
                        anchor["metrics"],
                    )
                    point_proofs += 1
                for side, u in (("left", Q()), ("right", Q(1))):
                    expected_p, _, _ = source.candidate(
                        mid, a + width * u, body, profile
                    )
                    expected_q, _ = source.reference(mid, a + width * u, body)
                    if (
                        list(map(Q, data["candidate_endpoint_states"][side]))
                        != expected_p
                        or list(map(Q, data["reference_endpoint_states"][side]))
                        != expected_q
                    ):
                        raise ValueError("One-sided endpoint source state changed")
    for body in plan["bodies"]:
        for profile in plan["profiles"]:
            branches = [c["bodies"][body][profile] for c in report["cells"]]
            leaves = [x for d in branches for x in d["leaves"]]
            points = [x["midpoint"] for x in leaves] + [
                a["metrics"] for d in branches for a in d["anchors"]
            ]
            upper = [max(Q(x["enclosure"][i][1]) for x in leaves) for i in (0, 1)]
            lower = [max(Q(x[i][0]) for x in points) for i in (0, 1)]
            lines = list(
                map(
                    Q,
                    [
                        plan["position_chord_line_arcsec"],
                        plan["direction_rate_line_arcsec_per_source_day"],
                    ],
                )
            )
            status = (
                "guaranteed_under_lines"
                if all(x <= y for x, y in zip(upper, lines))
                else (
                    "definitely_over_line"
                    if any(x > y for x, y in zip(lower, lines))
                    else "unresolved"
                )
            )
            if report["summary"][body][profile] != {
                "status": status,
                "full_domain_upper_bounds": list(map(str, upper)),
                "largest_witness_lower_bounds": list(map(str, lower)),
                "leaf_count": len(leaves),
            }:
                raise ValueError("Full-curve fixed-line classification changed")
    expected_seams = []
    for left, right in zip(report["cells"], report["cells"][1:]):
        for body in plan["bodies"]:
            for profile in plan["profiles"]:
                for origin, field in (
                    ("SWE", "candidate_endpoint_states"),
                    ("DE441", "reference_endpoint_states"),
                ):
                    if origin == "DE441" and profile != plan["profiles"][0]:
                        continue
                    expected_seams.append((left, right, body, profile, origin, field))
    if len(report["seams"]) != len(expected_seams):
        raise ValueError("One-sided seam population changed")
    for row, (left, right, body, profile, origin, field) in zip(
        report["seams"], expected_seams
    ):
        if (row["epoch_exact"], row["body"], row["origin"], row["profile"]) != (
            left["end_exact"],
            body,
            origin,
            profile if origin == "SWE" else None,
        ):
            raise ValueError("One-sided seam rebound")
        a = list(map(Q, left["bodies"][body][profile][field]["right"]))
        b = list(map(Q, right["bodies"][body][profile][field]["left"]))
        if (row["position_equal_exact"], row["velocity_equal_exact"]) != (
            a[:3] == b[:3],
            a[3:] == b[3:],
        ):
            raise ValueError("One-sided state equality changed")
        d = [x - y for x, y in zip(a, b)]
        cover(
            vector_metrics(
                list(map(B, b[:3])),
                list(map(B, b[3:])),
                list(map(B, d[:3])),
                list(map(B, d[3:])),
                row["normalization_scales"],
            ),
            row["one_sided_direction_and_rate_jump"],
        )
    return {
        "protocol_sha256": PLAN_SHA,
        "report_sha256": sha(path),
        "split": split,
        "case_index": index,
        "exact_source_polynomial_identities": root_identities,
        "full_leaf_enclosures_checked": leaf_proofs,
        "point_enclosures_checked": point_proofs,
        "one_sided_seams_checked": len(expected_seams),
        "source_curve_only": True,
        "old_gates": {"production": 2, "overall": 1},
        "physical_accuracy_certified": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = verify(a.run, a.input)
    with a.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
