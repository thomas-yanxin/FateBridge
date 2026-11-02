"""Independently check interval evidence with frozen 100-digit point references.

Uses the previously scalar-replayed Decimal/Clenshaw source implementation,
never the interval producer or its direct-basis reader. Interior checks are
checks of the enclosure implementation, not the proof for unsampled times.
"""

import argparse
import hashlib
import json
import math
import runpy
from decimal import Decimal as N
from decimal import localcontext
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_de441_records import calendar_jd_tdb


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounds(record):
    if record["denominator_power_two"] != 256:
        raise ValueError("Interval rounding grid changed")
    lo, hi = (
        Q(int(record[k]), 1 << 256) for k in ["lower_numerator", "upper_numerator"]
    )
    if lo > hi:
        raise ValueError("Reversed evidence interval")
    return lo, hi


def contains(record, number):
    lo, hi = bounds(record)
    if not lo <= Q(number) <= hi:
        raise ValueError("Independent source point outside claimed interval")


def number(value):
    q = Q(value)
    return N(q.numerator) / N(q.denominator)


def rate(center, matrix, derivative, factor):
    p = [
        sum(
            (
                N.from_float(float(c)) * N(v)
                for c, v in zip(row, center["direction_icrf"])
            ),
            N(0),
        )
        for row in matrix
    ]
    v = [
        sum(
            (
                N.from_float(float(c)) * N(d) * factor + N.from_float(float(cc)) * N(u)
                for c, cc, d, u in zip(
                    row, drow, center["derivative_per_day"], center["direction_icrf"]
                )
            ),
            N(0),
        )
        for row, drow in zip(matrix, derivative)
    ]
    # A high-precision mathematical pi, independent of producer's Machin bound.
    # Gauss-Legendre AGM has quadratic convergence; 10 iterations suffice here.
    a, b, t, power = N(1), N(1) / N(2).sqrt(), N(1) / 4, N(1)
    for _ in range(10):
        next_a = (a + b) / 2
        b = (a * b).sqrt()
        t -= power * (a - next_a) ** 2
        a = next_a
        power *= 2
    pi = (a + b) ** 2 / (4 * t)
    return (p[0] * v[1] - p[1] * v[0]) / (p[0] ** 2 + p[1] ** 2) * 648000 / pi


def author_clock_envelope(source, epoch):
    """A second term enumeration, using exact rational author binary64 words."""
    import re

    text = source.split("static const double fairhd[787][3] = {", 1)[1].split("};", 1)[
        0
    ]
    rows = re.findall(r"\{([^{}]+)\}", text)
    if len(rows) != 787:
        raise ValueError("Author clock population changed")
    millennia = abs((Q(epoch) - 2451545) / 365250)
    maximum = (
        millennia.numerator + millennia.denominator - 1
    ) // millennia.denominator + 1
    amplitude = derivative = Q(0)
    for j, row in enumerate(rows):
        a, frequency, _ = (Q(float(v.strip())) for v in row.split(","))
        power = sum(j >= threshold for threshold in [474, 679, 764, 784])
        polynomial = maximum**power
        polynomial_derivative = power * maximum ** (power - 1) if power else 0
        amplitude += abs(a) * polynomial
        derivative += abs(a) * (abs(frequency) * polynomial + polynomial_derivative)
    for a, frequency in [
        (0.00065e-6, 6069.776754),
        (0.00033e-6, 213.299095),
        (-0.00196e-6, 6208.294251),
        (-0.00173e-6, 74.781599),
    ]:
        amplitude += abs(Q(a))
        derivative += abs(Q(a) * Q(frequency))
    amplitude += Q(0.03638e-6) * maximum**2
    derivative += 2 * Q(0.03638e-6) * maximum
    return amplitude, derivative / Q(365250 * 86400)


def position_change(point, center):
    u, v = ([N(x) for x in value["direction_icrf"]] for value in [point, center])
    cross = [
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    ]
    dot = sum((a * b for a, b in zip(u, v)), N(0))
    tangent = sum((a * a for a in cross), N(0)).sqrt() / dot
    if not 0 <= tangent < N("0.001"):
        raise ValueError("Independent angular check outside small branch")
    # atan(t), with a negligible alternating remainder for the planned domain.
    angle = sum(
        ((-1) ** k * tangent ** (2 * k + 1) / (2 * k + 1) for k in range(8)), N(0)
    )
    pi = N(
        "3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986280348253421170679"
    )
    return angle * 648000 / pi


def audit(run, fixture, result_path, frames, output):
    protocol_path = run / "protocol-before-development.json"
    protocol = json.loads(protocol_path.read_text())
    if (
        protocol["position_line_arcsec"] != 0.02
        or protocol["rate_line_arcsec_per_day"] != 0.002
        or protocol["interval_binary_fraction_bits"] != 256
        or protocol["independent_point_validation_precision"] != 100
        or protocol["independent_point_offsets_as_fractions_of_radius"]
        != ["-1", "-1/2", "0", "1/2", "1"]
    ):
        raise ValueError("Independent check policy changed")
    root = Path(__file__).resolve().parents[1]
    if (
        digest(run / "dtdb.c")
        != "228bd7c7c1c88dda44c29a076f289c968f64d77a2dc389138b03ab5d1d442105"
    ):
        raise ValueError("Named author clock source changed")
    reference_path = root / (
        "tests/fixtures/astrodice-venus-source-shape-v1/frozen-source/scripts/"
        "astrodice_apparent_source_reference.py"
    )
    if digest(reference_path) != protocol["reference_source_sha256"]:
        raise ValueError("Independent point-reference source changed")
    reference = runpy.run_path(str(reference_path))
    Reader, sample = reference["Reader"], reference["sample"]
    manifest = fixture / "manifest.json"
    if (
        digest(manifest)
        != "96f8c9b6a8b2fde8f5f11b43316928fc2694fb90ab89c7d438bc7d4ef5aa9d30"
    ):
        raise ValueError("Original coefficient source changed")
    for name, h in json.loads(manifest.read_text())["files"].items():
        if digest(fixture / name) != h:
            raise ValueError("Original raw source changed")
    data = json.loads(result_path.read_text())
    cases = protocol[data["group"]]
    if (
        data["protocol_sha256"] != digest(protocol_path)
        or [r["id"] for r in data["rows"]] != [c["id"] for c in cases]
        or data["candidate_imported"]
        or data["candidate_accuracy_acceptances"] != 0
    ):
        raise ValueError("Frozen population or claim boundary changed")
    profile = json.loads(
        (
            root
            / "tests/fixtures/astrodice-apparent-source-v1/source-solar-profile.json"
        ).read_text()
    )["radius_mass_pairs"]
    points = []
    unknown = []
    with localcontext() as context:
        context.prec = 100
        for row, case in zip(data["rows"], cases):
            if any(
                row[k] != case[k]
                for k in ["body", "date_nominal_tt", "window_index", "role"]
            ):
                raise ValueError("Declared condition identity changed")
            if row.get("status"):
                unknown.append(row["id"])
                continue
            exact = calendar_jd_tdb(row["date_nominal_tt"])
            amplitude, rho = author_clock_envelope((run / "dtdb.c").read_text(), exact)
            if (
                Q(row["clock_model_envelope"]["maximum_offset_seconds"]) != amplitude
                or Q(row["clock_model_envelope"]["delta_derivative_per_second"]) != rho
            ):
                raise ValueError("Clock envelope does not match all author terms")
            native = Q(float(exact))
            reader = Reader(fixture, row["window_index"])
            center = sample(reader, row["body"], number(native), profile, precision=100)
            for kind, source_key, interval_key in [
                ("position", "direction_icrf", "center_direction_icrf_intervals"),
                (
                    "derivative",
                    "derivative_per_day",
                    "center_derivative_intervals_per_TDB_day",
                ),
            ]:
                for interval, value in zip(row[interval_key], center[source_key]):
                    contains(interval, N(value))
            frame = json.loads((frames / (row["id"] + ".json")).read_text())
            for hypothesis, item in row["hypotheses"].items():
                if (
                    item["status"]
                    != "source_interval_enclosed_under_declared_clock_hypothesis"
                ):
                    unknown.append(row["id"] + ":" + hypothesis)
                    continue
                if item["physical_clock_hypothesis_certified"]:
                    raise ValueError(
                        "Conditional clock promoted to physical certification"
                    )
                if (
                    hypothesis == "source_documented_offset_no_rate_bound"
                    and item["display_rate_change_upper_arcsec_per_TT_day"] is not None
                ):
                    raise ValueError("Offset magnitude invented a rate constraint")
                radius = Q(item["maximum_offset_seconds"]) / 86400
                required = (
                    Q(1, 500)
                    if hypothesis == "source_documented_offset_no_rate_bound"
                    else amplitude
                )
                if radius * 86400 != required:
                    raise ValueError("Clock radius differs from fixed hypothesis")
                if item.get("clock_rate_factor"):
                    contains(item["clock_rate_factor"], 1 / (1 - rho))
                    contains(item["clock_rate_factor"], 1 / (1 + rho))
                for fraction in map(
                    Q, protocol["independent_point_offsets_as_fractions_of_radius"]
                ):
                    epoch = exact + radius * fraction
                    point = sample(
                        reader, row["body"], number(epoch), profile, precision=100
                    )
                    if position_change(point, center) > N.from_float(
                        item["direction_position_change_upper_arcsec"]
                    ):
                        raise ValueError(
                            "Independent direction change exceeds interval bound"
                        )
                    contains(item["source_epoch_interval"], epoch)
                    for k in range(3):
                        contains(
                            item["direction_icrf_intervals"][k],
                            N(point["direction_icrf"][k]),
                        )
                        contains(
                            item["direction_derivative_intervals_per_TDB_day"][k],
                            N(point["derivative_per_day"][k]),
                        )
                    if item["display_rate_change_upper_arcsec_per_TT_day"] is not None:
                        for fname, f in frame["frames"].items():
                            for j, d in enumerate(f["derivatives"]):
                                for factor in bounds(item["clock_rate_factor"]):
                                    actual = rate(point, f["matrix"], d, number(factor))
                                    base = rate(center, f["matrix"], d, N(1))
                                    saved = item[
                                        "display_rate_change_upper_arcsec_per_TT_day"
                                    ][fname]
                                    contains(
                                        saved["rate_intervals_arcsec_per_TT_day"][j],
                                        actual,
                                    )
                                    if abs(actual - base) > N.from_float(
                                        saved["clock_change_upper_arcsec_per_day"]
                                    ):
                                        raise ValueError(
                                            "Independent display change exceeds interval bound"
                                        )
                    points.append(
                        {
                            "id": row["id"],
                            "hypothesis": hypothesis,
                            "offset_fraction": str(fraction),
                            "epoch": str(epoch),
                            "reference": point,
                        }
                    )
    result = {
        "method_id": "independent_100_digit_source_points_against_dyadic_clock_enclosures_v1",
        "group": data["group"],
        "rows": len(cases),
        "point_evaluations": len(points),
        "unqualified_ids": unknown,
        "exit_code": 2 if unknown else 0,
        "candidate_accuracy_acceptances": 0,
        "full_goal_complete": False,
        "original_Horizons_results_regraded": False,
        "points": points,
        "scope": "Independent arithmetic and Clenshaw cross-check of reported intervals. Finite probes are not the enclosure proof or physical clock validation.",
    }
    with output.open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write("\n")
    return result["exit_code"]


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ["run", "fixture", "result", "frames", "output"]:
        p.add_argument("--" + n, type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(
        audit(args.run, args.fixture, args.result, args.frames, args.output)
    )
