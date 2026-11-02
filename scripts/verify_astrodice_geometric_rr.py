"""Independent source-grid endpoint proofs and radial interval transfers.

No geometric producer, its parser, axis evaluator or binary search imports.
Source clocks remain conditional on the frozen DE441/grid/numerical models.
"""

import argparse
import csv
import hashlib
import json
import re
from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_discrete_lt import (
    measured,
    radial_membership,
    verify_profile,
)
from scripts.verify_astrodice_earth_clock import wire
from scripts.verify_astrodice_emission_epoch import enumerate_bits, from_raw
from scripts.verify_astrodice_joint_epoch import exact_state, predicate_layers
from scripts.verify_astrodice_observer_clock import (
    Source,
    add,
    cover,
    divide,
    length,
    mul,
    parse,
    rounded,
    sub,
)
from scripts.verify_astrodice_observer_timescale import inspect
from scripts.verify_astrodice_retarded_table import parse_vectors


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def label(epoch, encoding):
    if encoding != "CAL":
        q = epoch - (Q("2400000.5") if encoding == "MJD" else 0)
        with localcontext() as c:
            c.prec = 70
            return format(Decimal(q.numerator) / Decimal(q.denominator), "f")
    q = (epoch - Q("1721424.5")) * 86400000000
    integer, remainder = divmod(q.numerator, q.denominator)
    integer += (
        remainder * 2 > q.denominator
        or remainder * 2 == q.denominator
        and integer % 2 == 1
    )
    ordinal, micro = divmod(integer, 86400000000)
    day = date.fromordinal(ordinal)
    sec, us = divmod(micro, 1000000)
    hour, sec = divmod(sec, 3600)
    minute, second = divmod(sec, 60)
    month = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()[day.month - 1]
    return (
        f"{day.year}ad-{month}-{day.day:02} {hour:02}:{minute:02}:{second:02}.{us:06}"
    )


def contexts(run, cohort, plan):
    for spec in plan["groups"][cohort]:
        sp = json.loads((run / spec["root"] / "plan-before-queries.json").read_text())
        joint = json.loads((run / spec["joint_analysis"]).read_text())
        discrete = json.loads((run / spec["discrete_analysis"]).read_text())
        for query in sp["queries"]:
            if query["cohort"] != spec["source_cohort"] or query["kind"] != "LT_vector":
                continue
            j = next(
                g
                for g in joint["groups"]
                if g["id"] == spec["joint_group"] and g["query"] == query["id"]
            )
            d = next(
                g
                for g in discrete["groups"]
                if g["id"] == spec["discrete_group"] and g["query"] == query["id"]
            )
            yield spec, sp, query, j, d


def expected_geometry_plan(run, cohort, plan, rawplan):
    out = {
        "parent_plan_sha256": digest(rawplan),
        "parent_cohort": cohort,
        "inputs_sha256": {"../plan-before-queries.json": digest(rawplan)},
        "maximum_url_bytes": plan["maximum_url_bytes"],
        "queries": [],
        "skipped_source_pairs": [],
    }
    for spec, sp, query, joint, discrete in contexts(run, cohort, plan):
        for n in (spec["joint_analysis"], spec["discrete_analysis"]):
            out["inputs_sha256"]["../" + n] = digest((run / n).read_bytes())
        selected = []
        for row in discrete["rows"]:
            if row["role"] == "auxiliary_not_primary":
                continue
            s = row["profiles"][plan["geometry_probe_pair_profile"]]
            c = s["models"].get("seconds_from_J2000_binary64", {}).get("candidates", [])
            if len(c) != 1:
                out["skipped_source_pairs"].append(
                    {
                        "LT_query": query["id"],
                        "case_id": row["case_id"],
                        "reason": "nonunique_frozen_source_pair",
                    }
                )
                continue
            case = next(
                k
                for k in sp["cohorts"][spec["source_cohort"]]
                if k["id"] == row["case_id"]
            )
            selected.append((case, c[0]))
        for body, key, identifier in (
            ("Earth", "reception_hex", "399"),
            ("Venus", "emission_hex", "299"),
        ):
            cases = [
                {
                    "id": "geometry-auxiliary",
                    "nominal_JD": "2243796",
                    "window_index": 3,
                    "role": "auxiliary_not_primary",
                    "intended_ET_hex": float((Q(2243796) - 2451545) * 86400).hex(),
                }
            ]
            for case, point in selected:
                raw = float.fromhex(point[key])
                epoch = from_raw(raw, "seconds_from_J2000_binary64")
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
            p = {
                "format": "json",
                "COMMAND": "'" + identifier + "'",
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
                    "'" + label(Q(c["nominal_JD"]), enc) + "'" for c in cases
                ),
            }
            out["queries"].append(
                {
                    "id": cohort + "-GEOMETRY-" + body + "-" + enc,
                    "cohort": cohort,
                    "body": body,
                    "encoding": enc,
                    "time_type": "TDB",
                    "parameters": p,
                    "cases": cases,
                    "LT_query": query["id"],
                    "source_group": spec["id"],
                }
            )
    return out


def raw_rows(raw, query, plan):
    payload = json.loads(raw)
    if payload.get("error"):
        raise ValueError("Service error is not a geometric state")
    prefix, text = payload["result"].split("$$SOE")
    text, _ = text.split("$$EOE")
    body = query["body"]
    identifier = {"Earth": "399", "Venus": "299"}[body]
    expressions = [
        rf"Target body name: {body}.*?\({identifier}\).*?DE441",
        r"Center body name: Solar System Barycenter \(0\).*?DE441",
        r"Output units\s*:\s*AU-D",
        r"Reference frame\s*:\s*ICRF",
        r"Output type\s*:\s*GEOMETRIC cartesian states",
        r"Calendar mode\s*:\s*Gregorian",
        r"JDTDB",
    ]
    if any(not re.search(expr, prefix) for expr in expressions):
        raise ValueError("Geometric source header differs")
    rows = []
    seen = set()
    for cells in csv.reader(text.strip().splitlines()):
        c = [s.strip() for s in cells]
        if (
            len(c) != 9
            or c[-1]
            or any(not Decimal(s).is_finite() for s in c[:1] + c[2:8])
        ):
            raise ValueError("Geometric numeric columns differ")
        near = [
            k
            for k in query["cases"]
            if abs(Q(c[0]) - Q(k["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(near) != 1 or near[0]["id"] in seen:
            raise ValueError("Geometric row population differs")
        case = near[0]
        seen.add(case["id"])
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
        raise ValueError("Geometric row missing")
    return rows


def clock_proof(source, case, row, body, profile, saved, plan):
    epoch = Q(case["nominal_JD"])
    radius = Q(plan["geometry_clock_search_radius_seconds"]) / 86400
    support = parse(saved["support_JD"])
    if not (
        support[0] <= epoch - radius <= epoch + radius <= support[1]
        and epoch - radius - support[0] <= Q(1, 1 << 256)
        and support[1] - epoch - radius <= Q(1, 1 << 256)
    ):
        raise ValueError("Frozen geometric clock search changed")
    broad = Source(source, case["window_index"]).state(support, body)
    if len(saved["derivative_bounds"]) != 3:
        raise ValueError("Monotonicity dimension changed")
    for actual, declared in zip(broad[3:], saved["derivative_bounds"]):
        cover(actual, declared)
    derivatives = list(map(parse, saved["derivative_bounds"]))
    conditions = [min(abs(a), abs(b)) if a * b > 0 else Q(0) for a, b in derivatives]
    axis = max(range(3), key=conditions.__getitem__)
    base = {
        "support_JD": saved["support_JD"],
        "derivative_bounds": saved["derivative_bounds"],
        "axis": axis,
        "physical_time_model_certified": False,
    }
    if saved["axis"] != axis:
        raise ValueError("Source-only monotone axis changed")
    if conditions[axis] <= 0:
        if saved != {**base, "status": "conditioning_unknown"}:
            raise ValueError("Unconditioned clock promoted")
        return 0
    status, points = enumerate_bits(
        (support[0] - 2451545) * 86400,
        (support[1] - 2451545) * 86400,
        plan["maximum_lattice_points_per_model"],
    )
    base["grid_hex"] = [v.hex() for v in points]
    if status != "complete":
        if saved != {**base, "status": "enumeration_limit"}:
            raise ValueError("Incomplete clock grid promoted")
        return 0
    if saved["grid_hex"] != base["grid_hex"]:
        raise ValueError("Geometric clock grid changed")
    ulps = plan["numerical_tube_profiles"][profile]["extra_binary64_ULPs"]
    bounds = [measured(v, ulps) for v in row["printed_state"]]
    sign = 1 if derivatives[axis][0] > 0 else -1
    targets = bounds[axis] if sign == 1 else (-bounds[axis][1], -bounds[axis][0])
    first, last = saved["axis_indices"]
    if not (0 <= first <= last <= len(points)):
        raise ValueError("Geometric inverse index bounds differ")

    def evaluate(index):
        return (
            sign
            * exact_state(
                source,
                case["window_index"],
                from_raw(points[index], "seconds_from_J2000_binary64"),
                body,
            )[axis]
        )

    if (
        first > 0
        and evaluate(first - 1) >= targets[0]
        or first < len(points)
        and evaluate(first) < targets[0]
        or last > 0
        and evaluate(last - 1) > targets[1]
        or last < len(points)
        and evaluate(last) <= targets[1]
    ):
        raise ValueError("Discrete monotone inverse endpoint proof failed")
    candidates = []
    for point in points[first:last]:
        values = exact_state(
            source,
            case["window_index"],
            from_raw(point, "seconds_from_J2000_binary64"),
            body,
        )
        flags = [a <= v <= b for v, (a, b) in zip(values, bounds)]
        candidates.append(
            {
                "raw_hex": point.hex(),
                "source_state": list(map(str, values)),
                "components_compatible": flags,
                "all_six_compatible": all(flags),
            }
        )
    matches = [c["raw_hex"] for c in candidates if c["all_six_compatible"]]
    if saved != {
        **base,
        "status": "complete",
        "axis_indices": [first, last],
        "candidates": candidates,
        "all_six_grid_matches": matches,
        "unique_at_intended_epoch": matches == [case["intended_ET_hex"]],
    }:
        raise ValueError("Geometric source components or clock qualification changed")
    return len(candidates)


def projection(state):
    total = rounded(0)
    for p, v in zip(state[:3], state[3:]):
        total = add(total, mul(p, v))
    return divide(total, length(state[:3]))


def verify(run, cohort):
    rawplan = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(rawplan)
    for n, h in {
        **plan["inputs_sha256"],
        **json.loads((run / "implementation-before-queries.json").read_text()),
    }.items():
        if digest((run / n).read_bytes()) != h:
            raise ValueError("Frozen geometric source input drift: " + n)
    child = run / ("geometry-" + cohort)
    rawgp = (child / "plan-before-queries.json").read_bytes()
    gp = json.loads(rawgp)
    if gp != expected_geometry_plan(run, cohort, plan, rawplan):
        raise ValueError("Adaptive geometric query rule or intended epoch changed")
    before = json.loads((child / ("before-" + cohort + "-queries.json")).read_text())
    if before["plan_sha256"] != digest(rawgp) or before["collector_sha256"] != digest(
        (run / "frozen-source/scripts/astrodice_vector_clock.py").read_bytes()
    ):
        raise ValueError("Actual geometric collection binding changed")
    if cohort == "B":
        binding = json.loads((run / "before-B-open-binding.json").read_text())
        bfirst = json.loads((run / "before-B-queries.json").read_text())
        if (
            binding["plan_sha256"] != digest(rawplan)
            or binding["A_analysis_sha256"]
            != digest((run / "A-first-analysis.json").read_bytes())
            or binding["A_proof_sha256"]
            != digest((run / "A-independent-replay-first.json").read_bytes())
            or bfirst["prior_A_analysis_sha256"] != binding["A_analysis_sha256"]
            or bfirst["plan_sha256"] != digest(rawplan)
            or digest((child / "A-first-analysis.json").read_bytes())
            != binding["A_analysis_sha256"]
            or before["prior_A_analysis_sha256"] != binding["A_analysis_sha256"]
        ):
            raise ValueError("A-before-B geometric binding lost")
        for stage in ("joint", "discrete"):
            generated = json.loads(
                (run / ("B-" + stage + "-first-process.json")).read_text()
            )
            if generated["exit_code"] != 0 or generated["analysis_sha256"] != digest(
                (run / ("B-" + stage + "-first-analysis.json")).read_bytes()
            ):
                raise ValueError("Frozen B source stage changed")
    raw = (run / (cohort + "-first-analysis.json")).read_bytes()
    data = json.loads(raw)
    if (
        data["cohort"] != cohort
        or data["plan_sha256"] != digest(rawplan)
        or data["geometry_plan_sha256"] != digest(rawgp)
        or data["candidate_calls"]
        or data["new_candidate_holdouts"]
        or data["physical_time_model_certified"]
        or data["full_goal_complete"]
        or data["production_acceptance_exit_code"] != 2
        or data["retained_overall_numeric_gate_exit_code"] != 1
    ):
        raise ValueError("Geometric source evidence promoted")
    if len(data["geometry"]) != len(gp["queries"]):
        raise ValueError("Geometric query omitted")
    clock_points = 0
    for query, saved in zip(gp["queries"], data["geometry"]):
        rawv, receipt = wire(child, query)
        if receipt["status"] != 200:
            raise ValueError("Unavailable geometry")
        rows = raw_rows(rawv, query, plan)
        if {k: saved[k] for k in ("query", "body", "LT_query")} != {
            "query": query["id"],
            "body": query["body"],
            "LT_query": query["LT_query"],
        } or len(saved["rows"]) != len(rows):
            raise ValueError("Geometric group identity changed")
        for row, record in zip(rows, saved["rows"]):
            if {k: record[k] for k in row} != row or set(record["profiles"]) != set(
                plan["numerical_tube_profiles"]
            ):
                raise ValueError("Geometric raw row changed")
            case = next(c for c in query["cases"] if c["id"] == row["case_id"])
            for p, value in record["profiles"].items():
                clock_points += clock_proof(
                    run / "source-records", case, row, query["body"], p, value, plan
                )
    expected = []
    joint_steps = source_boxes = source_pairs = 0
    for spec, sp, query, joint, discrete in contexts(run, cohort, plan):
        rawv, receipt = wire(run / spec["root"], query)
        cases = sp["cohorts"][spec["source_cohort"]]
        vectors = parse_vectors(rawv, query, cases, sp)
        ob = sp["observer_bindings"][spec["source_cohort"]][query["encoding"]]
        oq = ob["query"]
        rawo, orr = wire(run / spec["root"] / ob["root"], oq)
        obs = inspect(rawo, orr["status"], oq, cases, sp)
        keys = (
            "TIME_TYPE",
            "CAL_TYPE",
            "TIME_DIGITS",
            "CAL_FORMAT",
            "TLIST_TYPE",
            "TLIST",
        )
        if (
            receipt["status"] != 200
            or obs["status"] != "supported"
            or any(query["parameters"][k] != oq["parameters"][k] for k in keys)
        ):
            raise ValueError("LT source batch invalid")
        lookup = {r["case_id"]: r for r in obs["rows"]}
        if len(vectors) != len(joint["rows"]) or len(vectors) != len(discrete["rows"]):
            raise ValueError("LT family omitted")
        for vector, j, d in zip(vectors, joint["rows"], discrete["rows"]):
            if (
                j["vector"] != vector
                or j["observer"] != lookup[vector["case_id"]]
                or d["case_id"] != vector["case_id"]
                or d["role"] != vector["role"]
            ):
                raise ValueError("LT source row identity changed")
            if set(j["profiles"]) != set(plan["numerical_tube_profiles"]) or set(
                d["profiles"]
            ) != set(plan["numerical_tube_profiles"]):
                raise ValueError("LT source profile omitted")
            case = next(c for c in cases if c["id"] == vector["case_id"])
            for p, family in j["profiles"].items():
                proof, pairs = verify_profile(
                    run, case, vector, j["observer"], p, family, d["profiles"][p], plan
                )
                joint_steps += proof["steps"]
                source_boxes += proof["source_boxes"]
                source_pairs += pairs
            if vector["role"] != "auxiliary_not_primary":
                expected.append((query, vector, d))
    if len(expected) != len(data["transfers"]):
        raise ValueError("Transfer population omitted")
    stats = {
        p: {
            k: 0
            for k in (
                "primary",
                "source_pair_unavailable",
                "both_geometry_clocks_unique_at_intended",
                "transfer_qualified",
                "geometric_state_and_RR_not_refuted",
                "LT_printed_projection_RR_overlap",
                "exact_source_RR_matches_LT",
            )
        }
        for p in plan["numerical_tube_profiles"]
    }
    refinements = []
    for (query, vector, drow), transfer in zip(expected, data["transfers"]):
        case_id = vector["case_id"]
        geos = {
            g["body"]: {r["case_id"]: r for r in g["rows"]}
            for g in data["geometry"]
            if g["LT_query"] == query["id"]
        }
        if any(case_id not in geos[body] for body in ("Earth", "Venus")):
            if transfer != {
                "case_id": case_id,
                "LT_query": query["id"],
                "status": "source_pair_unavailable",
            }:
                raise ValueError("Unavailable source pair promoted")
            for s in stats.values():
                s["primary"] += 1
                s["source_pair_unavailable"] += 1
            continue
        if (
            transfer["case_id"] != case_id
            or transfer["LT_query"] != query["id"]
            or transfer["status"] != "compared"
            or set(transfer["profiles"]) != set(plan["numerical_tube_profiles"])
        ):
            raise ValueError("Transfer binding changed")
        intended = drow["profiles"][plan["geometry_probe_pair_profile"]]["models"][
            "seconds_from_J2000_binary64"
        ]["candidates"][0]
        values = list(map(Q, intended["source_difference_AU_and_AU_per_day"]))
        square = sum(v * v for v in values[:3])
        numerator = sum(a * b for a, b in zip(values[:3], values[3:]))
        for p, saved in transfer["profiles"].items():
            ulps = plan["numerical_tube_profiles"][p]["extra_binary64_ULPs"]
            obs = [measured(v, ulps) for v in vector["printed_state"]]
            source_flags = [a <= v <= b for v, (a, b) in zip(values, obs)]
            clock = all(
                geos[b][case_id]["profiles"][p].get("unique_at_intended_epoch", False)
                for b in ("Earth", "Venus")
            )
            qualified = clock and all(source_flags)
            geo = [
                sub(rounded(*measured(v, ulps)), rounded(*measured(e, ulps)))
                for v, e in zip(
                    geos["Venus"][case_id]["printed_state"],
                    geos["Earth"][case_id]["printed_state"],
                )
            ]
            if (
                len(saved["geometric_difference_state_bounds"]) != 6
                or len(saved["geometric_difference_vs_LT_components"]) != 6
            ):
                raise ValueError("Transfer component omitted")
            refin = []
            flags = [
                predicate_layers(
                    "component." + str(i), flag, declared, actual, target, refin
                )
                for i, (flag, declared, actual, target) in enumerate(
                    zip(
                        saved["geometric_difference_vs_LT_components"],
                        saved["geometric_difference_state_bounds"],
                        geo,
                        obs,
                    )
                )
            ]
            rr = measured(vector["range_rate_AU_per_day"], ulps)
            radial = projection(geo)
            lt_radial = projection([rounded(*v) for v in obs])
            rg = predicate_layers(
                "geometric.RR",
                saved["geometric_projection_RR_overlap"],
                saved["geometric_projection_RR"],
                radial,
                rr,
                refin,
            )
            rl = predicate_layers(
                "LT_printed.RR",
                saved["LT_printed_projection_RR_overlap"],
                saved["LT_printed_projection_RR"],
                lt_radial,
                rr,
                refin,
            )
            exact = radial_membership(numerator, square, rr)
            if (
                saved["geometry_clocks_unique_at_intended_epochs"] != clock
                or saved["LT_exact_source_component_flags"] != source_flags
                or saved["conditional_transfer_qualified"] != qualified
                or saved["exact_source_RR_matches_LT"] != exact
                or saved["qualified_geometric_state_and_RR_not_refuted"]
                != (
                    qualified
                    and all(saved["geometric_difference_vs_LT_components"])
                    and saved["geometric_projection_RR_overlap"]
                )
                or saved["physical_or_internal_algorithm_certified"]
            ):
                raise ValueError(
                    "Clock, radial source or transfer qualification promoted"
                )
            s = stats[p]
            s["primary"] += 1
            s["both_geometry_clocks_unique_at_intended"] += clock
            s["transfer_qualified"] += qualified
            s["geometric_state_and_RR_not_refuted"] += qualified and all(flags) and rg
            s["LT_printed_projection_RR_overlap"] += rl
            s["exact_source_RR_matches_LT"] += exact
            if refin:
                refinements.append(
                    {
                        "LT_query": query["id"],
                        "case_id": case_id,
                        "profile": p,
                        "refinements": refin,
                    }
                )
    return {
        "method": "independent_direct_source_monotone_ET_grid_and_RR_transfer_v1",
        "cohort": cohort,
        "analysis_sha256": digest(raw),
        "profiles": stats,
        "clock_grid_candidates_checked": clock_points,
        "joint_steps_checked": joint_steps,
        "source_boxes_checked": source_boxes,
        "exact_parent_grid_pairs_checked": source_pairs,
        "refinement_rows": refinements,
        "exit_code": 0,
        "candidate_calls": 0,
        "new_candidate_holdouts": 0,
        "physical_time_model_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--cohort", choices=["A", "B"], required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    with a.output.open("x") as f:
        json.dump(verify(a.run, a.cohort), f, indent=2)
        f.write("\n")
