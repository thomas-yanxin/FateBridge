"""Capture a shared display bridge only; never sample a delivered candidate rate."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from scripts.astrodice_de441_records import calendar_jd_tdb
from scripts.audit_astrodice_local_motion import orientation_derivative


def capture(case, fixture):
    from fatebridge.core.astro.physical_sources import PhysicalEphemerisTrace

    original = json.loads((fixture / "geometric-reference.json").read_text())["rows"][
        case["window_index"]
    ]
    kernel = fixture / original["kernel_path"]
    if hashlib.sha256(kernel.read_bytes()).hexdigest() != original["kernel_sha256"]:
        raise ValueError("Original diagnostic kernel changed")
    if (
        os.environ["FATEBRIDGE_JPL_FILE"] != kernel.name
        or Path(os.environ["SE_EPHE_PATH"]).resolve() != kernel.parent.resolve()
    ):
        raise ValueError("Declared source file configuration changed")
    epoch = float(calendar_jd_tdb(case["date_nominal_tt"]))
    trace = PhysicalEphemerisTrace()
    frames = {}
    for name in ["tropical", "lahiri"]:
        matrix, derivatives, geometry = orientation_derivative(
            epoch, name == "lahiri", "jpl", trace
        )
        frames[name] = {
            "matrix": matrix,
            "derivatives": derivatives,
            "geometry": geometry,
        }
    return {
        "id": case["id"],
        "native_numeric_argument": epoch,
        "frames": frames,
        "source": trace.finish(),
        "delivered_candidate_rate_sampled": False,
        "independent_frame_certification": False,
        "full_goal_complete": False,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--case", type=Path, required=True)
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = capture(json.loads(args.case.read_text()), args.fixture)
    with args.output.open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write("\n")
