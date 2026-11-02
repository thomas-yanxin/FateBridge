"""Retain four original controls and add a declared uniform-source reference."""

import argparse
import copy
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_interval_reference import WINDOWS
from scripts.astrodice_nonuniform_reference import DEGREES, quality
from scripts.astrodice_transferred_reference import fit

DESIGN_SHA = "072c72e5a9f00d79107063aaf577b636fc693998316d989bb794a7463330c517"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path, proof_path, digest_key):
    data, proof = [json.loads(p.read_text()) for p in (path, proof_path)]
    if proof[digest_key] != sha(path):
        raise ValueError("Independent proof/input binding changed")
    return data, proof


def source_position_control(receiver):
    # Original position line is angular, not separate per-axis permissions.
    failures = []
    maximum = Q()
    for row in receiver["rows"]:
        for model in row["models"]:
            squared = sum(
                (
                    max(map(abs, map(Q, pair))) ** 2
                    for pair in model["model_minus_observed_arcsec"]
                ),
                Q(),
            )
            maximum = max(maximum, squared)
            if squared > Q("0.02") ** 2:
                failures.append(
                    {
                        "case_id": row["case_id"],
                        "model": [
                            model["SR_model"],
                            model["sun_epoch_model"],
                            model["potential_term"],
                        ],
                        "coordinate_distance_bound_squared": str(squared),
                    }
                )
    return {
        "fixed_angular_line_arcsec": "0.02",
        "method": "Euclidean RA/DEC upper bound is conservative for spherical angular separation; every full-LSB model residual included",
        "component_flags_are_not_a_joint_angular_pass": True,
        "maximum_coordinate_distance_bound_squared": str(maximum),
        "failed_model_nodes": failures,
        "all_source_model_levels_qualified": not failures,
        "service_model_equivalence_certified": False,
    }


def as_source_alias(result):
    result = copy.deepcopy(result)
    del result["quality"]["requested_TT_axis_not_internal_time_certified"]
    result["quality"]["TDB_day_not_certified_TT_day"] = True
    for row in result["all_windows"]:
        for axis in row["axes"]:
            old = "derivative_interval_arcsec_per_nominal_TT_day"
            if old in axis:
                axis["derivative_interval_arcsec_per_TDB_day"] = axis.pop(old)
    return result


def center_rate(receiver):
    center = next(r for r in receiver["rows"] if r["offset_seconds"] == 0)
    intervals = [m["rate_arcsec_per_source_day"] for m in center["models"]]
    return [
        [
            str(min(Q(v[a][0]) for v in intervals)),
            str(max(Q(v[a][1]) for v in intervals)),
        ]
        for a in (0, 1)
    ]


def analyze(
    design,
    receiver_path,
    receiver_proof,
    emission_path,
    emission_proof,
    reference_path,
    reference_proof,
):
    if sha(design / "design-before-development.json") != DESIGN_SHA:
        raise ValueError("Fixed receiver design changed")
    receiver, rproof = bind(receiver_path, receiver_proof, "receiver_transfer_sha256")
    emission, eproof = bind(emission_path, emission_proof, "transfer_sha256")
    original, oproof = bind(reference_path, reference_proof, "reference_sha256")
    if (
        rproof["rows_checked"] != 577
        or eproof["rows_checked"] != 577
        or receiver["emission_transfer_sha256"] != sha(emission_path)
        or receiver["independent_emission_proof_sha256"] != sha(emission_proof)
        or original["transfer_sha256"] != sha(emission_path)
        or original["independent_transfer_proof_sha256"] != sha(emission_proof)
    ):
        raise ValueError("Full retained source/reference proof chain required")
    offsets = list(range(-1440, 1441, 5))
    if [r["offset_seconds"] for r in receiver["rows"]] != offsets or [
        r["offset_seconds"] for r in emission["rows"]
    ] != offsets:
        raise ValueError("All original nodes required")
    epochs = {
        r["offset_seconds"]: (Q(r["target_receiver_JD"]) - 2451545) * 86400
        for r in receiver["rows"]
    }
    if any(t - epochs[0] != o for o, t in epochs.items()):
        raise ValueError("Exact uniform source coordinate changed")
    output = {
        "design_sha256": DESIGN_SHA,
        "receiver_sha256": sha(receiver_path),
        "receiver_proof_sha256": sha(receiver_proof),
        "emission_sha256": sha(emission_path),
        "emission_proof_sha256": sha(emission_proof),
        "original_reference_sha256": sha(reference_path),
        "original_reference_proof_sha256": sha(reference_proof),
        "controls": {},
        "source_model_position_control": source_position_control(receiver),
        "source_model_center_rate_envelope": center_rate(receiver),
        "physical_TT_time_model_certified": False,
        "physical_service_model_equivalence_certified": False,
        "physical_remainder_certified": False,
        "original_results_regraded": False,
        "production_acceptance_exit_code": 2,
        "retained_overall_numeric_gate_exit_code": 1,
        "full_goal_complete": False,
    }
    mapping = {
        "raw/native_source_seconds": "raw/native_source_seconds",
        "emission_only/native_source_seconds": "corrected/native_source_seconds",
        "raw/nominal_TT_seconds": "raw/nominal_TT_seconds",
        "emission_only/nominal_TT_seconds": "corrected/nominal_TT_seconds",
    }
    for name, source in mapping.items():
        output["controls"][name] = {
            "kind": "adopted_previous_first_result_unchanged",
            "source_control": source,
            "result": copy.deepcopy(original["controls"][source]),
        }
    for name, source in (
        ("raw/uniform_source_seconds", "raw/nominal_TT_seconds"),
        ("emission_only/uniform_source_seconds", "emission_only/nominal_TT_seconds"),
    ):
        output["controls"][name] = {
            "kind": "exact_centered_input_alias_distinct_coordinate_units",
            "numerical_input_same_as": source,
            "all_577_time_differences_exactly_equal": True,
            "result": as_source_alias(output["controls"][source]["result"]),
        }
    intervals = {
        r["offset_seconds"]: [
            tuple(map(Q, v)) for v in r["total_corrected_observation_interval_arcsec"]
        ]
        for r in receiver["rows"]
    }
    fitted = []
    for window in WINDOWS:
        for degree in DEGREES:
            item = fit(intervals, epochs, window, degree)
            fitted.append(item)
            print(
                "total/uniform_source_seconds",
                window,
                degree,
                item["status"],
                flush=True,
            )
    output["controls"]["total/uniform_source_seconds"] = {
        "kind": "joint_receiver_emitter_endpoint_transfer",
        "result": {"all_windows": fitted, "quality": quality(fitted)},
    }
    output["proof_aliases_count_as_independent_evidence"] = False
    return output


def main():
    parser = argparse.ArgumentParser()
    for name in (
        "design",
        "receiver",
        "receiver-proof",
        "emission",
        "emission-proof",
        "reference",
        "reference-proof",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    a = parser.parse_args()
    result = analyze(
        a.design,
        a.receiver,
        a.receiver_proof,
        a.emission,
        a.emission_proof,
        a.reference,
        a.reference_proof,
    )
    with a.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
