"""Independent power/Bernstein and raw-derivative replay of lunar references.

Imports no lunar producer, its algebra or source evaluator. Shared DE441
coefficients are not independent observations, and source time is not TT.
"""

import argparse
import hashlib
import json
from datetime import datetime
from fractions import Fraction as Q
from pathlib import Path

from scripts.verify_astrodice_observer_clock import (
    add,
    cover,
    independent_pi,
    mul,
    root,
    rounded,
    square,
    sub,
)
from scripts.verify_astrodice_taylor_remainder import (
    DerivativeSource,
    R,
    dot,
    length,
    normalize,
    plus,
    subtract,
    times,
)

PLAN_SHA = "a1864830d09ef8dcfdec0d592ed9fad61aad29c1b506ea6d7b96902f6139505f"
SOURCE_INPUTS_SHA = "fe93fb3dbcbca81c544a3fe3bfe281fa339597df3de74c6026236ac123329222"
K = Q(149597870700, 299792458 * 86400)


def tdb_label(label):
    v = datetime.fromisoformat(label)
    if v.tzinfo is not None:
        raise ValueError("Source coordinates cannot carry civil zones")
    return (
        Q(v.toordinal())
        + Q(3442849, 2)
        + Q(v.hour * 3600 + v.minute * 60 + v.second, 86400)
        + Q(v.microsecond, 86400000000)
    )


class LunarSource(DerivativeSource):
    def state_derivatives(self, t, body):
        if body not in {"Moon", "Earth"}:
            raise ValueError("Independent unsupported lunar body")
        emb, geo = self.group_derivatives(t, 2), self.group_derivatives(t, 9)
        if body == "Earth":
            return [e - m / (1 + self.emrat) for e, m in zip(emb, geo)]
        return [e + m * (self.emrat / (1 + self.emrat)) for e, m in zip(emb, geo)]


def binary64_nearest(q):
    """Rational ties-to-even on the normal positive JD grid, without float()."""
    q = Q(q)
    if not 100000 < q < 100000000:
        raise ValueError("Unplanned normal Julian epoch range")
    e = q.numerator.bit_length() - q.denominator.bit_length()
    while Q(2) ** e > q:
        e -= 1
    while Q(2) ** (e + 1) <= q:
        e += 1
    ulp = Q(2) ** (e - 52)
    x = q / ulp
    k, r = divmod(x.numerator, x.denominator)
    k += int(2 * r > x.denominator or (2 * r == x.denominator and k % 2 == 1))
    return k * ulp


def model(source, epoch, profile, derivative=False):
    if derivative and profile != "continuous_split":
        raise ValueError("No smooth derivative of rounded clock")
    if profile not in {
        "continuous_split",
        "rounded_emitter_only",
        "rounded_reception_and_emitter",
    }:
        raise ValueError("Unplanned independent profile")
    value = (
        binary64_nearest(epoch) if profile == "rounded_reception_and_emitter" else epoch
    )
    t = R([rounded(value), rounded(1)] if derivative else [rounded(value)])
    observer = source.state_derivatives(t, "Earth")
    tau = length(source.group_derivatives(t, 9)[:3]) * K
    te = t - tau
    if profile != "continuous_split":
        a, b = map(binary64_nearest, te.v[0])
        if a != b:
            raise ValueError("Independent rounded epoch is ambiguous")
        te = R([rounded(a)])
    ray = subtract(source.state_derivatives(te, "Moon")[:3], observer[:3])
    velocity = times(observer[3:], K)
    mag = length(ray)
    gamma = (1 - dot(velocity, velocity)).sqrt()
    uv = dot(ray, velocity) / mag
    apparent = times(
        plus(times(ray, gamma), times(velocity, mag * (1 + uv / (1 + gamma)))),
        1 / (1 + uv),
    )
    unit = normalize(apparent)
    result = {
        "direction": [x.v[0] for x in unit],
        "reception_epoch": t.v[0],
        "emission_epoch": te.v[0],
        "geometric_delay_days": tau.v[0],
        "direction_derivative_per_source_day": (
            [x.v[1] for x in unit] if derivative else None
        ),
    }
    if derivative:
        result["emission_clock_derivative"] = te.v[1]
    return result


def check_model(computed, saved):
    if set(computed) != set(saved):
        raise ValueError("Lunar source field omitted or added")
    for key in computed:
        if computed[key] is None:
            if saved[key] is not None:
                raise ValueError("Rounded clock assigned an instantaneous derivative")
        elif key in {"direction", "direction_derivative_per_source_day"}:
            if len(saved[key]) != 3:
                raise ValueError("A direction component was omitted")
            for a, b in zip(computed[key], saved[key]):
                cover(a, b)
        else:
            cover(computed[key], saved[key])


def distance(a, b):
    total = rounded(0)
    for x, y in zip(a, b):
        total = add(total, square(sub(x, y)))
    pi = independent_pi()
    return mul(root(total), rounded(Q(648000) / pi[1], Q(648000) / pi[0]))


def verify(run, candidate):
    raw = (run / "plan-before-analysis.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != PLAN_SHA:
        raise ValueError("Independent lunar plan binding failed")
    if (
        hashlib.sha256(
            (run / "source-inputs-before-evaluation.json").read_bytes()
        ).hexdigest()
        != SOURCE_INPUTS_SHA
    ):
        raise ValueError("Independent source input manifest changed")
    plan = json.loads(raw)
    for name, digest in json.loads(
        (run / "source-inputs-before-evaluation.json").read_text()
    ).items():
        if hashlib.sha256((run / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Independent raw source input changed")
    data = json.loads(candidate.read_text())
    if data["plan_sha256"] != PLAN_SHA or data["source_model"] != plan["source_model"]:
        raise ValueError("Model or plan substitution")
    for k in [
        "original_references_replaced",
        "original_failure_records_regraded",
        "physical_TT_TDB_model_certified",
        "Horizons_model_equivalence_certified",
        "production_accuracy_certified",
        "full_goal_complete",
    ]:
        if data[k] is not False:
            raise ValueError("Conditional lunar model promoted to a global certificate")
    if (
        data["old_gate_codes"] != [2, 1]
        or data["new_external_observations"] != 0
        or data["new_production_accuracy_holdouts"] != 0
    ):
        raise ValueError("Old gate or evidence population changed")
    split = data["split"]
    if split not in {"development", "heldout"}:
        raise ValueError("Unknown lunar split")
    sources = [LunarSource(run, k) for k in range(3)]
    expected = []
    for filename in plan["old_studies"]:
        p = json.loads((run / "before-change/tests/fixtures" / filename).read_text())
        labels = (
            p["development_dates_tt"] + p["holdout_dates_tt"]
            if split == "development"
            else plan["heldout_source_coordinates"]
        )
        for label in labels:
            expected.append((filename, label, p))
    if [(x["protocol"], x["date_label"]) for x in data["rows"]] != [
        (a, b) for a, b, _ in expected
    ]:
        raise ValueError("Original lunar centres removed or substituted")
    wanted = set()
    cached = {}
    summary = []
    for row, (filename, label, p) in zip(data["rows"], expected):
        epoch = tdb_label(label)
        index = 0 if label.startswith("0001-") else 1
        direction = (
            p["directions"][label]
            if split == "development"
            else (1 if index == 0 else -1)
        )
        if (
            Q(row["epoch_source_jd"]) != epoch
            or row["window"] != index
            or row["direction"] != direction
            or row["steps"] != p["steps_seconds"]
        ):
            raise ValueError("Original epoch, steps or orientation changed")
        center = model(sources[index], epoch, "continuous_split", True)
        check_model(center, row["center"])
        if set(row["profiles"]) != set(plan["profiles"]):
            raise ValueError("A lunar profile was dropped")
        result = {"protocol": filename, "date_label": label, "profiles": {}}
        for profile in plan["profiles"]:
            saved = row["profiles"][profile]
            rates = []
            errs = []
            if set(saved["templates"]) != {str(s) for s in p["steps_seconds"]}:
                raise ValueError("A lunar template step was dropped")
            for step in p["steps_seconds"]:
                keys = []
                values = []
                for i in range(p["node_count"]):
                    at = epoch + Q(direction * i * step, 86400)
                    key = f"{index}/{at}/{profile}"
                    keys.append(key)
                    wanted.add(key)
                    if key not in cached:
                        cached[key] = model(sources[index], at, profile)
                        check_model(cached[key], data["points"][key])
                    values.append(cached[key]["direction"])
                template = saved["templates"][str(step)]
                if template["point_keys"] != keys:
                    raise ValueError("Template nodes reordered or omitted")
                weights = [Q(a, b) for a, b in p["rational_weights"]]
                rate = []
                for axis in range(3):
                    total = rounded(0)
                    for w, v in zip(weights, values):
                        total = add(
                            total, mul(rounded(w), sub(v[axis], values[0][axis]))
                        )
                    rate.append(mul(total, rounded(Q(86400, direction * step))))
                if len(template["derivative_per_source_day"]) != 3:
                    raise ValueError("Template derivative component missing")
                for a, b in zip(rate, template["derivative_per_source_day"]):
                    cover(a, b)
                error = distance(rate, center["direction_derivative_per_source_day"])
                cover(
                    error,
                    template[
                        "joint_error_from_continuous_source_derivative_arcsec_per_source_day"
                    ],
                )
                errs.append(float(error[1]))
                rates.append(rate)
            diff = distance(*rates)
            cover(diff, saved["step_difference_arcsec_per_source_day"])
            if (
                saved["named_model_step_check_passed"]
                != (diff[1] <= Q(plan["fixed_rate_arcsec_per_day"]))
                or saved["rounded_clock_instantaneous_derivative_certified"]
                is not False
            ):
                raise ValueError("Template grade or clock meaning changed")
            result["profiles"][profile] = {
                "step_difference_upper_arcsec_per_source_day": float(diff[1]),
                "maximum_template_bias_upper_arcsec_per_source_day": max(errs),
                "named_model_step_check_passed": saved["named_model_step_check_passed"],
            }
        summary.append(result)
    if set(data["points"]) != wanted:
        raise ValueError("A point was added, omitted or orphaned")
    if split == "development":
        check_model(
            model(
                sources[2],
                tdb_label(plan["record_window_labels"][2]),
                "continuous_split",
                True,
            ),
            data["lunar_3000_source_control"],
        )
    elif data["lunar_3000_source_control"] is not None:
        raise ValueError("Control added to the holdout population")
    return {
        "plan_sha256": PLAN_SHA,
        "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
        "split": split,
        "rows": len(summary),
        "points": len(wanted),
        "strict_independent_containment": True,
        "summary": summary,
        "new_external_observations": 0,
        "new_production_accuracy_holdouts": 0,
        "old_gate_codes": [2, 1],
        "whole_production_accuracy_certified": False,
        "full_goal_complete": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("candidate", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    result = verify(a.run, a.candidate)
    with a.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "summary"}))


if __name__ == "__main__":
    main()
