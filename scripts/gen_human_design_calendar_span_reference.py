"""Additional DE440 seasonal positions across all600supported birthTT years.

Explicit maintenance only. No FateBridge or Swiss imports, online downloads,
civil UTC conversions or engine-selected clocks. The frozen plan fixes epochs,
targets and tolerances before collection; ordinary tests read the JSON facts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "tests/fixtures/human-design-calendar-span-plan.json"
OUTPUT = ROOT / "tests/fixtures/human-design-calendar-span-de440.json"


def derive(kernel_path: Path) -> dict:
    import numpy as np
    from skyfield.api import load, load_file
    from skyfield.framelib import ecliptic_frame

    plan = json.loads(PLAN.read_text())
    if len(plan["birth_epochs"]) != 1200:
        raise ValueError("All1200 frozen calendar strata are required")
    raw = kernel_path.read_bytes()
    if hashlib.md5(raw).hexdigest() != plan["kernel_md5"]:
        raise ValueError("DE440 does not match NASA's published checksum")
    for name in ("skyfield", "jplephem", "numpy"):
        if version(name) != plan[name + "_version"]:
            raise ValueError("Reference runtime differs from the frozen plan")
    kernel = load_file(str(kernel_path))
    ts = load.timescale(builtin=True)
    earth = kernel[399]
    births = np.array([r["jd_tt"] for r in plan["birth_epochs"]])

    def apparent(body, epochs):
        position = earth.at(ts.tt_jd(epochs)).observe(kernel[body]).apparent()
        latitude, longitude, distance = position.frame_latlon(ecliptic_frame)
        return longitude.degrees, latitude.degrees, distance.au

    natal_sun = apparent(10, births)[0]

    def residual(epochs):
        return (natal_sun - apparent(10, epochs)[0]) % 360.0 - 88.0

    lower, upper = births - 100, births - 70
    if not (np.all(residual(lower) > 0) and np.all(residual(upper) < 0)):
        raise ValueError("Independent solar roots are not bracketed")
    for _ in range(42):
        middle = lower + (upper - lower) / 2
        earlier = residual(middle) > 0
        lower = np.where(earlier, middle, lower)
        upper = np.where(earlier, upper, middle)
    roots = lower + (upper - lower) / 2
    widths = (upper - lower) * 86400
    residuals = residual(roots) * 3600
    if (
        np.max(widths) > plan["root_maximum_bracket_width_seconds"]
        or np.max(np.abs(residuals)) > plan["root_maximum_residual_arcseconds"]
    ):
        raise ValueError("Independent root numerical convergence failed")
    epochs = np.concatenate((births, roots))
    positions = {name: apparent(body, epochs) for name, body in plan["bodies"].items()}
    pairs = []
    for index, item in enumerate(plan["birth_epochs"]):
        sides = {}
        for side, offset in (("personality", 0), ("design", len(births))):
            sides[side] = {
                "jd_tt": float(epochs[index + offset]),
                "positions": {
                    name: {
                        "longitude": float(value[0][index + offset]),
                        "latitude": float(value[1][index + offset]),
                        "distance_au": float(value[2][index + offset]),
                        "target_id": plan["bodies"][name],
                    }
                    for name, value in positions.items()
                },
            }
        pairs.append(
            {
                "label": item["label"],
                **sides,
                "independent_solver": {
                    "target_arc_degrees": 88.0,
                    "residual_arcseconds": float(residuals[index]),
                    "bracket_width_seconds": float(widths[index]),
                    "iterations": 42,
                },
            }
        )
    kernel.close()
    return {
        "method_id": "independent_de440_calendar_span_skyfield_v1",
        "plan_path": PLAN.relative_to(ROOT).as_posix(),
        "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "kernel_url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp",
        "kernel_checksum_url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/aa_checksums.txt",
        "kernel_md5": hashlib.md5(raw).hexdigest(),
        "kernel_sha256": hashlib.sha256(raw).hexdigest(),
        "kernel_bytes": len(raw),
        "generator_versions": {
            name: version(name) for name in ("skyfield", "jplephem", "numpy")
        },
        "frame_source_url": "https://rhodesmill.org/skyfield/api-framelib.html",
        "apparent_source_url": "https://rhodesmill.org/skyfield/positions.html",
        "target_scope": plan["target_scope"],
        "original_plan_sha256": plan["original_plan_sha256"],
        "original_reference_sha256": plan["original_reference_sha256"],
        "scope": plan["scope"],
        "pairs": pairs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = derive(args.kernel)
    if args.check:
        if json.loads(args.output.read_text()) != result:
            raise SystemExit("Independent astronomy reference differs")
    else:
        args.output.write_bytes(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
        )
    print(
        json.dumps(
            {
                "pairs": len(result["pairs"]),
                "observations": len(result["pairs"]) * 20,
                "checked": args.check,
            }
        )
    )


if __name__ == "__main__":
    main()
