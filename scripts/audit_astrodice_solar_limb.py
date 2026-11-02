"""Discriminate solar apparent-position models without changing production.

Each sample keeps the default, diagnostic controls, both reference encodings,
and an independent aberration of published astrometric coordinates. No model
is fitted and no rate or unconditional physical accuracy is certified here.
"""

import argparse
import hashlib
import json
import math
import os
import traceback
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from importlib.metadata import version
from pathlib import Path

from scripts.astrodice_apparent_source_reference import (
    D,
    Reader,
    aberration,
    scale,
)
from scripts.astrodice_apparent_source_reference import unit as decimal_unit
from scripts.astrodice_reference_math import precise_direction
from scripts.astrodice_solar_limb_reference import replay


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def separation(a, b):
    def normalized(v):
        length = math.hypot(*v)
        if not length or not math.isfinite(length):
            raise ValueError("Invalid direction")
        return [x / length for x in v]

    a, b = normalized(a), normalized(b)
    cross = [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
    return (
        math.atan2(math.hypot(*cross), math.fsum(x * y for x, y in zip(a, b)))
        * math.degrees(1)
        * 3600
    )


def direction(angles):
    return [float(x) for x in precise_direction(*map(float, angles))]


def compare(vector, angles):
    error = separation(vector, direction(angles))
    # Full original one-LSB radius on each printed angle; L1 is a
    # conservative spherical metric bound, with a separate arithmetic floor.
    radius = (
        float(
            sum((Q(Decimal(10) ** Decimal(s).as_tuple().exponent) for s in angles), Q())
            * 3600
        )
        + 1e-9
    )
    lower, upper = max(0, error - radius), error + radius
    return {
        "status": (
            "numeric_failure"
            if lower > 0.02
            else (
                "declared_position_line_satisfied"
                if upper <= 0.02
                else "comparison_unresolved"
            )
        ),
        "difference_arcsec": error,
        "printing_and_arithmetic_radius_arcsec": radius,
        "error_lower_arcsec": lower,
        "error_upper_arcsec": upper,
        "fixed_line_arcsec": 0.02,
    }


def independent_aberration(run, case, angles):
    with localcontext() as context:
        context.prec = 100
        epoch = Q(case["exact_numeric_JD_fraction"])
        t = D(epoch)
        reader = Reader(run / "source-records", case["window_index"])
        earth = reader.states(t, case["body"])["Earth"]
        beta = scale(earth[3:], D(149597870700) / D(299792458) / D(86400))
        ray = [D(value) for value in precise_direction(*map(float, angles))]
        apparent = decimal_unit(aberration(ray, beta))
        return {
            "direction": [float(v.v) for v in apparent],
            "observer_barycentric_velocity_AU_per_TDB_day": [
                str(v.v) for v in earth[3:]
            ],
            "source_cells": sorted(reader.cells),
            "decimal_precision": 100,
            "time_contract": "Original source evaluated at nominal equal numeric TT/TDB argument; physical time conversion not certified.",
            "independent_of_native_corrections": True,
            "candidate_accuracy_certified": False,
        }


def audit(run, seal_path, cohort, index):
    root = Path(__file__).resolve().parents[1]
    seal = json.loads(seal_path.read_text())

    def check():
        for name, expected in seal["candidate_files"].items():
            if digest(root / name) != expected:
                raise ValueError("Frozen candidate or checker source changed: " + name)
        if digest(run / "selection-first.json") != seal["selection_sha256"]:
            raise ValueError("Selected source conditions changed")

    check()
    selected = json.loads((run / "selection-first.json").read_text())["cohorts"][
        cohort
    ][index]
    references = {}
    for encoding in ["JD", "MJD"]:
        prefix = cohort + "-" + encoding
        result = replay(
            run / (prefix + "-protocol.json"),
            run / (prefix + "-reference-first.json"),
            run / (prefix + "-raw"),
        )
        row = result["rows"][index]
        if row["id"] != selected["id"]:
            raise ValueError("Reference condition identity changed")
        references[encoding] = row
    from fatebridge.core.astro import runtime
    from fatebridge.core.astro.native_coordinates import COORDINATE_FLAGS
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace
    from fatebridge.core.astro.reference import PLANET_SWISSEPH_IDS

    if (
        not Path(runtime.__file__).is_relative_to(root)
        or digest(Path(runtime.swe.__file__)) != seal["native_binary_sha256"]
    ):
        raise ValueError("Unfrozen native implementation")
    swe = runtime.swe
    if (str(swe.version), version("pyswisseph")) != ("2.10.03", "2.10.3.2"):
        raise ValueError("Unaudited native or distribution version")
    source = json.loads((run / "source-records/geometric-reference.json").read_text())[
        "rows"
    ][selected["window_index"]]
    kernel = run / "source-records" / source["kernel_path"]
    if (
        digest(kernel) != source["kernel_sha256"]
        or Path(os.environ["SE_EPHE_PATH"]).resolve() != kernel.parent.resolve()
        or os.environ.get("FATEBRIDGE_JPL_FILE") != kernel.name
    ):
        raise ValueError("Diagnostic kernel configuration changed")
    epoch = float(Q(selected["exact_numeric_JD_fraction"]))
    trace = PhysicalEphemerisTrace()
    base = (
        swe.FLG_SWIEPH
        | swe.FLG_SPEED
        | swe.FLG_XYZ
        | swe.FLG_EQUATORIAL
        | swe.FLG_J2000
        | swe.FLG_ICRS
    )
    mask = sum(getattr(swe, name) for name in COORDINATE_FLAGS)
    variants = {
        "default": base,
        "no_GR": base | swe.FLG_NOGDEFL,
        "no_aberration": base | swe.FLG_NOABERR,
        "astrometric": base | swe.FLG_NOGDEFL | swe.FLG_NOABERR,
        "default_after_controls": base,
    }
    states = {}
    for mode, flags in variants.items():
        try:
            vector, returned = runtime.ephemeris_call(
                "calc", epoch, PLANET_SWISSEPH_IDS[selected["body"]], flags
            )
            if (
                returned < 0
                or returned & mask != (flags | swe.FLG_NONUT) & mask
                or runtime.ephemeris_model_from_retflag(returned) != "jpl"
                or len(vector) != 6
                or not all(math.isfinite(v) for v in vector)
            ):
                raise ValueError("Actual source, coordinate or vector contract changed")
            trace.observe(selected["body"] + "_" + mode, "jpl")
            states[mode] = {
                "status": "computed",
                "requested_flags": flags,
                "returned_flags": returned,
                "state_xyz_AU_and_AU_per_day": list(vector),
                "ephemeris_model": "jpl",
            }
        except Exception as error:
            states[mode] = {
                "status": "candidate_error",
                "error_type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }
    warm = None
    if (
        states["default"]["status"]
        == states["default_after_controls"]["status"]
        == "computed"
    ):
        warm = separation(
            states["default"]["state_xyz_AU_and_AU_per_day"][:3],
            states["default_after_controls"]["state_xyz_AU_and_AU_per_day"][:3],
        )
    comparisons = {}
    inside = (
        selected["nominal_source_background_ray"]
        and Q(selected["nominal_source_impact_radius_fraction"]) < 1
    )
    for encoding, row in references.items():
        point = row["observation"]
        if point is None:
            comparisons[encoding] = {"status": "reference_unavailable"}
            continue
        tests = {}
        for mode, state in states.items():
            tests[mode] = (
                compare(
                    state["state_xyz_AU_and_AU_per_day"][:3],
                    (
                        point["astrometric_printed_angles"]
                        if mode == "astrometric"
                        else point["apparent_printed_angles"]
                    ),
                )
                if state["status"] == "computed"
                else state
            )
        tests["piecewise_background_inside_no_GR"] = {
            "selected_native_mode": "no_GR" if inside else "default",
            **tests["no_GR" if inside else "default"],
        }
        extra = independent_aberration(
            run, selected, point["astrometric_printed_angles"]
        )
        extra["separation_from_printed_apparent_arcsec"] = separation(
            extra["direction"], direction(point["apparent_printed_angles"])
        )
        comparisons[encoding] = {
            "status": "compared_position_models",
            "observation": point,
            "native_comparisons": tests,
            "independent_aberration_of_quantity1": extra,
        }
    try:
        physical = trace.finish()
    except Exception as error:
        physical = {
            "status": "source_trace_error",
            "type": type(error).__name__,
            "message": str(error),
        }
    check()
    return {
        "case": selected,
        "epoch_native_hex": epoch.hex(),
        "native_version": swe.version,
        "binding_distribution_version": version("pyswisseph"),
        "states": states,
        "comparisons": comparisons,
        "native_default_repeat_drift_arcsec": warm,
        "warm_control_line_arcsec": 1e-9,
        "physical_sources": physical,
        "rate_accuracy_assessed": False,
        "production_formula_changed": False,
        "hypotheses_are_diagnostics_not_production_acceptance": True,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["run", "candidate-seal", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--cohort", choices=["A", "B"], required=True)
    p.add_argument("--case-index", type=int, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError(a.output)
    result = audit(a.run, a.candidate_seal, a.cohort, a.case_index)
    with a.output.open("x") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    print(result["case"]["id"], "position models recorded")
