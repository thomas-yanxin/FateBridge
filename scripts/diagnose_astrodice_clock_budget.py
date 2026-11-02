"""Enclose complete apparent changes under two fixed, conditional clock models.

All planned rows remain. A budget result cannot regrade historical Horizons
comparisons, certify extrapolated TT/TDB physics or count as candidate accuracy.
"""

import argparse
import hashlib
import json
import math
import sys
import traceback
from fractions import Fraction as Q
from pathlib import Path

from scripts.astrodice_clock_interval import (
    FB_SHA256,
    I,
    Reader,
    apparent,
    clock_envelope,
)
from scripts.astrodice_de441_records import calendar_jd_tdb
from scripts.diagnose_astrodice_de441_clock import pi_bounds

SOURCE_MANIFEST = "96f8c9b6a8b2fde8f5f11b43316928fc2694fb90ab89c7d438bc7d4ef5aa9d30"


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def record(value):
    return value.record() if isinstance(value, I) else str(value)


def upper_float(value):
    return math.nextafter(float(value), math.inf)


def norm_upper(vector):
    return sum((v.square() for v in vector), I()).sqrt().bounds()[1]


def rotate(matrix, vector):
    return [sum((I(c) * v for c, v in zip(row, vector)), I()) for row in matrix]


def rate(direction, matrix, derivative, factor, angular_scale):
    p = rotate(matrix, [v.v for v in direction])
    source = rotate(matrix, [v.d * factor for v in direction])
    moving = rotate(derivative, [v.v for v in direction])
    v = [a + b for a, b in zip(source, moving)]
    rho = p[0].square() + p[1].square()
    if rho.bounds()[0] < Q(1, 10000):
        raise ValueError("Clock display longitude is ill-conditioned")
    return (p[0] * v[1] - p[1] * v[0]) / rho * angular_scale


def one(case, fixture, profile, clock_source, frame):
    exact = calendar_jd_tdb(case["date_nominal_tt"])
    native = Q(float(exact))
    if frame["id"] != case["id"] or Q(frame["native_numeric_argument"]) != native:
        raise ValueError("Frozen display bridge epoch changed")
    pl, ph = pi_bounds()
    angular_scale = 648000 / I(pl, ph)
    reader = Reader(fixture, case["window_index"])
    center, center_cells = apparent(reader, case["body"], I(native), profile)
    clock = clock_envelope(clock_source, exact)
    hypotheses = {}
    for name, budget, factor in [
        ("source_documented_offset_no_rate_bound", Q(1, 500), None),
        (
            "full_geocentric_FB_analytic_envelope_conditional_model",
            clock["maximum_offset_seconds"],
            clock["tdb_per_tt_rate_factor"],
        ),
    ]:
        try:
            epoch = I(exact - budget / 86400, exact + budget / 86400)
            value, cells = apparent(reader, case["body"], epoch, profile)
            if cells != center_cells:
                raise ValueError("Clock interval is not within the center source cells")
            speed = norm_upper([v.d for v in value])
            radius = budget / 86400 + abs(exact - native)
            chord = speed * radius
            if chord >= 1:
                raise ValueError("Clock direction bound outside local angular branch")
            angle = I(chord) / (1 - I(chord / 2).square()).sqrt() * angular_scale
            item = {
                "status": "source_interval_enclosed_under_declared_clock_hypothesis",
                "maximum_offset_seconds": str(budget),
                "source_epoch_interval": epoch.record(),
                "source_cells": cells,
                "direction_icrf_intervals": [v.v.record() for v in value],
                "direction_derivative_intervals_per_TDB_day": [
                    v.d.record() for v in value
                ],
                "direction_position_change_upper_arcsec": upper_float(
                    angle.bounds()[1]
                ),
                "physical_clock_hypothesis_certified": False,
                "display_rate_change_upper_arcsec_per_TT_day": None,
                "rate_constraint_reason": "Offset magnitude alone does not bound the clock-rate factor.",
            }
            if factor is not None:
                frames = {}
                for fname, f in frame["frames"].items():
                    changes = []
                    absolute = []
                    for derivative in f["derivatives"]:
                        base = rate(
                            center, f["matrix"], derivative, I(1), angular_scale
                        )
                        shifted = rate(
                            value, f["matrix"], derivative, factor, angular_scale
                        )
                        changes.append((shifted - base).absolute_upper())
                        absolute.append(shifted.record())
                    frames[fname] = {
                        "clock_change_upper_arcsec_per_day": upper_float(max(changes)),
                        "rate_intervals_arcsec_per_TT_day": absolute,
                    }
                identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
                zero = [[0, 0, 0]] * 3
                item.update(
                    display_rate_change_upper_arcsec_per_TT_day=frames,
                    clock_rate_factor=factor.record(),
                    icrf_RA_rate_interval_arcsec_per_TT_day=rate(
                        value, identity, zero, factor, angular_scale
                    ).record(),
                    rate_constraint_reason="Implicit derivative of the named full analytic clock model; physical extrapolation remains unqualified.",
                )
            hypotheses[name] = item
        except Exception as error:
            hypotheses[name] = {
                "status": "source_interval_unqualified",
                "error_type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }
    return {
        **case,
        "native_numeric_argument": float(native),
        "calendar_to_native_rounding_seconds": str((native - exact) * 86400),
        "clock_model_envelope": {k: record(v) for k, v in clock.items()},
        "hypotheses": hypotheses,
        "candidate_accuracy_pass": False,
        "center_direction_icrf_intervals": [v.v.record() for v in center],
        "center_derivative_intervals_per_TDB_day": [v.d.record() for v in center],
    }


def collect(run, fixture, group, frames, output):
    protocol_path = run / "protocol-before-development.json"
    protocol = json.loads(protocol_path.read_text())
    if (
        protocol["position_line_arcsec"] != 0.02
        or protocol["rate_line_arcsec_per_day"] != 0.002
        or protocol["interval_binary_fraction_bits"] != 256
        or protocol["source_documented_offset_seconds"] != "1/500"
    ):
        raise ValueError("Frozen clock budget policy changed")
    manifest = fixture / "manifest.json"
    if digest(manifest) != SOURCE_MANIFEST:
        raise ValueError("Frozen coefficient source manifest changed")
    for n, h in json.loads(manifest.read_text())["files"].items():
        if digest(fixture / n) != h:
            raise ValueError("Frozen coefficient source changed")
    if digest(run / "dtdb.c") != FB_SHA256 or protocol["FB_source_sha256"] != FB_SHA256:
        raise ValueError("Full author clock definition changed")
    profile_path = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/astrodice-apparent-source-v1/source-solar-profile.json"
    )
    if (
        digest(profile_path)
        != "05523a9aa716373cd16ea400ad93182fdd672ac18e93618fb5eb6bd476adbc83"
    ):
        raise ValueError("Frozen finite-Sun source table changed")
    profile = json.loads(profile_path.read_text())["radius_mass_pairs"]
    frame_manifest = json.loads((frames / "manifest.json").read_text())
    for name, expected in frame_manifest["files"].items():
        if digest(frames / name) != expected:
            raise ValueError("Frozen frame bridge changed")
    rows = []
    for case in protocol[group]:
        try:
            frame = json.loads((frames / (case["id"] + ".json")).read_text())
            row = one(case, fixture, profile, (run / "dtdb.c").read_text(), frame)
        except Exception as error:
            row = {
                **case,
                "status": "source_interval_unavailable",
                "error_type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc(),
            }
        rows.append(row)
        details = row.get("status")
        if details is None:
            details = {n: v["status"] for n, v in row["hypotheses"].items()}
        print(case["id"], details, flush=True)
    forbidden = [
        n
        for n in sys.modules
        if n == "swisseph" or n == "fatebridge" or n.startswith("fatebridge.")
    ]
    if forbidden:
        raise ValueError("Source encloser imported candidate")
    unknown = [
        r["id"]
        for r in rows
        if r.get("status")
        or any(
            h["status"] != "source_interval_enclosed_under_declared_clock_hypothesis"
            for h in r["hypotheses"].values()
        )
    ]
    result = {
        "method_id": "outward_256_bit_complete_apparent_conditional_clock_budget_v1",
        "protocol_sha256": digest(protocol_path),
        "group": group,
        "rows": rows,
        "unqualified_ids": unknown,
        "exit_code": 2 if unknown else 0,
        "candidate_imported": False,
        "candidate_accuracy_acceptances": 0,
        "full_goal_complete": False,
        "original_Horizons_results_regraded": False,
        "scope": "Conditional source-model time-offset/rate enclosures, shared display bridge. No actual TT/TDB or extrapolated clock validity certification.",
    }
    with output.open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write("\n")
    return result["exit_code"]


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["run", "fixture", "frames", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--group", choices=["development", "holdout"], required=True)
    args = p.parse_args()
    raise SystemExit(
        collect(args.run, args.fixture, args.group, args.frames, args.output)
    )
