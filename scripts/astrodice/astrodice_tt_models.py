"""Maintenance clock-model comparison; no fitted clock or production correction.

The analytic model is enclosed mathematically. Its error relative to a physical
time ephemeris is not enclosed, especially outside its documented accuracy era.
"""

import argparse
import json
import math
import re
from fractions import Fraction as Q
from functools import lru_cache
from pathlib import Path

from scripts.astrodice.astrodice_clock_interval import FB_SHA256, I, clock_envelope
from scripts.astrodice.astrodice_earth_clock import diagnose, parse
from scripts.astrodice.astrodice_vector_clock import check_inputs, save, sha

MODELS = ("ERFA_Fairhead_geocentric", "NAIF_LSK_periodic")
SLICES = ((0, 474), (474, 679), (679, 764), (764, 784), (784, 787))
ADJUSTMENTS = (
    ("0.00065e-6", "6069.776754", "4.021194"),
    ("0.00033e-6", "213.299095", "5.543132"),
    ("-0.00196e-6", "6208.294251", "5.696701"),
    ("-0.00173e-6", "74.781599", "2.435900"),
)


@lru_cache(maxsize=1)
def pi_interval():
    def atan(n, count):
        a = sum(
            (Q((-1) ** k, (2 * k + 1) * n ** (2 * k + 1)) for k in range(count)), Q()
        )
        b = a + Q((-1) ** count, (2 * count + 1) * n ** (2 * count + 1))
        return I(min(a, b), max(a, b))

    return 16 * atan(5, 80) - 4 * atan(239, 32)


def sine(x):
    """Outward Taylor enclosure after rigorous Machin-pi reduction."""
    lo, hi = x.bounds()
    pl, ph = pi_interval().bounds()
    turns = round((lo + hi) / (2 * (pl + ph)))
    x = x - 2 * turns * pi_interval()
    if x.absolute_upper() > 4:
        raise ValueError("Sine enclosure support too wide")
    term, total = x, x
    minus_square = -x.square()
    for k in range(1, 96):
        term = term * minus_square / ((2 * k) * (2 * k + 1))
        total = total + term
    tail = Q(4) ** 193 / math.factorial(193)
    return total + I(-tail, tail)


@lru_cache(maxsize=1)
def coefficients(raw):
    if sha(raw) != FB_SHA256:
        raise ValueError("Pinned ERFA author source changed")
    table = re.search(rb"fairhd\[787\]\[3\] = \{(.*?)\n\s*\};", raw, re.S)
    rows = re.findall(rb"\{\s*([\d.e+-]+),\s*([\d.e+-]+),\s*([\d.e+-]+)\s*\}", table[1])
    if len(rows) != 787:
        raise ValueError("Incomplete Fairhead series")
    return [tuple(Q(float(x)) for x in row) for row in rows]


def delta(tdb, model, rows):
    """TDB minus TT seconds; geocenter (u=v=0)."""
    if model == MODELS[1]:
        m = Q(float("6.239996")) + Q(float("1.99096871e-7")) * (tdb - 2451545) * 86400
        return Q(float("1.657e-3")) * sine(m + Q(float("1.671e-2")) * sine(m))
    if model != MODELS[0]:
        raise ValueError("Unknown analytic clock model")
    t = (tdb - 2451545) / 365250
    groups = [
        sum((a * sine(b * t + c) for a, b, c in rows[lo:hi]), I()) for lo, hi in SLICES
    ]
    value = groups[-1]
    for g in reversed(groups[:-1]):
        value = value * t + g
    for a, b, c in ADJUSTMENTS:
        value = value + Q(float(a)) * sine(Q(float(b)) * t + Q(float(c)))
    return value + Q(float("0.03638e-6")) * t.square()


def prediction(tt, model, raw):
    rows = coefficients(raw)
    if not Q("1721425.5") <= tt < Q("5373484.5"):
        raise ValueError("Clock study outside AD1..9999")
    if clock_envelope(raw.decode(), tt)["maximum_offset_seconds"] >= 1:
        raise ValueError("Initial implicit support not qualified")
    if (
        model == MODELS[1]
        and not Q(float("1.657e-3"))
        * (1 + Q(float("1.671e-2")))
        * Q(float("1.99096871e-7"))
        < 1
    ):
        raise ValueError("NAIF fixed point not contractive")
    interval = I(tt - Q(1, 86400), tt + Q(1, 86400))
    for _ in range(6):
        updated = tt + delta(interval, model, rows) / 86400
        a, b = interval.bounds()
        c, d = updated.bounds()
        if not a <= c <= d <= b:
            raise ValueError("Implicit clock enclosure not nested")
        interval = updated
    documented = Q("2433282.5") <= tt <= Q("2469807.5")
    return {
        "predicted_JD_TDB": list(map(str, interval.bounds())),
        "predicted_TDB_minus_TT_seconds": list(
            map(str, ((interval - tt) * 86400).bounds())
        ),
        "model_accuracy_scope": (
            (
                "documented_1950_2050_DE405_comparison"
                if documented
                else "outside_documented_accuracy_era"
            )
            if model == MODELS[0]
            else "approximate_30_microsecond_description_no_uniform_era_bound"
        ),
        "physical_model_error_certified": False,
    }


def comparison(pred, inverse, label_pass):
    if inverse["status"] != "bracketed":
        return {"status": "source_clock_unknown", "qualified_not_refuted": False}
    a, b = map(Q, pred["predicted_JD_TDB"])
    c, d = map(Q, inverse["effective_JD"])
    overlap = a <= d and c <= b
    return {
        "status": "overlap" if overlap else "disjoint",
        "prediction_minus_source_seconds": [str((a - d) * 86400), str((b - c) * 86400)],
        "source_all_six_compatible": inverse["all_six_compatible"],
        "label_budget_pass": label_pass,
        "qualified_not_refuted": overlap
        and inverse["all_six_compatible"]
        and label_pass,
    }


def analyze(run, cohort):
    plan, digest = check_inputs(run)
    predictions = json.loads((run / "predictions-before-queries.json").read_text())
    output = {
        "plan_sha256": digest,
        "cohort": cohort,
        "queries": [],
        "pairs": [],
        "new_TT_source_conditions": 5 if cohort == "B" else 0,
        "new_candidate_holdouts": 0,
        "physical_time_model_certified": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    for query in plan["queries"]:
        if query["cohort"] != cohort:
            continue
        receipt = json.loads(
            (run / "responses" / (query["id"] + ".receipt.json")).read_text()
        )
        raw = (run / "responses" / (query["id"] + ".raw")).read_bytes()
        if receipt["status"] != 200 or sha(raw) != receipt["raw_sha256"]:
            raise ValueError("Unavailable or changed TT model response")
        cases = query["cases"]
        rows = parse(raw, query, cases, plan)
        checked = []
        for row in rows:
            if row["role"] == "auxiliary_not_primary":
                continue
            case = next(c for c in cases if c["id"] == row["case_id"])
            record = diagnose(run / "source-records", case, row, query["body"], plan)
            record["models"] = {
                model: {
                    name: comparison(
                        predictions[case["id"]][model],
                        inv,
                        row["original_label_budget_pass"],
                    )
                    for name, inv in record["profiles"].items()
                }
                for model in MODELS
            }
            checked.append(record)
        output["queries"].append(
            {
                "id": query["id"],
                "body": query["body"],
                "encoding": query["encoding"],
                "rows": checked,
            }
        )
    return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--cohort", choices=("A", "B"), required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    save(args.output, analyze(args.run, args.cohort))


if __name__ == "__main__":
    main()
