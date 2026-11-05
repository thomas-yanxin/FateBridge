"""Maintenance-only geometric clock diagnosis, never candidate acceptance.

Exact original DE441 source coefficients and outward intervals constrain an
effective numerical source argument. The numerical error tube is a hypothesis,
not an independently certified Horizons error bound or a TT conversion.
"""

import argparse
import csv
import hashlib
import json
import math
import re
import ssl
import struct
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction as Q
from pathlib import Path

import certifi

from scripts.astrodice.astrodice_clock_interval import A, I, Reader
from scripts.astrodice.astrodice_de441_records import clenshaw_with_derivative, header
from scripts.astrodice.astrodice_horizons_transport import open_horizons


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def check_inputs(run):
    plan_raw = (run / "plan-before-queries.json").read_bytes()
    plan = json.loads(plan_raw)
    for name, digest in plan["inputs_sha256"].items():
        if sha((run / name).read_bytes()) != digest:
            raise ValueError("Frozen input drift: " + name)
    return plan, sha(plan_raw)


def collect(run, cohort):
    plan, plan_hash = check_inputs(run)
    before = run / ("before-" + cohort + "-queries.json")
    if cohort == "B" and not (run / "A-first-analysis.json").is_file():
        raise ValueError("Analyze and freeze A before opening B")
    inputs = {
        "plan_sha256": plan_hash,
        "collector_sha256": sha(Path(__file__).read_bytes()),
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "cohort": cohort,
        "prior_A_analysis_sha256": (
            sha((run / "A-first-analysis.json").read_bytes()) if cohort == "B" else None
        ),
    }
    save(before, inputs)
    output = run / "responses"
    output.mkdir(exist_ok=True)
    context = ssl.create_default_context(cafile=certifi.where())
    receipts = []
    for query in plan["queries"]:
        if query["cohort"] != cohort:
            continue
        name = query["id"]
        url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(
            query["parameters"]
        )
        if len(url.encode()) > plan["maximum_url_bytes"]:
            raise ValueError("Frozen request exceeds URL budget")
        receipt = {"id": name, "url": url, "attempt": 1}
        try:
            request = urllib.request.Request(url)
            with open_horizons(
                request, context=context, timeout=40, receipt=receipt
            ) as response:
                raw = response.read()
                receipt.update(status=response.status, headers=dict(response.headers))
        except urllib.error.HTTPError as error:
            raw = error.read()
            receipt.update(
                status=error.code, headers=dict(error.headers), error=repr(error)
            )
        except (OSError, urllib.error.URLError) as error:
            raw = b""
            receipt.update(status=None, error=repr(error))
        with (output / (name + ".raw")).open("xb") as stream:
            stream.write(raw)
        receipt.update(raw_sha256=sha(raw), raw_bytes=len(raw))
        save(output / (name + ".receipt.json"), receipt)
        receipts.append(receipt)
        print(name, receipt["status"], len(raw), flush=True)
    save(run / (cohort + "-collection.json"), {**inputs, "receipts": receipts})


def parse(raw, query, cases, plan):
    data = json.loads(raw)
    if data.get("error"):
        raise ValueError("Horizons service error: " + str(data["error"]))
    result = data["result"]
    if result.count("$$SOE") != 1 or result.count("$$EOE") != 1:
        raise ValueError("Missing/duplicate ephemeris delimiters")
    prefix, rest = result.split("$$SOE")
    body, _ = rest.split("$$EOE")
    target = re.search(r"Target body name:.*?\((\d+)\).*?DE441", prefix)
    center = re.search(r"Center body name:.*?\((\d+)\)", prefix)
    expected = "JD" + query["time_type"]
    if (
        target is None
        or target.group(1) not in {"2", "299"}
        or center is None
        or center.group(1) != "0"
        or re.search(r"Output units\s*:\s*AU-D", prefix) is None
        or re.search(r"Reference frame\s*:\s*ICRF", prefix) is None
        or re.search(r"Output type\s*:\s*GEOMETRIC cartesian states", prefix) is None
        or expected not in prefix
    ):
        raise ValueError("Returned vector header differs from frozen contract")
    rows, assigned = [], set()
    for line in body.splitlines():
        if not line.strip():
            continue
        cells = [v.strip() for v in next(csv.reader([line]))]
        if len(cells) != 9 or cells[-1] != "":
            raise ValueError("Unplanned vector column set")
        epoch = Q(cells[0])
        near = [
            c
            for c in cases
            if abs(epoch - Q(c["nominal_JD"])) * 86400
            <= Q(plan["row_assignment_radius_seconds"])
        ]
        if len(near) != 1 or near[0]["id"] in assigned:
            raise ValueError("Row identity is missing, duplicate or ambiguous")
        case = near[0]
        assigned.add(case["id"])
        if not all(math.isfinite(float(v)) for v in cells[2:8]):
            raise ValueError("Nonfinite vector component")
        error = epoch - Q(case["nominal_JD"])
        rows.append(
            {
                "case_id": case["id"],
                "printed_JD": cells[0],
                "printed_calendar": cells[1],
                "printed_state": cells[2:8],
                "label_error_seconds": str(error * 86400),
                "original_label_budget_pass": abs(error)
                <= Q(plan["returned_label_match_budget_days"]),
            }
        )
    if assigned != {c["id"] for c in cases}:
        raise ValueError("Missing or unexpected requested population")
    return rows


def tube(printed, ulps):
    value = Decimal(printed)
    if not value.is_finite():
        raise ValueError("Nonfinite printed state")
    lsb = Q(10) ** value.as_tuple().exponent
    center = Q(printed)
    radius = lsb + ulps * Q(math.ulp(float(printed)))
    return center - radius, center + radius


def scalar_source(source, window, epoch, axis):
    meta = header((source / "header.bin").read_bytes())
    raw = (source / f"record-responses/case-{window:02}.bin").read_bytes()
    records = [raw[k : k + 8144] for k in range(0, len(raw), 8144)]
    record = next(
        v
        for v in records
        if Q(struct.unpack_from("<d", v)[0])
        <= epoch
        < Q(struct.unpack_from("<d", v, 8)[0])
    )
    values = struct.unpack("<1018d", record)
    offset, count, parts = meta["pointers"][1]
    width = (Q(values[1]) - Q(values[0])) / parts
    part = (epoch - Q(values[0])) // width
    begin = Q(values[0]) + part * width
    first = offset - 1 + (part * 3 + axis) * count
    coeff = list(map(Q, values[first : first + count]))
    au = Q(meta["au_km"])

    def evaluate(t):
        if not begin <= t < begin + width:
            raise ValueError("Inverse left the frozen polynomial cell")
        x = 2 * (t - begin) / width - 1
        return clenshaw_with_derivative(coeff, x)[0] / au

    return evaluate


def inverse(evaluate, nominal, bounds, increasing, radius, iterations):
    left, right = nominal - radius, nominal + radius
    sign = 1 if increasing else -1
    low, high = bounds if increasing else (-bounds[1], -bounds[0])
    if sign * evaluate(left) > low or sign * evaluate(right) < high:
        return {"status": "unbracketed"}
    witnesses = []
    for value in (low, high):
        a, b = left, right
        for _ in range(iterations):
            m = (a + b) / 2
            if sign * evaluate(m) < value:
                a = m
            else:
                b = m
        witnesses.append([str(a), str(b)])
    return {
        "status": "bracketed",
        "boundary_brackets_JD": witnesses,
        "effective_JD": [witnesses[0][0], witnesses[1][1]],
    }


def clock_hypotheses(epoch):
    return {
        "exact_nominal_TDB": epoch,
        "binary64_absolute_JD": Q(float(epoch)),
        "binary64_seconds_from_J2000": Q(2451545)
        + Q(float((epoch - 2451545) * 86400)) / 86400,
    }


def diagnose(source, case, row, plan):
    epoch = Q(case["nominal_JD"])
    radius = Q(plan["source_inverse_search_radius_seconds"]) / 86400
    reader = Reader(source, case["window_index"])
    broad = reader.state(A(I(epoch - radius, epoch + radius), 1), "Venus")
    derivatives = [v.d.bounds() for v in broad[:3]]
    conditioning = [min(abs(a), abs(b)) if a * b > 0 else Q(0) for a, b in derivatives]
    axis = max(range(3), key=lambda i: conditioning[i])
    if conditioning[axis] < Q(plan["minimum_monotone_position_derivative_AU_per_day"]):
        raise ValueError("No planned well-conditioned monotone position axis")
    evaluate = scalar_source(source, case["window_index"], epoch, axis)
    result = {
        **row,
        "role": case["role"],
        "nominal_JD": case["nominal_JD"],
        "axis": axis,
        "derivative_bounds": [[str(v) for v in pair] for pair in derivatives],
        "profiles": {},
    }
    for name, profile in plan["numerical_tube_profiles"].items():
        bounds = [tube(v, profile["extra_binary64_ULPs"]) for v in row["printed_state"]]
        item = inverse(
            evaluate,
            epoch,
            bounds[axis],
            derivatives[axis][0] > 0,
            radius,
            plan["source_inverse_bisection_iterations"],
        )
        if item["status"] == "bracketed":
            low, high = map(Q, item["effective_JD"])
            states = reader.state(A(I(low, high), 1), "Venus")
            source_bounds = [v.v.bounds() for v in states]
            compatible = [
                a <= d and c <= b for (a, b), (c, d) in zip(source_bounds, bounds)
            ]
            item.update(
                effective_offset_seconds=[
                    str((v - epoch) * 86400) for v in (low, high)
                ],
                source_state_bounds=[[str(v) for v in pair] for pair in source_bounds],
                component_compatible=compatible,
                position_compatible=all(compatible[:3]),
                velocity_compatible=all(compatible[3:]),
                all_six_compatible=all(compatible),
                hypothesis_in_inverse_interval={
                    k: low <= v <= high for k, v in clock_hypotheses(epoch).items()
                },
            )
        result["profiles"][name] = item
    return result


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    output = {
        "plan_sha256": digest,
        "cohort": cohort,
        "queries": [],
        "candidate_calls": 0,
        "TT_observer_clock_equivalence_certified": False,
        "numerical_tube_certified": False,
        "physical_time_model_certified": False,
        "production_acceptance_exit_code": 2,
        "full_goal_complete": False,
        "state_overlap_semantics": "Necessary component interval overlaps, not proof of a common exact epoch or certified numerical tube.",
    }
    cases = plan["cohorts"][cohort]
    lookup = {c["id"]: c for c in cases}
    for query in plan["queries"]:
        if query["cohort"] != cohort:
            continue
        raw = (run / "responses" / (query["id"] + ".raw")).read_bytes()
        receipt = json.loads(
            (run / "responses" / (query["id"] + ".receipt.json")).read_text()
        )
        result = {"id": query["id"], "raw_sha256": sha(raw), "rows": []}
        if sha(raw) != receipt["raw_sha256"]:
            raise ValueError("Raw network response drift")
        try:
            if receipt["status"] != 200:
                raise ValueError("Unavailable HTTP result: " + str(receipt["status"]))
            rows = parse(raw, query, cases, plan)
            for row in rows:
                result["rows"].append(
                    diagnose(run / "source-records", lookup[row["case_id"]], row, plan)
                )
            result["status"] = "diagnosed"
        except (ValueError, KeyError, StopIteration) as error:
            result.update(status="unavailable_or_invalid", error=repr(error))
        output["queries"].append(result)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["collect", "analyze"])
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--cohort", choices=["A", "B"], required=True)
    args = parser.parse_args()
    if args.action == "collect":
        collect(args.run, args.cohort)
    else:
        save(
            args.run / (args.cohort + "-first-analysis.json"),
            analyze(args.run, args.cohort),
        )
