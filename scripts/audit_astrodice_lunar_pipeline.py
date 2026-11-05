"""Retain all actual lunar pipeline rows under the fixed source error lines."""

import argparse
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import I
from scripts.astrodice_lunar_pipeline import BIAS, PLAN_SHA, plan, write_new
from scripts.astrodice_source_slope_bounds import pi_bounds
from scripts.verify_astrodice_lunar_pipeline import verify


def interval(pair):
    return I(*map(Q, pair))


def transform(matrix, vector):
    return [sum((Q(a) * b for a, b in zip(row, vector)), I()) for row in matrix]


def norm(vector):
    return sum((v.square() for v in vector), I()).sqrt()


def pack(value):
    return {
        "bounds": list(map(str, value.bounds())),
        "lower": float(value.bounds()[0]),
        "upper": float(value.bounds()[1]),
    }


def within(value, limit):
    return value.absolute_upper() <= Q(limit)


def audit(run, split, reference_path, sampler=None, *, jpl_file=None):
    from scripts.astrodice_current_sampling import sample_lunar

    if sampler is None:
        from functools import partial

        sampler = partial(sample_lunar, jpl_file=jpl_file)
    protocol = plan(run)
    reference = json.loads(reference_path.read_text())
    verify(run, reference_path)
    if reference["split"] != split:
        raise ValueError("Independent reference split detached")
    scale = 648000 / I(*pi_bounds())
    rows = []
    for index, (case, ref) in enumerate(zip(protocol[split], reference["rows"])):
        p = transform(BIAS, list(map(interval, ref["model"]["direction"])))
        v = transform(
            BIAS,
            list(map(interval, ref["model"]["direction_derivative_per_source_day"])),
        )
        for backend in protocol["backends"]:
            native = sampler(run, split, index, backend)
            if (
                any(native[k] != value for k, value in case.items())
                or native["protocol_sha256"] != PLAN_SHA
                or native["backend_requested"] != backend
                or native["split"] != split
                or native["exact_binary64_numeric_jd"]
                != ref["exact_binary64_numeric_jd"]
                or Q(native["native_numeric_jd"]) != Q(ref["exact_binary64_numeric_jd"])
            ):
                raise ValueError("Native row rebound from frozen input")
            row = {
                **case,
                "backend": (
                    "jpl_explicit_source"
                    if backend == "jpl_record_window" and jpl_file is not None
                    else backend
                ),
                "protocol_backend": backend,
                "source_filename": native.get("configured_jpl_file"),
                "status": native["status"],
            }
            if native["status"] != "ready":
                row.update(
                    qualified=False,
                    error=native.get("error"),
                    error_type=native.get("error_type"),
                )
                rows.append(row)
                continue
            actual_model = native["production_return"][1]
            expected_model = "swieph" if backend == "swieph" else "jpl"
            policy = native["metadata"]["lunar_light_time"][
                "fixed_frame_source_derivative"
            ]
            context_ok = (
                actual_model == expected_model
                and policy["status"] == "applied"
                and policy["center_native_states_reproduced_exactly"] is True
                and policy["center_file_context_reproduced_exactly"] is True
                and native["trace"]["atomic_file_read_proven"] is False
            )
            u = native["direction_j2000"]
            d = native["direction_derivative_per_native_argument_day_j2000"]
            position_error = norm([I(Q(a)) - b for a, b in zip(u, p)]) * scale
            rate_error = norm([I(Q(a)) - b for a, b in zip(d, v)]) * scale
            mean = native["mean_reception_frame"]
            fixed_p, fixed_v = transform(mean, p), transform(mean, v)
            reference_longitude_rate = (
                (fixed_p[0] * fixed_v[1] - fixed_p[1] * fixed_v[0])
                / (fixed_p[0].square() + fixed_p[1].square())
                * scale
            )
            native_rate = (
                Q(policy["full_fixed_frame_longitude_speed_degrees_per_day"]) * 3600
            )
            longitude_error = I(native_rate) - reference_longitude_rate
            position_pass = within(position_error, protocol["position_line_arcsec"])
            rate_pass = within(
                longitude_error, protocol["rate_line_arcsec_per_source_day"]
            )
            vector_pass = within(
                rate_error, protocol["rate_line_arcsec_per_source_day"]
            )
            row.update(
                context_ok=context_ok,
                position_chord_error_arcsec=pack(position_error),
                unit_direction_derivative_error_arcsec_per_source_day=pack(rate_error),
                signed_fixed_longitude_rate_error_arcsec_per_source_day=pack(
                    longitude_error
                ),
                reference_fixed_longitude_rate_arcsec_per_source_day=pack(
                    reference_longitude_rate
                ),
                position_pass=position_pass,
                longitude_rate_pass=rate_pass,
                auxiliary_full_direction_rate_pass=vector_pass,
                qualified=context_ok and position_pass and rate_pass and vector_pass,
                final_displayed_longitude_speed_degrees_per_native_day=native[
                    "production_return"
                ][0]["longitude_speed"],
                full_displayed_rate_independently_graded=False,
                bias_position_control=native["bias_position_control"],
            )
            rows.append(row)
    numeric_failure = any(
        row.get("position_pass") is False
        or row.get("rate_pass", row.get("longitude_rate_pass")) is False
        or row.get("auxiliary_full_direction_rate_pass") is False
        for row in rows
    )
    gate = (
        1 if numeric_failure else 2 if any(not row["qualified"] for row in rows) else 0
    )
    return {
        "exit_code": gate,
        "declared_source_lines_satisfied": gate == 0,
        "physical_accuracy_certified": False,
        "protocol_sha256": PLAN_SHA,
        "split": split,
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "position_line_arcsec": protocol["position_line_arcsec"],
        "rate_line_arcsec_per_source_day": protocol["rate_line_arcsec_per_source_day"],
        "rows": rows,
        "scope": protocol["purpose"],
        "position_metric": "Small-angle unit-direction chord times radians-to-arcseconds; conditional shared frame",
        "auxiliary_rate_metric": "Full unit-direction derivative vector norm; stronger than old longitude-only line, not a redefinition of original acceptance",
        "physical_TT_equivalence_certified": False,
        "complete_moving_frame_derivative_certified": False,
        "original_failure_records_regraded": False,
        "original_overall_gate": protocol["original_overall_gate"],
        "original_production_gate": protocol["original_production_gate"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "heldout"), required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jpl-file", type=Path)
    args = parser.parse_args()
    result = audit(args.run, args.split, args.reference, jpl_file=args.jpl_file)
    write_new(args.output, result)
    raise SystemExit(result["exit_code"])


if __name__ == "__main__":
    main()
