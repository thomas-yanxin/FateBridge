"""Replay restoration grades without importing the producer or FateBridge.

Checks stored arithmetic and original fixed lines, not independent celestial
frame physics or physical reference error bounds. Optional --full-kernel
checks each excerpt directly against the complete pinned source file.
"""

import argparse
import hashlib
import json
import math
import struct
from decimal import Decimal
from pathlib import Path

PASS = "declared_lines_satisfied_under_reference_model"
FAIL = "numeric_failure_under_declared_reference_model"
UNKNOWN = "reference_quality_unresolved"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(folder, full_kernel=None):
    def load(name):
        return json.loads((folder / name).read_text())

    p, reference, source = map(
        load,
        [
            "protocol-before-queries.json",
            "reference-first.json",
            "candidate-before-first.json",
        ],
    )
    if (
        digest(folder / "protocol-before-queries.json") != source["protocol_sha256"]
        or digest(folder / "reference-first.json") != source["reference_sha256"]
        or p["fixed_rate_arcsec_per_day"] != 0.002
        or p["fixed_position_arcsec"] != 0.02
        or len(p["cases"]) != 14
        or sum(v["role"] == "new_predeclared_condition" for v in p["cases"]) != 12
    ):
        raise ValueError("Frozen inputs, cohort or numerical lines changed")
    counts = {}
    for model in ["swieph", "jpl"]:
        candidate = load(model + "-candidate-first.json")
        if len(candidate["rows"]) != 14 or candidate["model"] != model:
            raise ValueError("Candidate population changed")
        counts[model] = {"position_pass": 0, "rate_pass": 0, "rate_fail": 0}
        for case, expected, observed in zip(
            p["cases"], reference["rows"], candidate["rows"]
        ):
            if any(expected[k] != v or observed[k] != v for k, v in case.items()):
                raise ValueError("Case identity changed")
            position = observed["layers"]["position"]
            center = expected["samples"]["0"]
            a, d = map(lambda v: math.radians(float(v)), center["printed_angles"])
            direction = [
                math.cos(d) * math.cos(a),
                math.cos(d) * math.sin(a),
                math.sin(d),
            ]
            vector = position["native_values"][:3]
            norm = math.sqrt(sum(v * v for v in vector))
            vector = [v / norm for v in vector]
            cross = [
                vector[1] * direction[2] - vector[2] * direction[1],
                vector[2] * direction[0] - vector[0] * direction[2],
                vector[0] * direction[1] - vector[1] * direction[0],
            ]
            error = (
                math.atan2(
                    math.sqrt(sum(v * v for v in cross)),
                    sum(a * b for a, b in zip(vector, direction)),
                )
                * 180
                * 3600
                / math.pi
            )
            noise = (
                math.radians(
                    sum(
                        float(Decimal(10) ** Decimal(v).as_tuple().exponent)
                        for v in center["printed_angles"]
                    )
                )
                + 8e-15
            )
            radius = math.nextafter(noise * 180 * 3600 / math.pi + 1e-9, math.inf)
            if (
                abs(error - position["midpoint_error_arcsec"]) > 1e-8
                or abs(radius - position["printing_and_arithmetic_radius_arcsec"])
                > 1e-15
            ):
                raise ValueError("Independent position arithmetic disagrees")
            if position["status"] != PASS or error + radius > 0.02:
                raise ValueError("Position pass declaration disagrees")
            counts[model]["position_pass"] += 1
            rate = observed["layers"]["rate"]
            if set(rate["frames"]) != {"tropical", "lahiri"}:
                raise ValueError("Missing display-rate frame")
            frame_status = []
            for frame in rate["frames"].values():
                ref = frame["reference"]
                error = abs(
                    frame["candidate_state"]["longitude_speed"] * 3600
                    - ref["midpoint_arcsec_per_day"]
                )
                radius = ref["rounding_and_frame_check_radius_arcsec_per_day"]
                low, high = max(0.0, error - radius), error + radius
                if (
                    error != frame["midpoint_error_arcsec_per_day"]
                    or low != frame["conditional_error_lower_arcsec_per_day"]
                    or high != frame["conditional_error_upper_arcsec_per_day"]
                    or radius < expected["step_difference_arcsec_per_day"]
                    or ref["frame_step_difference_arcsec_per_day"] > 0.00002
                ):
                    raise ValueError(
                        "Independent rate/error propagation replay disagrees"
                    )
                frame_status.append(
                    FAIL
                    if low > 0.002
                    else (
                        PASS
                        if high <= 0.002 and ref["frame_check_qualified"]
                        else UNKNOWN
                    )
                )
            status = (
                FAIL
                if FAIL in frame_status
                else UNKNOWN if UNKNOWN in frame_status else PASS
            )
            if rate["status"] != status:
                raise ValueError("Rate grade differs from original fixed line")
            counts[model]["rate_pass" if status == PASS else "rate_fail"] += 1
        if candidate["exit_code"] != (0 if model == "jpl" else 1):
            raise ValueError("Original candidate outcome changed")
    if counts != {
        "swieph": {"position_pass": 14, "rate_pass": 13, "rate_fail": 1},
        "jpl": {"position_pass": 14, "rate_pass": 14, "rate_fail": 0},
    }:
        raise ValueError("First comparison result changed")
    mini = load("mini-full-first-comparison.json")
    excerpts = load("excerpts-before-candidates.json")
    if len(mini["rows"]) != 14 or len(excerpts["files"]) != 14:
        raise ValueError("Excerpt cohort changed")
    for row, excerpt in zip(mini["rows"], excerpts["files"]):
        if row["id"] != excerpt["id"] or not row["matches_full_numeric_leaves"]:
            raise ValueError("Full/excerpt numeric replay differs")
        path = folder / excerpt["path"]
        if (
            digest(path) != excerpt["sha256"]
            or row["source_sha256"] != excerpt["sha256"]
        ):
            raise ValueError("Excerpt content identity changed")
        original = next(
            v for v in load("jpl-candidate-first.json")["rows"] if v["id"] == row["id"]
        )
        replayed = load("mini-" + row["id"] + ".json")
        if (
            replayed["position"]["native_values"]
            != original["layers"]["position"]["native_values"]
        ):
            raise ValueError("Excerpt vector is not bitwise equal to full file")
        for frame in ["tropical", "lahiri"]:
            for key in [
                "candidate_state",
                "reference",
                "midpoint_error_arcsec_per_day",
                "conditional_error_lower_arcsec_per_day",
                "conditional_error_upper_arcsec_per_day",
                "frame_geometry",
            ]:
                if (
                    replayed["rate"]["frames"][frame][key]
                    != original["layers"]["rate"]["frames"][frame][key]
                ):
                    raise ValueError("Excerpt display leaves differ")
    pin = load("download-first-receipt.json")
    if pin["returncode"] or pin["expected_sha256"] != excerpts["source_full_sha256"]:
        raise ValueError("Acquisition receipt changed")
    if full_kernel is not None:
        if (
            full_kernel.stat().st_size != 2788676624
            or digest(full_kernel) != pin["expected_sha256"]
        ):
            raise ValueError("Complete original DE441 content pin differs")
        with full_kernel.open("rb") as stream:
            header, constants = stream.read(8144), stream.read(8144)
            start = struct.unpack_from("<d", header, 2652)[0]
            for excerpt in excerpts["files"]:
                raw = (folder / excerpt["path"]).read_bytes()
                if raw[8144:16288] != constants or any(
                    raw[i] != header[i]
                    for i in range(8144)
                    if not (i < 252 or 2652 <= i < 2668)
                ):
                    raise ValueError(
                        "Excerpt changed non-title/range header or constants"
                    )
                for offset, index in enumerate(excerpt["full_file_indices"]):
                    stream.seek((index + 2) * 8144)
                    record = stream.read(8144)
                    if record != raw[
                        (offset + 2) * 8144 : (offset + 3) * 8144
                    ] or struct.unpack_from("<2d", record) != (
                        start + index * 32,
                        start + (index + 1) * 32,
                    ):
                        raise ValueError(
                            "Excerpt coefficients differ from complete pinned source"
                        )
    if load("original-overall-gate.json")["overall_numeric_gate_exit_code"] != 1:
        raise ValueError("Original overall failure was relabelled")
    return {
        "method_id": "standalone_de441_restoration_receipt_arithmetic_replay_v1",
        "exit_code": 0,
        "counts": counts,
        "excerpt_numeric_comparisons": 14,
        "full_kernel_and_all_excerpt_bytes_verified": full_kernel is not None,
        "producer_or_FateBridge_imported": False,
        "old_overall_exit_code": 1,
        "full_objective_complete": False,
        "scope": "Independent replay of stored arithmetic and fixed grades; reference celestial data and native orientation remain separately qualified. Not physical frame, clock or prediction certification.",
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder", type=Path, required=True)
    p.add_argument("--full-kernel", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = verify(a.folder, a.full_kernel)
    with a.output.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps(result, indent=2))
