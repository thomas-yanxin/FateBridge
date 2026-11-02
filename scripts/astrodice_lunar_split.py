"""Complete geocentric lunar source model on exact split epochs.

Maintenance reference, not an observed TT/Horizons oracle. Original endpoint
protocols, weights, probes, printing errors and failed scores stay unchanged.
Rounded clock profiles are position-only diagnostics, never smooth derivatives.
"""

import argparse
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import (
    A,
    I,
    Reader,
    add,
    dot,
    norm,
    scale,
    sub,
    unit,
)
from scripts.astrodice_de441_records import calendar_jd_tdb
from scripts.astrodice_source_slope_bounds import pi_bounds

PLAN_SHA = "a1864830d09ef8dcfdec0d592ed9fad61aad29c1b506ea6d7b96902f6139505f"
SOURCE_INPUTS_SHA = "fe93fb3dbcbca81c544a3fe3bfe281fa339597df3de74c6026236ac123329222"
K = Q(149597870700, 299792458 * 86400)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_plan(run):
    if sha(run / "plan-before-analysis.json") != PLAN_SHA:
        raise ValueError("Lunar split-epoch frozen plan changed")
    if sha(run / "source-inputs-before-evaluation.json") != SOURCE_INPUTS_SHA:
        raise ValueError("Frozen lunar source input manifest changed")
    bindings = json.loads((run / "source-inputs-before-evaluation.json").read_text())
    for name, digest in bindings.items():
        if sha(run / name) != digest:
            raise ValueError("Frozen lunar source input changed: " + name)
    return json.loads((run / "plan-before-analysis.json").read_text())


def record(box):
    return list(map(str, box.bounds()))


class LunarSource(Reader):
    def state(self, epoch, body):
        if body not in {"Earth", "Moon"}:
            raise ValueError("Unplanned lunar source body")
        emb, geo = self.group(epoch, 2), self.group(epoch, 9)
        earth = sub(emb, scale(geo, 1 / (1 + self.emrat)))
        return earth if body == "Earth" else add(earth, geo)


def rounded_epoch(value):
    low, high = value.bounds()
    a, b = Q(float(low)), Q(float(high))
    if a != b:
        raise ValueError("Emission rounding cell is ambiguous; no node dropped")
    return I(a)


def apparent(source, epoch, profile="continuous_split", derivative=False):
    if derivative and profile != "continuous_split":
        raise ValueError("A rounded clock does not acquire a smooth derivative")
    if profile not in {
        "continuous_split",
        "rounded_emitter_only",
        "rounded_reception_and_emitter",
    }:
        raise ValueError("Unknown lunar split profile")
    t = A(
        Q(float(epoch)) if profile == "rounded_reception_and_emitter" else epoch,
        int(derivative),
    )
    earth = source.state(t, "Earth")
    delay = norm(source.group(t, 9)[:3]) * K
    emitted = t - delay
    if profile != "continuous_split":
        emitted = A(rounded_epoch(emitted.v))
    ray = sub(source.state(emitted, "Moon")[:3], earth[:3])
    radius = norm(ray)
    beta = scale(earth[3:], K)
    lorentz = (1 - dot(beta, beta)).sqrt()
    projection = dot(ray, beta) / radius
    f2 = 1 + projection / (1 + lorentz)
    bent = scale(
        add(scale(ray, lorentz), scale(beta, f2 * radius)), 1 / (1 + projection)
    )
    direction = unit(bent)
    result = {
        "direction": [record(v.v) for v in direction],
        "reception_epoch": record(t.v),
        "emission_epoch": record(emitted.v),
        "geometric_delay_days": record(delay.v),
        "direction_derivative_per_source_day": (
            [record(v.d) for v in direction] if derivative else None
        ),
    }
    if derivative:
        result["emission_clock_derivative"] = record(emitted.d)
    return result


def qbox(pair):
    return I(*map(Q, pair))


def vector_distance(a, b):
    return sum(((x - y).square() for x, y in zip(a, b)), I()).sqrt() * (
        648000 / I(*pi_bounds())
    )


def cases(run, plan, split):
    rows = []
    for filename in plan["old_studies"]:
        p = json.loads((run / "before-change/tests/fixtures" / filename).read_text())
        labels = (
            p["development_dates_tt"] + p["holdout_dates_tt"]
            if split == "development"
            else plan["heldout_source_coordinates"]
        )
        for label in labels:
            index = 0 if label.startswith("0001-") else 1
            rows.append(
                {
                    "protocol": filename,
                    "date_label": label,
                    "window": index,
                    "epoch": calendar_jd_tdb(label),
                    "direction": (
                        p["directions"][label]
                        if split == "development"
                        else (1 if index == 0 else -1)
                    ),
                    "steps": p["steps_seconds"],
                    "weights": [Q(*v) for v in p["rational_weights"]],
                }
            )
    return rows


def evaluate(run, split):
    plan = load_plan(run)
    sources = [LunarSource(run, i) for i in range(3)]
    points, rows = {}, []

    def sample(index, epoch, profile):
        key = f"{index}/{epoch}/{profile}"
        if key not in points:
            points[key] = apparent(sources[index], epoch, profile)
        return key

    for item in cases(run, plan, split):
        center = apparent(sources[item["window"]], item["epoch"], derivative=True)
        exact_rate = list(map(qbox, center["direction_derivative_per_source_day"]))
        row = {k: v for k, v in item.items() if k not in {"epoch", "weights"}}
        row.update(epoch_source_jd=str(item["epoch"]), center=center, profiles={})
        for profile in plan["profiles"]:
            templates = {}
            for step in item["steps"]:
                keys = [
                    sample(
                        item["window"],
                        item["epoch"] + Q(item["direction"] * i * step, 86400),
                        profile,
                    )
                    for i in range(len(item["weights"]))
                ]
                values = [[qbox(p) for p in points[k]["direction"]] for k in keys]
                rate = [
                    sum(
                        (
                            w * (v[axis] - values[0][axis])
                            for w, v in zip(item["weights"], values)
                        ),
                        I(),
                    )
                    * Q(86400, item["direction"] * step)
                    for axis in range(3)
                ]
                error = vector_distance(rate, exact_rate)
                templates[str(step)] = {
                    "point_keys": keys,
                    "derivative_per_source_day": [record(v) for v in rate],
                    "joint_error_from_continuous_source_derivative_arcsec_per_source_day": record(
                        error
                    ),
                }
            rates = [
                [qbox(p) for p in v["derivative_per_source_day"]]
                for v in templates.values()
            ]
            difference = vector_distance(*rates)
            row["profiles"][profile] = {
                "templates": templates,
                "step_difference_arcsec_per_source_day": record(difference),
                "named_model_step_check_passed": difference.bounds()[1]
                <= Q(plan["fixed_rate_arcsec_per_day"]),
                "rounded_clock_instantaneous_derivative_certified": False,
            }
        rows.append(row)
    control = None
    if split == "development":
        control = apparent(
            sources[2],
            calendar_jd_tdb(plan["record_window_labels"][2]),
            derivative=True,
        )
    return {
        "plan_sha256": PLAN_SHA,
        "split": split,
        "rows": rows,
        "points": points,
        "lunar_3000_source_control": control,
        "source_model": plan["source_model"],
        "original_references_replaced": False,
        "original_failure_records_regraded": False,
        "physical_TT_TDB_model_certified": False,
        "Horizons_model_equivalence_certified": False,
        "production_accuracy_certified": False,
        "new_external_observations": 0,
        "new_production_accuracy_holdouts": 0,
        "old_gate_codes": [2, 1],
        "full_goal_complete": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("split", choices=["development", "heldout"])
    p.add_argument("output", type=Path)
    a = p.parse_args()
    result = evaluate(a.run, a.split)
    with a.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(
        json.dumps(
            {
                "rows": len(result["rows"]),
                "points": len(result["points"]),
                "output_sha256": sha(a.output),
                "new_external_observations": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
