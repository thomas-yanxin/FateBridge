"""Explicit-epoch geometric probes of LT radial-rate arithmetic.

Independent source-grid clock qualification precedes every cross-table transfer.
These conditional source tests never certify TT conversion or angular rates.
"""

import argparse
import csv
import json
import re
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import A, I, Reader
from scripts.astrodice_discrete_lt import groups, ratio_in_interval
from scripts.astrodice_earth_clock import exact_axis
from scripts.astrodice_emission_epoch import epoch_from_coordinate, lattice_points
from scripts.astrodice_joint_epoch import exact_state
from scripts.astrodice_observer_clock import box, norm
from scripts.astrodice_vector_clock import check_inputs, save, sha, tube
from scripts.gen_astrodice_horizons_wide import calendar_label


def epoch_label(epoch, encoding):
    if encoding == "CAL":
        return calendar_label(round((epoch - Q("1721424.5")) * 86400 * 10**6))
    with localcontext() as context:
        context.prec = 70
        value = epoch - (Q("2400000.5") if encoding == "MJD" else 0)
        return format(Decimal(value.numerator) / Decimal(value.denominator), "f")


def contexts(run, cohort, plan):
    for spec, sp, query, joint in groups(run, cohort, plan):
        discrete = json.loads((run / spec["discrete_analysis"]).read_text())
        discrete = next(
            g
            for g in discrete["groups"]
            if g["id"] == spec["discrete_group"] and g["query"] == query["id"]
        )
        yield spec, sp, query, joint, discrete


def geometry_plan(run, cohort):
    plan, digest = check_inputs(run)
    out = {
        "parent_plan_sha256": digest,
        "parent_cohort": cohort,
        "inputs_sha256": {"../plan-before-queries.json": digest},
        "maximum_url_bytes": plan["maximum_url_bytes"],
        "queries": [],
        "skipped_source_pairs": [],
    }
    for spec, sp, query, joint, discrete in contexts(run, cohort, plan):
        for name in (spec["joint_analysis"], spec["discrete_analysis"]):
            out["inputs_sha256"]["../" + name] = sha((run / name).read_bytes())
        intended = []
        for row in discrete["rows"]:
            if row["role"] == "auxiliary_not_primary":
                continue
            saved = row["profiles"][plan["geometry_probe_pair_profile"]]
            candidates = (
                saved["models"]
                .get("seconds_from_J2000_binary64", {})
                .get("candidates", [])
            )
            if len(candidates) != 1:
                out["skipped_source_pairs"].append(
                    {
                        "LT_query": query["id"],
                        "case_id": row["case_id"],
                        "reason": "nonunique_frozen_source_pair",
                    }
                )
                continue
            case = next(
                c
                for c in sp["cohorts"][spec["source_cohort"]]
                if c["id"] == row["case_id"]
            )
            intended.append((case, candidates[0]))
        for body, key in (("Earth", "reception_hex"), ("Venus", "emission_hex")):
            cases = [
                {
                    "id": "geometry-auxiliary",
                    "nominal_JD": "2243796",
                    "window_index": 3,
                    "role": "auxiliary_not_primary",
                    "intended_ET_hex": float((Q(2243796) - 2451545) * 86400).hex(),
                }
            ]
            for case, c in intended:
                raw = float.fromhex(c[key])
                epoch = epoch_from_coordinate(raw, "seconds_from_J2000_binary64")
                cases.append(
                    {
                        "id": case["id"],
                        "nominal_JD": str(epoch),
                        "window_index": case["window_index"],
                        "role": "source_argument_probe",
                        "intended_ET_hex": raw.hex(),
                    }
                )
            enc = query["encoding"]
            params = {
                "format": "json",
                "COMMAND": "'399'" if body == "Earth" else "'299'",
                "OBJ_DATA": "'NO'",
                "MAKE_EPHEM": "'YES'",
                "EPHEM_TYPE": "'VECTORS'",
                "CENTER": "'500@0'",
                "REF_SYSTEM": "'ICRF'",
                "REF_PLANE": "'FRAME'",
                "VEC_CORR": "'NONE'",
                "VEC_TABLE": "'2'",
                "OUT_UNITS": "'AU-D'",
                "CSV_FORMAT": "'YES'",
                "CAL_TYPE": "'GREGORIAN'",
                "CAL_FORMAT": "'BOTH'",
                "TIME_DIGITS": "'FRACSEC'",
                "TIME_TYPE": "'TDB'",
                "TLIST_TYPE": "'" + enc + "'",
                "TLIST": "\n".join(
                    "'" + epoch_label(Q(c["nominal_JD"]), enc) + "'" for c in cases
                ),
            }
            out["queries"].append(
                {
                    "id": cohort + "-GEOMETRY-" + body + "-" + enc,
                    "cohort": cohort,
                    "body": body,
                    "encoding": enc,
                    "time_type": "TDB",
                    "parameters": params,
                    "cases": cases,
                    "LT_query": query["id"],
                    "source_group": spec["id"],
                }
            )
    return out


def parse_geometry(raw, query, plan):
    payload = json.loads(raw)
    if payload.get("error"):
        raise ValueError("Geometric service error: " + str(payload["error"]))
    prefix, text = payload["result"].split("$$SOE")
    text, _ = text.split("$$EOE")
    ident = {"Earth": "399", "Venus": "299"}[query["body"]]
    for pattern in [
        rf"Target body name: {query['body']}.*?\({ident}\).*?DE441",
        r"Center body name: Solar System Barycenter \(0\).*?DE441",
        r"Output units\s*:\s*AU-D",
        r"Reference frame\s*:\s*ICRF",
        r"Output type\s*:\s*GEOMETRIC cartesian states",
        r"Calendar mode\s*:\s*Gregorian",
        r"JDTDB",
    ]:
        if not re.search(pattern, prefix):
            raise ValueError("Geometric body/frame/time contract differs")
    rows = []
    seen = set()
    for cells in csv.reader(text.strip().splitlines()):
        c = [v.strip() for v in cells]
        if len(c) != 9 or c[-1]:
            raise ValueError("Geometric columns differ")
        near = [
            case
            for case in query["cases"]
            if abs(Q(c[0]) - Q(case["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(near) != 1 or near[0]["id"] in seen:
            raise ValueError("Geometric row identity ambiguous")
        case = near[0]
        seen.add(case["id"])
        for v in c[:1] + c[2:8]:
            if not Decimal(v).is_finite():
                raise ValueError("Nonfinite geometry")
        rows.append(
            {
                "case_id": case["id"],
                "printed_JD": c[0],
                "printed_calendar": c[1],
                "printed_state": c[2:8],
                "original_label_budget_pass": abs(Q(c[0]) - Q(case["nominal_JD"]))
                <= Q(plan["returned_label_match_budget_days"]),
            }
        )
    if seen != {c["id"] for c in query["cases"]}:
        raise ValueError("Geometric population changed")
    return rows


def lower_bound(points, evaluate, target, strict):
    lo, hi = 0, len(points)
    while lo < hi:
        mid = (lo + hi) // 2
        v = evaluate(points[mid])
        if v < target or strict and v == target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def diagnose(source, case, row, body, profile, plan):
    nominal = Q(case["nominal_JD"])
    radius = Q(plan["geometry_clock_search_radius_seconds"]) / 86400
    support = I(nominal - radius, nominal + radius)
    broad = Reader(source, case["window_index"]).state(A(support, 1), body)
    derivatives = [v.d.bounds() for v in broad[:3]]
    conditioning = [min(abs(a), abs(b)) if a * b > 0 else Q(0) for a, b in derivatives]
    axis = max(range(3), key=conditioning.__getitem__)
    result = {
        "support_JD": box(support),
        "derivative_bounds": [list(map(str, p)) for p in derivatives],
        "axis": axis,
        "physical_time_model_certified": False,
    }
    if conditioning[axis] <= 0:
        return {**result, "status": "conditioning_unknown"}
    low, high = support.bounds()
    found = lattice_points(
        (low - 2451545) * 86400,
        (high - 2451545) * 86400,
        plan["maximum_lattice_points_per_model"],
    )
    result["grid_hex"] = [v.hex() for v in found["points"]]
    if found["status"] != "complete":
        return {**result, "status": "enumeration_limit"}
    ulps = plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
    bounds = [tube(v, ulps) for v in row["printed_state"]]
    sign = 1 if derivatives[axis][0] > 0 else -1
    targets = bounds[axis] if sign == 1 else (-bounds[axis][1], -bounds[axis][0])
    function = exact_axis(source, case["window_index"], nominal, body, axis)

    def evaluate(x):
        return sign * function(epoch_from_coordinate(x, "seconds_from_J2000_binary64"))

    first = lower_bound(found["points"], evaluate, targets[0], False)
    last = lower_bound(found["points"], evaluate, targets[1], True)
    candidates = []
    for raw in found["points"][first:last]:
        state = exact_state(
            source,
            case["window_index"],
            epoch_from_coordinate(raw, "seconds_from_J2000_binary64"),
            body,
        )
        flags = [a <= v <= b for v, (a, b) in zip(state, bounds)]
        candidates.append(
            {
                "raw_hex": raw.hex(),
                "source_state": list(map(str, state)),
                "components_compatible": flags,
                "all_six_compatible": all(flags),
            }
        )
    matches = [v["raw_hex"] for v in candidates if v["all_six_compatible"]]
    return {
        **result,
        "status": "complete",
        "axis_indices": [first, last],
        "candidates": candidates,
        "all_six_grid_matches": matches,
        "unique_at_intended_epoch": matches == [case["intended_ET_hex"]],
    }


def projection(state):
    ray, velocity = state[:3], state[3:]
    return sum((p * v for p, v in zip(ray, velocity)), I()) / norm(ray)


def overlaps(a, b):
    low, high = a.bounds()
    return low <= b[1] and b[0] <= high


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    gp = json.loads(
        (run / ("geometry-" + cohort) / "plan-before-queries.json").read_text()
    )
    result = {
        "cohort": cohort,
        "plan_sha256": digest,
        "geometry_plan_sha256": sha(
            (run / ("geometry-" + cohort) / "plan-before-queries.json").read_bytes()
        ),
        "geometry": [],
        "transfers": [],
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "physical_time_model_certified": False,
        "full_goal_complete": False,
    }
    for query in gp["queries"]:
        base = run / ("geometry-" + cohort)
        raw = (base / "responses" / (query["id"] + ".raw")).read_bytes()
        receipt = json.loads(
            (base / "responses" / (query["id"] + ".receipt.json")).read_text()
        )
        if receipt["status"] != 200 or sha(raw) != receipt["raw_sha256"]:
            raise ValueError("Unavailable/changed geometric table")
        rows = []
        for row in parse_geometry(raw, query, plan):
            case = next(c for c in query["cases"] if c["id"] == row["case_id"])
            rows.append(
                {
                    **row,
                    "profiles": {
                        p: diagnose(
                            run / "source-records", case, row, query["body"], p, plan
                        )
                        for p in plan["numerical_tube_profiles"]
                    },
                }
            )
        result["geometry"].append(
            {
                "query": query["id"],
                "body": query["body"],
                "LT_query": query["LT_query"],
                "rows": rows,
            }
        )
    for spec, sp, query, joint, discrete in contexts(run, cohort, plan):
        geos = {
            g["body"]: {r["case_id"]: r for r in g["rows"]}
            for g in result["geometry"]
            if g["LT_query"] == query["id"]
        }
        for row in joint["rows"]:
            case_id = row["vector"]["case_id"]
            if row["vector"]["role"] == "auxiliary_not_primary":
                continue
            if any(case_id not in geos[body] for body in ("Earth", "Venus")):
                result["transfers"].append(
                    {
                        "case_id": case_id,
                        "LT_query": query["id"],
                        "status": "source_pair_unavailable",
                    }
                )
                continue
            drow = next(r for r in discrete["rows"] if r["case_id"] == case_id)
            intended = drow["profiles"][plan["geometry_probe_pair_profile"]]["models"][
                "seconds_from_J2000_binary64"
            ]["candidates"][0]
            values = list(map(Q, intended["source_difference_AU_and_AU_per_day"]))
            square = sum(v * v for v in values[:3])
            numerator = sum(a * b for a, b in zip(values[:3], values[3:]))
            profiles = {}
            for p, settings in plan["numerical_tube_profiles"].items():
                ulps = settings["extra_binary64_ULPs"]
                observed = [tube(v, ulps) for v in row["vector"]["printed_state"]]
                source_flags = [a <= v <= b for v, (a, b) in zip(values, observed)]
                clock = all(
                    geos[b][case_id]["profiles"][p].get(
                        "unique_at_intended_epoch", False
                    )
                    for b in ("Earth", "Venus")
                )
                qualified = clock and all(source_flags)
                geo = [
                    I(*tube(v, ulps)) - I(*tube(e, ulps))
                    for v, e in zip(
                        geos["Venus"][case_id]["printed_state"],
                        geos["Earth"][case_id]["printed_state"],
                    )
                ]
                radial = projection(geo)
                lt_radial = projection([I(*v) for v in observed])
                rr = tube(row["vector"]["range_rate_AU_per_day"], ulps)
                flags = [overlaps(x, y) for x, y in zip(geo, observed)]
                profiles[p] = {
                    "geometry_clocks_unique_at_intended_epochs": clock,
                    "LT_exact_source_component_flags": source_flags,
                    "conditional_transfer_qualified": qualified,
                    "geometric_difference_state_bounds": [box(v) for v in geo],
                    "geometric_difference_vs_LT_components": flags,
                    "geometric_projection_RR": box(radial),
                    "LT_printed_projection_RR": box(lt_radial),
                    "geometric_projection_RR_overlap": overlaps(radial, rr),
                    "LT_printed_projection_RR_overlap": overlaps(lt_radial, rr),
                    "exact_source_RR_matches_LT": ratio_in_interval(
                        numerator, square, rr
                    ),
                    "qualified_geometric_state_and_RR_not_refuted": qualified
                    and all(flags)
                    and overlaps(radial, rr),
                    "physical_or_internal_algorithm_certified": False,
                }
            result["transfers"].append(
                {
                    "case_id": case_id,
                    "LT_query": query["id"],
                    "status": "compared",
                    "profiles": profiles,
                }
            )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["build", "analyze"])
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--cohort", choices=["A", "B"], required=True)
    a = p.parse_args()
    if a.action == "build":
        child = a.run / ("geometry-" + a.cohort)
        child.mkdir()
        save(child / "plan-before-queries.json", geometry_plan(a.run, a.cohort))
        if a.cohort == "B":
            with (child / "A-first-analysis.json").open("xb") as f:
                f.write((a.run / "A-first-analysis.json").read_bytes())
    else:
        save(a.run / (a.cohort + "-first-analysis.json"), analyze(a.run, a.cohort))
