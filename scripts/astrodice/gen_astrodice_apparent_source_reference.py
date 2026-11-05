"""Freeze automatic-differentiation references before native comparisons."""

import argparse
import hashlib
import json
import math
import sys
import traceback
from decimal import Decimal as N
from decimal import localcontext
from fractions import Fraction as F
from pathlib import Path

from scripts.astrodice.astrodice_apparent_source_reference import Reader, sample
from scripts.astrodice.astrodice_de441_records import calendar_jd_tdb

SOURCE_MANIFEST = "48f97f0490dfda470e363d6ba3209f209e90900cacb5c5d7ff114bf65efab660"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_fixed_policy(protocol):
    expected = {
        "position_line_arcsec": 0.02,
        "rate_line_arcsec_per_day": 0.002,
        "reference_precisions": [70, 100],
        "reference_precision_component_line": "1e-45",
        "reference_fd_steps_days": ["1/1048576", "1/2097152"],
        "reference_fd_order": 6,
        "reference_fd_vs_AD_line_arcsec_per_day": 1e-7,
        "require_same_mass_and_polynomial_cells": True,
    }
    if (
        any(protocol.get(name) != value for name, value in expected.items())
        or protocol.get("require_same_mass_and_polynomial_cells") is not True
    ):
        raise ValueError("Frozen source-reference qualification policy changed")


def _rate_reference(case, fixture, profile, protocol):
    reader = Reader(fixture, case["window_index"])
    # Preserve exactly the native API's single numeric argument, with no claim
    # that a TT label is physically identical to the model's nominal TDB time.
    epoch = float(calendar_jd_tdb(case["date_tdb"]))
    centers = [
        sample(reader, case["body"], epoch, profile, precision=p)
        for p in protocol["reference_precisions"]
    ]
    precise = centers[-1]
    with localcontext() as context:
        context.prec = 100
        precision_difference = max(
            abs(N(a) - N(b))
            for field in ("direction_icrf", "derivative_per_day")
            for a, b in zip(centers[0][field], precise[field])
        )
        probes = []
        estimates = []
        for declared in protocol["reference_fd_steps_days"]:
            h = F(declared)
            step = N(h.numerator) / N(h.denominator)
            points = []
            for k in (-3, -2, -1, 1, 2, 3):
                point = sample(
                    reader,
                    case["body"],
                    N.from_float(epoch) + k * step,
                    profile,
                    precision=70,
                    seed=0,
                )
                points.append(point)
                probes.append({"offset_days": str(k * h), "sample": point})
            weights = (-1, 9, -45, 45, -9, 1)
            estimate = [
                sum(
                    (
                        N(w) * N(p["direction_icrf"][axis])
                        for w, p in zip(weights, points)
                    ),
                    N(0),
                )
                / (60 * step)
                for axis in range(3)
            ]
            estimates.append(estimate)
        derivative = list(map(N, precise["derivative_per_day"]))
        differences = [
            math.hypot(*(float(x - y) for x, y in zip(estimate, derivative)))
            * (180 * 3600 / math.pi)
            for estimate in estimates
        ]
    same_cells = all(
        p["sample"]["solar_profile_cell"]["cell"]
        == precise["solar_profile_cell"]["cell"]
        and p["sample"]["original_polynomial_cells"]
        == precise["original_polynomial_cells"]
        for p in probes
    )
    same_centers = (
        centers[0]["solar_profile_cell"]["cell"]
        == precise["solar_profile_cell"]["cell"]
        and centers[0]["original_polynomial_cells"]
        == precise["original_polynomial_cells"]
    )
    qualified = (
        precision_difference <= N(protocol["reference_precision_component_line"])
        and max(differences) <= protocol["reference_fd_vs_AD_line_arcsec_per_day"]
        and same_cells
        and same_centers
    )
    return {
        **case,
        "native_numeric_argument": epoch,
        "status": (
            "qualified_under_declared_continuous_source_model"
            if qualified
            else "reference_quality_unresolved"
        ),
        "precision_component_difference": str(precision_difference),
        "same_profile_and_polynomial_cells": same_cells and same_centers,
        "finite_difference_vs_AD_arcsec_per_day": differences,
        "centers": centers,
        "finite_difference_samples": probes,
        "finite_difference_estimates_per_day": [list(map(str, v)) for v in estimates],
        "frame_projection_performed": False,
        "physical_TT_or_observational_accuracy_certified": False,
    }


def reference_row(case, fixture, profile, protocol):
    reader = Reader(fixture, case["window_index"])
    epoch = float(calendar_jd_tdb(case["date_tdb"]))
    positions = [
        sample(reader, case["body"], epoch, profile, precision=p, seed=0)
        for p in protocol["reference_precisions"]
    ]
    with localcontext() as context:
        context.prec = 100
        position_difference = max(
            abs(N(a) - N(b))
            for a, b in zip(
                positions[0]["direction_icrf"], positions[-1]["direction_icrf"]
            )
        )
    try:
        result = _rate_reference(case, fixture, profile, protocol)
    except Exception as error:
        # A derivative knot or stencil failure cannot erase a usable center.
        result = {
            **case,
            "native_numeric_argument": epoch,
            "status": "reference_quality_unresolved",
            "rate_reference_error": {
                "error_type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            },
        }
    result["position_centers"] = positions
    result["position_precision_component_difference"] = str(position_difference)
    result["position_status"] = (
        "qualified_under_declared_source_position_model"
        if position_difference <= N(protocol["reference_precision_component_line"])
        else "reference_quality_unresolved"
    )
    result["rate_status"] = result["status"]
    if result["position_status"] == "reference_quality_unresolved":
        result["status"] = "reference_quality_unresolved"
    return result


def collect(run, fixture, group, output):
    manifest = fixture / "manifest.json"
    if digest(manifest) != SOURCE_MANIFEST:
        raise ValueError("Frozen original record manifest changed")
    for name, expected in json.loads(manifest.read_text())["files"].items():
        if digest(fixture / name) != expected:
            raise ValueError("Frozen original source material changed: " + name)
    protocol_path = run / "protocol-before-development.json"
    protocol = json.loads(protocol_path.read_text())
    require_fixed_policy(protocol)
    for name, expected in protocol["source_artifact_sha256"].items():
        if digest(run / name) != expected:
            raise ValueError("Frozen native-source definition changed: " + name)
    profile = json.loads((run / "source-solar-profile.json").read_text())[
        "radius_mass_pairs"
    ]
    rows = []
    for case in protocol[group]:
        try:
            row = reference_row(case, fixture, profile, protocol)
        except Exception as error:
            row = {
                **case,
                "status": "reference_unavailable",
                "error_type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }
        rows.append(row)
        print(case["id"], row["status"], flush=True)
    forbidden = [
        name
        for name in sys.modules
        if name == "swisseph" or name == "fatebridge" or name.startswith("fatebridge.")
    ]
    if forbidden:
        raise ValueError("Reference producer imported candidate: " + str(forbidden))
    unqualified = [
        r["id"]
        for r in rows
        if r["status"] != "qualified_under_declared_continuous_source_model"
    ]
    result = {
        "method_id": "independent_de441_continuous_native_source_apparent_AD_v1",
        "protocol_sha256": digest(protocol_path),
        "group": group,
        "rows": rows,
        "candidate_imported": False,
        "exit_code": 2 if unqualified else 0,
        "unqualified_case_ids": unqualified,
        "full_goal_complete": False,
        "scope": "Declared continuous two-iteration native source position model and its analytic derivative. Decimal precision and local finite-difference checks are numerical evidence; raw DE441 physics and source corrections are shared, not independent observations or TT conversion.",
    }
    with output.open("x") as file:
        file.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result["exit_code"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--group", choices=["development", "holdout"], required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raise SystemExit(collect(args.run, args.fixture, args.group, args.output))
