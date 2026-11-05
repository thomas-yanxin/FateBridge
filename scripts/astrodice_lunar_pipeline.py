"""Frozen actual-production/source attribution; never an astronomical certificate.

Reference generation imports no candidate. Native execution is isolated per row.
The fixed-frame decoder is shared: this tests source motion conditional on that
orientation, not an independently validated date-frame or TT/TDB relation.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import traceback
from fractions import Fraction as Q
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


PLAN_SHA = "be9f316e77e39200635358c6e17ea913c83c5f1917a42aaf93bd5686cc26f729"
BIAS = (
    (0.99999999999999412, -0.00000007078368961, 0.00000008056213978),
    (0.00000007078368695, 0.99999999999999700, 0.00000003306428553),
    (-0.00000008056214212, -0.00000003306427981, 0.99999999999999634),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open("x") as output:
        json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")


def plan(run):
    from scripts.astrodice_reference_data import verify_material

    path = run / "plan-before-evaluation.json"
    verify_material(path)
    return json.loads(path.read_text())


def unit_state(p, v):
    radius = math.sqrt(math.fsum(x * x for x in p))
    u = [x / radius for x in p]
    radial = math.fsum(x * y for x, y in zip(u, v))
    return u, [(x - y * radial) / radius for x, y in zip(v, u)]


def reference(run, split):
    from scripts.astrodice_de441_records import calendar_jd_tdb
    from scripts.astrodice_lunar_split import LunarSource, apparent

    protocol = plan(run)
    rows = []
    for case in protocol[split]:
        exact = calendar_jd_tdb(case["label"])
        number = float(exact)
        source = LunarSource(Path(protocol["reference_source"]), case["window"])
        rows.append(
            {
                **case,
                "exact_label_jd_tdb": str(exact),
                "native_numeric_jd": number,
                "exact_binary64_numeric_jd": str(Q(number)),
                "model": apparent(source, Q(number), derivative=True),
                "source_cells": sorted(source.cells),
            }
        )
    return {
        "protocol_sha256": PLAN_SHA,
        "split": split,
        "source_inputs_sha256": sha(run / "inputs-before-evaluation.json"),
        "rows": rows,
        "physical_TT_equivalence_certified": False,
        "original_failure_records_regraded": False,
    }


def native(run, split, index, backend, *, jpl_file=None):
    protocol = plan(run)
    case = protocol[split][index]
    from scripts.astrodice_de441_records import calendar_jd_tdb

    epoch = float(calendar_jd_tdb(case["label"]))
    source_dir = Path(protocol["reference_source"]).resolve()
    if backend == "jpl_record_window":
        kernel = (
            jpl_file.resolve()
            if jpl_file is not None
            else source_dir / f"diagnostic-kernels/case-{case['window']:02}.eph"
        )
        os.environ["FATEBRIDGE_JPL_FILE"] = kernel.name
        os.environ["SE_EPHE_PATH"] = str(kernel.parent)
    elif backend == "swieph":
        os.environ.pop("FATEBRIDGE_JPL_FILE", None)
        os.environ["SE_EPHE_PATH"] = str(Path("ephe").resolve())
    else:
        raise ValueError("Unplanned backend")

    from fatebridge.core import ephemeris_runtime as runtime
    from fatebridge.core.astro import continuous_lahiri as frame
    from fatebridge.core.astro import ephemeris
    from fatebridge.core.astro import runtime as domain_runtime
    from fatebridge.core.astro.source_session import source_session
    from fatebridge.core.compressed_ephemeris import audit_compressed_endpoints

    native_calls = []
    original = domain_runtime.ephemeris_call

    def recording(operation, *args, **kwargs):
        result = original(operation, *args, **kwargs)
        if operation == "calc":
            native_calls.append(
                {
                    "operation": operation,
                    "args": args,
                    "kwargs": kwargs,
                    "coordinates": result[0],
                    "returned_flags": result[1],
                }
            )
        return result

    domain_runtime.ephemeris_call = recording
    runtime.configure_ephemeris_path()
    metadata = {}
    result = {
        **case,
        "split": split,
        "backend_requested": backend,
        "native_numeric_jd": epoch,
        "exact_binary64_numeric_jd": str(Q(epoch)),
        "protocol_sha256": PLAN_SHA,
        "native_version": runtime.swe.version,
        "binding_version": runtime.swe.__version__,
        "native_calls": native_calls,
        "metadata": metadata,
        "python": sys.version,
        "configured_path": runtime.configured_ephemeris_path(),
        "configured_jpl_file": os.environ.get("FATEBRIDGE_JPL_FILE"),
    }
    try:
        with audit_compressed_endpoints() as audit, source_session() as session:
            value = ephemeris._swisseph_planet_state(
                "Moon",
                julian_day_tt=epoch,
                source_trace=session.trace,
                motion_metadata=metadata,
            )
        result["production_return"] = value
        result["trace"] = session.trace.snapshot()
        result["compressed_audit"] = audit
        result["file_slots_after_production"] = [
            runtime.swe.get_current_file_data(k) for k in range(5)
        ]
        policy = metadata["lunar_light_time"]["fixed_frame_source_derivative"]
        if policy["status"] != "applied":
            result["status"] = "unavailable"
            return result
        position = policy["full_fixed_frame_apparent_position_au"]
        velocity = policy["full_fixed_frame_velocity_au_per_native_argument_day"]
        decoded = frame.decode_native_fixed_reception_state(epoch, position, velocity)
        u, d = unit_state(
            decoded["position"], decoded["velocity_per_native_argument_day"]
        )
        result.update(
            status="ready",
            decoded_state=decoded,
            direction_j2000=u,
            direction_derivative_per_native_argument_day_j2000=d,
            mean_reception_frame=frame.frame_state(epoch)["mean_frame"],
        )
        # Position-only orientation control, after the production result and
        # source restoration have been recorded. No control replaces a result.
        flags = (
            runtime.swe.FLG_SWIEPH
            | runtime.swe.FLG_XYZ
            | runtime.swe.FLG_EQUATORIAL
            | runtime.swe.FLG_BARYCTR
            | runtime.swe.FLG_TRUEPOS
            | runtime.swe.FLG_J2000
        )
        with runtime.preserve_ephemeris_path():
            j, jf = original("calc", epoch, runtime.swe.EARTH, flags)
            i, inf = original(
                "calc", epoch, runtime.swe.EARTH, flags | runtime.swe.FLG_ICRS
            )
        result["bias_position_control"] = {
            "j2000": j,
            "j2000_flags": jf,
            "icrs": i,
            "icrs_flags": inf,
            "absolute_residual_au": [
                abs(j[k] - math.fsum(a * b for a, b in zip(BIAS[k], i[:3])))
                for k in range(3)
            ],
        }
    except (ValueError, RuntimeError, KeyError, OSError) as error:
        result.update(
            status="error",
            error_type=type(error).__name__,
            error=str(error),
            traceback=traceback.format_exc(),
        )
    finally:
        domain_runtime.ephemeris_call = original
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("reference", "native"))
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "heldout"), required=True)
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument(
        "--backend", choices=("swieph", "jpl_record_window"), default="swieph"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jpl-file", type=Path)
    args = parser.parse_args()
    value = (
        reference(args.run, args.split)
        if args.mode == "reference"
        else native(
            args.run, args.split, args.index, args.backend, jpl_file=args.jpl_file
        )
    )
    write_new(args.output, value)


if __name__ == "__main__":
    main()
