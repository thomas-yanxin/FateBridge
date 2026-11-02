"""Infer effective emission epochs from range, then test complete float lattices.

Maintenance-only conditional source diagnosis, not physical clock certification.
Observed range, receiver-state uncertainty and both numerical tubes remain fixed.
"""

import argparse
import json
import math
import struct
import sys
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import A, I, Reader
from scripts.astrodice_de441_records import group_state, header
from scripts.astrodice_observer_clock import LIGHT_DAYS_PER_AU as K
from scripts.astrodice_observer_clock import (
    box,
    norm,
    observed_direction,
    parse_observer,
    state,
)
from scripts.astrodice_vector_clock import (
    check_inputs,
    inverse,
    save,
    scalar_source,
    sha,
    tube,
)


def earth_center(source, window, epoch):
    metadata = header((source / "header.bin").read_bytes())
    raw = (source / f"record-responses/case-{window:02}.bin").read_bytes()
    records = [raw[k : k + 8144] for k in range(0, len(raw), 8144)]
    record = next(
        v
        for v in records
        if Q(struct.unpack_from("<d", v)[0])
        <= epoch
        < Q(struct.unpack_from("<d", v, 8)[0])
    )
    emb, moon = [group_state(metadata, record, epoch, g) for g in (2, 9)]
    return [
        (e - m / (1 + Q(metadata["earth_moon_mass_ratio"]))) / Q(metadata["au_km"])
        for e, m in zip(emb[:3], moon[:3])
    ]


def lattice_points(low, high, maximum):
    if (
        low > high
        or sys.float_info.radix != 2
        or sys.float_info.mant_dig != 53
        or struct.calcsize("d") != 8
    ):
        raise ValueError("Unplanned binary64 lattice or support")
    value = float(low)
    if not math.isfinite(value):
        raise ValueError("Nonfinite lattice support")
    if Q(value) < low:
        value = math.nextafter(value, math.inf)
    points = []
    while Q(value) <= high:
        if len(points) == maximum:
            return {"status": "enumeration_limit", "points": points}
        points.append(value)
        value = math.nextafter(value, math.inf)
        if not math.isfinite(value):
            break
    return {"status": "complete", "points": points}


def rounding_cell(value):
    previous, following = (
        math.nextafter(value, -math.inf),
        math.nextafter(value, math.inf),
    )
    if not all(math.isfinite(v) for v in (previous, value, following)):
        raise ValueError("Unbounded rounding cell")
    even = struct.unpack(">Q", struct.pack(">d", value))[0] % 2 == 0
    return {
        "bounds": [
            str((Q(previous) + Q(value)) / 2),
            str((Q(value) + Q(following)) / 2),
        ],
        "lower_included": even,
        "upper_included": even,
    }


def cell_relations(image, cell):
    low, high = image
    a, b = map(Q, cell["bounds"])
    intersects = (high > a or high == a and cell["lower_included"]) and (
        low < b or low == b and cell["upper_included"]
    )
    contained = (low > a or low == a and cell["lower_included"]) and (
        high < b or high == b and cell["upper_included"]
    )
    return intersects, contained


def coordinate(epoch, model):
    if model == "absolute_JD_binary64":
        return epoch
    if model == "seconds_from_J2000_binary64":
        return (epoch - 2451545) * 86400
    raise ValueError("Unplanned time coordinate")


def epoch_from_coordinate(value, model):
    if model == "absolute_JD_binary64":
        return Q(value)
    if model == "seconds_from_J2000_binary64":
        return Q(2451545) + Q(value) / 86400
    raise ValueError("Unplanned time coordinate")


def candidate(reader, reception, earth, printed_range, direction, model, value):
    epoch = epoch_from_coordinate(value, model)
    venus = state(reader, I(epoch), "Venus")[:3]
    ray = [v - e for v, e in zip(venus, earth)]
    distance = norm(ray)
    unit = [v / distance for v in ray]
    next_epoch = reception - distance * K
    image = (
        next_epoch
        if model == "absolute_JD_binary64"
        else (next_epoch - 2451545) * 86400
    )
    cell = rounding_cell(value)
    cell_intersects, cell_contains = cell_relations(image.bounds(), cell)

    def overlap(x, y):
        a, b = x.bounds()
        c, d = y.bounds()
        return a <= d and c <= b

    checks = {
        "range_overlap": overlap(distance, printed_range),
        "astrometric_components_overlap": [
            overlap(v, d) for v, d in zip(unit, direction)
        ],
        "nearest_cell_intersects": cell_intersects,
        "entire_next_image_inside_cell": cell_contains,
    }
    return {
        "raw_hex": value.hex(),
        "raw_exact": str(Q(value)),
        "epoch_JD": str(epoch),
        "rounding_cell": cell,
        "range_AU": box(distance),
        "direction_ICRF": [box(v) for v in unit],
        "next_image_raw": box(image),
        "checks": checks,
        "hypothesis_not_refuted": checks["range_overlap"]
        and all(checks["astrometric_components_overlap"])
        and cell_intersects,
        "physical_or_internal_algorithm_certified": False,
    }


def infer(source, case, row, calibration, profile, plan):
    settings = plan["numerical_tube_profiles"][profile]
    result = {
        "calibration_all_six_not_refuted": calibration.get("all_six_compatible", False)
    }
    if calibration["status"] != "bracketed":
        return {**result, "status": "calibration_unknown"}
    low, high = map(Q, calibration["effective_JD"])
    reception = I(low, high)
    midpoint = (low + high) / 2
    center = earth_center(source, case["window_index"], midpoint)
    reader = Reader(source, case["window_index"])
    earth = state(reader, reception, "Earth")[:3]
    displacement = [
        max(abs(a - c), abs(b - c))
        for (a, b), c in zip([v.bounds() for v in earth], center)
    ]
    radius = norm([I(d) for d in displacement]).absolute_upper()
    observed = I(*tube(row["range_AU"], settings["extra_binary64_ULPs"]))
    raw_range_low, raw_range_high = observed.bounds()
    range_low, range_high = raw_range_low - radius, raw_range_high + radius
    if range_low <= 0:
        raise ValueError("Expanded range is nonpositive")
    nominal = midpoint - Q(row["range_AU"]) * K
    search = Q(plan["emission_search_radius_seconds"]) / 86400
    broad = reader.state(A(I(nominal - search, nominal + search), 1), "Venus")
    ray = [v.v - c for v, c in zip(broad[:3], center)]
    derivative = 2 * sum((v * w.v for v, w in zip(ray, broad[3:])), I())
    radial = derivative / (2 * norm(ray))
    dl, dh = radial.bounds()
    minimum = min(abs(dl), abs(dh)) if dl * dh > 0 else Q(0)
    result.update(
        reception_JD=calibration["effective_JD"],
        Earth_center_JD=str(midpoint),
        Earth_center_AU=list(map(str, center)),
        Earth_box_AU=[box(v) for v in earth],
        Earth_radius_AU=str(radius),
        observed_range_AU=box(observed),
        expanded_range_AU=[str(range_low), str(range_high)],
        search_center_JD=str(nominal),
        squared_distance_derivative=box(derivative),
        radial_derivative_AU_per_day=box(radial),
    )
    if minimum < Q(plan["minimum_absolute_emission_radial_derivative_AU_per_day"]):
        return {**result, "status": "conditioning_unknown"}
    axes = [scalar_source(source, case["window_index"], nominal, a) for a in range(3)]

    def evaluate(epoch):
        return sum(((f(epoch) - c) ** 2 for f, c in zip(axes, center)), Q(0))

    inv = inverse(
        evaluate,
        nominal,
        (range_low**2, range_high**2),
        dl > 0,
        search,
        plan["emission_inverse_bisection_iterations"],
    )
    result["inverse"] = inv
    if inv["status"] != "bracketed":
        return {**result, "status": "source_range_unbracketed"}
    a, b = map(Q, inv["effective_JD"])
    continuous = (low - raw_range_high * K, high - raw_range_low * K)
    result.update(
        status="inferred",
        effective_emission_JD=inv["effective_JD"],
        continuous_emission_JD=list(map(str, continuous)),
        continuous_necessary_overlap=a <= continuous[1] and continuous[0] <= b,
        effective_minus_continuous_seconds=[
            str((a - continuous[1]) * 86400),
            str((b - continuous[0]) * 86400),
        ],
        lattices={},
    )
    direction = observed_direction(
        row["astrometric_angles"],
        settings["extra_binary64_ULPs"],
        plan["interval_trig_terms"],
    )
    result["observed_direction_ICRF"] = [box(v) for v in direction]
    for model in plan["lattice_coordinate_models"]:
        found = lattice_points(
            coordinate(a, model),
            coordinate(b, model),
            plan["maximum_lattice_points_per_model"],
        )
        rows = [
            candidate(reader, reception, earth, observed, direction, model, v)
            for v in found["points"]
        ]
        admissible = sum(v["hypothesis_not_refuted"] for v in rows)
        result["lattices"][model] = {
            "enumeration_status": found["status"],
            "points_in_effective_interval": len(rows),
            "candidates": rows,
            "hypotheses_not_refuted": admissible,
            "unique_not_refuted": found["status"] == "complete" and admissible == 1,
            "conditional_refuted": found["status"] == "complete" and admissible == 0,
        }
    return result


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    if cohort == "A":
        specs = plan["development_groups"]
    else:
        specs = [
            {
                "cohort": "B",
                "observation_root": ".",
                "calibration_root": "B-vector-calibration",
            }
        ]
    output = {
        "plan_sha256": digest,
        "cohort": cohort,
        "groups": [],
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "TT_observer_clock_equivalence_certified": False,
        "physical_time_model_certified": False,
        "numerical_tubes_certified": False,
        "internal_emission_algorithm_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    for spec in specs:
        observation_root = run / spec["observation_root"]
        cal_root = run / spec["calibration_root"]
        source_plan = json.loads(
            (observation_root / "plan-before-queries.json").read_text()
        )
        cases = source_plan["cohorts"][spec["cohort"]]
        calibration_path = cal_root / (spec["cohort"] + "-first-analysis.json")
        cal = {q["id"]: q for q in json.loads(calibration_path.read_text())["queries"]}
        for query in source_plan["queries"]:
            if query["cohort"] != spec["cohort"]:
                continue
            raw_path = observation_root / "responses" / (query["id"] + ".raw")
            raw = raw_path.read_bytes()
            receipt = json.loads(raw_path.with_suffix(".receipt.json").read_text())
            group = {
                "observation_root": spec["observation_root"],
                "calibration_root": spec["calibration_root"],
                "source_cohort": spec["cohort"],
                "query_id": query["id"],
                "raw_sha256": sha(raw),
                "calibration_sha256": sha(calibration_path.read_bytes()),
                "rows": [],
            }
            if sha(raw) != receipt["raw_sha256"]:
                raise ValueError("Raw OBSERVER identity changed")
            try:
                if receipt["status"] != 200:
                    raise ValueError("Unavailable OBSERVER response")
                rows = parse_observer(raw, query, cases, source_plan)
                lookup = {v["case_id"]: v for v in cal[query["id"]]["rows"]}
                if cal[query["id"]]["status"] != "diagnosed":
                    raise ValueError("Geometric calibration unavailable")
                for row in rows:
                    case = next(c for c in cases if c["id"] == row["case_id"])
                    c = lookup[row["case_id"]]
                    row.update(
                        nominal_JD=case["nominal_JD"],
                        window_index=case["window_index"],
                        calibration_original_label_pass=c["original_label_budget_pass"],
                        profiles={},
                    )
                    for profile in plan["numerical_tube_profiles"]:
                        try:
                            row["profiles"][profile] = infer(
                                run / "source-records",
                                case,
                                row,
                                c["profiles"][profile],
                                profile,
                                plan,
                            )
                        except (ValueError, StopIteration) as error:
                            row["profiles"][profile] = {
                                "status": "source_model_unknown",
                                "error": repr(error),
                                "calibration_all_six_not_refuted": c["profiles"][
                                    profile
                                ].get("all_six_compatible", False),
                            }
                    group["rows"].append(row)
                group["status"] = "diagnosed"
            except (KeyError, ValueError) as error:
                group.update(status="unavailable_or_invalid", error=repr(error))
            output["groups"].append(group)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cohort", choices=["A", "B"], required=True)
    args = parser.parse_args()
    save(
        args.run / (args.cohort + "-first-analysis.json"),
        analyze(args.run, args.cohort),
    )
