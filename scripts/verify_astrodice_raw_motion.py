"""Exact Tn/first/second-derivative replay, without FateBridge or Swiss imports."""

import argparse
import hashlib
import json
import struct
from fractions import Fraction as Q
from pathlib import Path

PLAN_SHA = "bb20ffc5673e323742e3dfe9ab7b2d86b297f3289520955fc41b2771ddba4355"
GROUPS = {"Mercury": 0, "Venus": 1, "Mars": 3, "Sun": 10}


def dot(a, b):
    return sum((x * y for x, y in zip(a, b)), Q())


def squared_error(a, b):
    return sum(((x - y) ** 2 for x, y in zip(a, b)), Q())


def source_group(header, raw, epoch, group):
    values = struct.unpack("<1018d", raw)
    start, end = map(Q, values[:2])
    offset, n, parts = struct.unpack_from("<3i", header, 2696 + group * 12)
    width = (end - start) / parts
    part = min(int((epoch - start) // width), parts - 1)
    x = 2 * (epoch - start - part * width) / width - 1
    if not -1 <= x <= 1:
        raise ValueError("Exact reference outside source")
    axes = []
    for axis in range(3):
        first = offset - 1 + (3 * part + axis) * n
        c = list(map(Q, values[first : first + n]))
        t0, t1, d0, d1, a0, a1 = Q(1), x, Q(), Q(1), Q(), Q()
        value, velocity, acceleration = c[0], Q(), Q()
        for k, coefficient in enumerate(c[1:], 1):
            if k > 1:
                t0, t1, d0, d1, a0, a1 = (
                    t1,
                    2 * x * t1 - t0,
                    d1,
                    2 * t1 + 2 * x * d1 - d0,
                    a1,
                    4 * d1 + 2 * x * a1 - a0,
                )
            value += coefficient * t1
            velocity += coefficient * d1
            acceleration += coefficient * a1
        axes.append((value, velocity * 2 / width, acceleration * 4 / width**2))
    au = Q(struct.unpack_from("<d", header, 2680)[0])
    return [axes[axis][k] / au for k in range(3) for axis in range(3)]


def reference(header, raw, epoch, body):
    if body in {"Earth", "Moon"}:
        emb = source_group(header, raw, epoch, 2)
        moon = source_group(header, raw, epoch, 9)
        ratio = 1 + Q(struct.unpack_from("<d", header, 2688)[0])
        earth = [e - m / ratio for e, m in zip(emb, moon)]
        return earth if body == "Earth" else [e + m for e, m in zip(earth, moon)]
    return source_group(header, raw, epoch, GROUPS[body])


def verify(run, candidate_path, baseline_path):
    if (
        hashlib.sha256((run / "plan-before-evaluation.json").read_bytes()).hexdigest()
        != PLAN_SHA
    ):
        raise ValueError("Original kinematics plan changed")
    plan = json.loads((run / "plan-before-evaluation.json").read_text())
    candidate = json.loads(candidate_path.read_text())
    baseline = json.loads(baseline_path.read_text())
    split = candidate["split"]
    cases = plan["cases"][split]
    for data, is_candidate in [(candidate, True), (baseline, False)]:
        if (
            data["protocol_sha256"] != PLAN_SHA
            or data["candidate"] is not is_candidate
            or data["split"] != split
            or [r["case"] for r in data["rows"]] != cases
            or data["old_gates"] != {"production": 2, "overall": 1}
            or data["original_failures_regraded"] is not False
            or data["physical_accuracy_certified"] is not False
        ):
            raise ValueError("Original case population or claim changed")
    header = (run / "raw/header.bin").read_bytes()
    results = []
    if struct.unpack_from("<i", header, 2840)[0] != 441:
        raise ValueError("Reference edition changed")
    for row, old, case in zip(candidate["rows"], baseline["rows"], cases):
        if row["status"] != "captured" or old["status"] != "captured":
            raise ValueError("Original unavailable row remains unavailable")
        for sample in (row, old):
            if (
                sample["model"] != "jpl"
                or len(sample["source"]["files"]) != 1
                or sample["source"]["files"][0]["sha256"] != plan["raw_kernel_sha256"]
                or sample["source"]["accuracy_certified"] is not False
            ):
                raise ValueError("Actual native file identity or qualification changed")
        epoch = Q(float(Q(case["epoch"])))
        if (
            row["epoch_hex"] != float(epoch).hex()
            or old["epoch_hex"] != row["epoch_hex"]
        ):
            raise ValueError("Native argument changed")
        record = plan["record_receipts"][case["id"]]
        raw = Path(record["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["record_sha256"]:
            raise ValueError("Raw reference changed")
        if list(row["raw_states"]) != plan["bodies"]:
            raise ValueError("Raw body population changed")
        states = {}
        errors = {}
        lines = list(map(Q, plan["arithmetic_lines"].values()))
        for body, (state, policy) in row["raw_states"].items():
            if (
                len(state) != 9
                or policy["record_sha256"] != record["record_sha256"]
                or policy["record_index"] != record["record_index"]
                or policy["header_sha256"] != hashlib.sha256(header).hexdigest()
                or policy["tt_tdb_conversion_applied"] is not False
                or policy["observational_accuracy_certified"] is not False
            ):
                raise ValueError("Source identity/unit/clock claim changed")
            states[body] = reference(header, raw, epoch, body)
            measured = list(map(Q, state))
            error = [
                squared_error(
                    measured[i * 3 : i * 3 + 3], states[body][i * 3 : i * 3 + 3]
                )
                for i in range(3)
            ]
            if any(e > line**2 for e, line in zip(error, lines)):
                raise ValueError("Exact source arithmetic budget exceeded")
            errors[body] = list(map(str, error))
        fixed = row["motion"]["lunar_light_time"]["fixed_frame_source_derivative"]
        before = old["motion"]["lunar_light_time"]["fixed_frame_source_derivative"]
        if (
            fixed["analytic_observer_source"] != row["raw_states"]["Earth"][1]
            or fixed["fixed_observer_rotation"]["frame_derivative_added"] is not False
        ):
            raise ValueError("Analytic observer source receipt changed")
        if (
            fixed["status"] != "applied"
            or fixed["selected_stencil"] != "analytic_jpl_source"
            or fixed["sample_count"] != 0
            or fixed["acceleration_steps_days"] != []
            or fixed["selected_step_days"] is not None
            or fixed["acceleration_difference_au_per_day2"] is not None
            or fixed["observer_derivative_disagreement_arcsec_per_day"] is not None
        ):
            raise ValueError("Analytic method or null agreement evidence changed")
        earth = states["Earth"]
        matrix = [list(map(Q, r)) for r in fixed["fixed_observer_rotation"]["matrix"]]
        if len(matrix) != 3 or any(len(r) != 3 for r in matrix):
            raise ValueError("Invalid rotation shape")
        determinant = (
            matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
            - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
            + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
        )
        if abs(determinant - 1) > Q("1e-12") or max(
            abs(dot(a, b) - int(i == j))
            for i, a in enumerate(matrix)
            for j, b in enumerate(matrix)
        ) > Q("1e-12"):
            raise ValueError("Fixed rotation is not proper orthogonal")
        native = list(map(Q, fixed["observer_center_fixed_frame_state"]))

        def mapped(vector):
            return [dot(r, vector) for r in matrix]

        state_errors = [
            squared_error(mapped(earth[:3]), native[:3]),
            squared_error(mapped(earth[3:6]), native[3:6]),
        ]
        if any(
            e > Q(str(plan["fixed_frame_reproduction_line_au_or_au_per_day"])) ** 2
            for e in state_errors
        ):
            raise ValueError("Earth source/frame reproduction failed")
        expected = mapped(earth[6:9])
        acceleration = list(map(Q, fixed["acceleration_estimates_au_per_day2"][0]))
        new_error = squared_error(expected, acceleration)
        if new_error > Q("1e-15") ** 2:
            raise ValueError("Analytic observer acceleration budget exceeded")
        if before["sample_count"] != 10 or before["selected_stencil"] != "central":
            raise ValueError("Original ten-sample baseline changed")
        center = next(s for s in before["acceleration_samples"] if s["is_center"])
        if (
            center["velocity_au_per_native_argument_day"]
            != fixed["observer_center_fixed_frame_state"][3:6]
        ):
            raise ValueError("Baseline center changed")
        old_error = squared_error(
            expected, list(map(Q, before["acceleration_estimates_au_per_day2"][0]))
        )
        position_fields = {k: v for k, v in row["state"].items() if "speed" not in k}
        if position_fields != {
            k: v for k, v in old["state"].items() if "speed" not in k
        }:
            raise ValueError("Displayed positions changed")
        results.append(
            {
                "case_id": case["id"],
                "raw_body_error_squared": errors,
                "observer_acceleration_error_squared": str(new_error),
                "baseline_observer_acceleration_error_squared": str(old_error),
                "display_rate_change_arcsec_per_day": (
                    row["state"]["longitude_speed"] - old["state"]["longitude_speed"]
                )
                * 3600,
                "position_fields_unchanged": True,
            }
        )
    return {
        "protocol_sha256": PLAN_SHA,
        "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        "baseline_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        "split": split,
        "case_count": len(cases),
        "body_state_count": len(cases) * len(plan["bodies"]),
        "rows": results,
        "old_gates": {"production": 2, "overall": 1},
        "original_failures_regraded": False,
        "physical_accuracy_certified": False,
        "goal_complete": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.run, args.candidate, args.baseline)
    with args.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
