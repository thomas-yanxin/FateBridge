"""Independent first-cycle roots from DE440 and a Horizons Chiron SPK.

Explicit reference maintenance only; no FateBridge or Swiss imports. The frozen
plan fixes physical TT epochs, targets, grids and angular tolerances beforehand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "tests/fixtures/human-design-cycles-plan.json"


def derive(planet_path: Path, chiron_path: Path, source_path: Path) -> dict:
    import numpy as np
    import spiceypy as spice
    from skyfield.api import load, load_file
    from skyfield.framelib import ecliptic_frame
    from skyfield.vectorlib import VectorFunction

    plan = json.loads(PLAN.read_text())
    if hashlib.md5(planet_path.read_bytes()).hexdigest() != plan["kernel_md5"]:
        raise ValueError("DE440 checksum mismatch")
    source = json.loads(source_path.read_text())
    if hashlib.sha256(chiron_path.read_bytes()).hexdigest() != source["kernel_sha256"]:
        raise ValueError("Chiron source hash mismatch")
    planets = load_file(str(planet_path))
    spice.furnsh(str(planet_path))
    spice.furnsh(str(chiron_path))

    class ChironVector(VectorFunction):
        center = 0
        target = int(source["spk_file_id"])

        def _at(self, t):
            # CSPICE supports Horizons type-21 kernels; jplephem does not.
            # Geometric ICRF states only. Skyfield applies light time and its
            # usual apparent-frame corrections against the DE440 observer.
            et = (np.asarray(t.tdb) - 2451545.0) * 86400.0
            states = np.array(
                [
                    spice.spkgeo(self.target, float(x), "J2000", 0)[0]
                    for x in et.reshape(-1)
                ]
            )
            pos = (states[:, :3] / 149597870.7).T.reshape((3,) + et.shape)
            vel = (states[:, 3:] * 86400.0 / 149597870.7).T.reshape((3,) + et.shape)
            return pos, vel, None, None

    ts = load.timescale(builtin=True)
    earth = planets[399]
    records = []
    for birth in plan["birth_epochs"]:
        jd = birth["jd_tt"]
        stop = jd + plan["search_horizon_days"]
        epochs = np.append(
            np.arange(jd, stop, plan["independent_grid_step_days"]), stop
        )
        for body, target in plan["skyfield_targets"].items():
            vector = ChironVector() if body == "Chiron" else planets[target]

            def longitude(t):
                pos = earth.at(ts.tt_jd(t)).observe(vector).apparent()
                return pos.frame_latlon(ecliptic_frame)[1].degrees

            values = longitude(epochs)
            unwrapped = np.degrees(np.unwrap(np.radians(values))) - values[0]
            arc = plan["target_arc_degrees"][body]
            residuals = unwrapped - arc
            indexes = np.where(residuals[:-1] * residuals[1:] < 0)[0]
            lo, hi = epochs[indexes].copy(), epochs[indexes + 1].copy()
            left_values = values[indexes].copy()
            left_residual = residuals[indexes].copy()
            original_lo, original_hi = lo.copy(), hi.copy()
            for _ in range(36):
                mid = lo + (hi - lo) / 2
                middle_values = longitude(mid)
                middle_residual = (
                    left_residual + (middle_values - left_values + 180) % 360 - 180
                )
                keep_left = (middle_residual > 0) == (left_residual > 0)
                lo = np.where(keep_left, mid, lo)
                hi = np.where(keep_left, hi, mid)
                left_values = np.where(keep_left, middle_values, left_values)
                left_residual = np.where(keep_left, middle_residual, left_residual)
            roots = lo + (hi - lo) / 2
            root_values = longitude(roots)
            records.append(
                {
                    "birth": birth,
                    "body": body,
                    "target_id": target,
                    "natal_longitude": float(values[0]),
                    "target_arc_degrees": arc,
                    "grid_count": len(epochs),
                    "grid_longitudes_float64_sha256": hashlib.sha256(
                        np.asarray(values, dtype="<f8").tobytes()
                    ).hexdigest(),
                    "contacts": [
                        {
                            "jd_tt": float(t),
                            "longitude": float(v),
                            "motion": (
                                "direct"
                                if residuals[indexes[i] + 1] > residuals[indexes[i]]
                                else "retrograde"
                            ),
                            "initial_bracket_jd_tt": [
                                float(original_lo[i]),
                                float(original_hi[i]),
                            ],
                            "bracket_width_seconds": float((hi[i] - lo[i]) * 86400),
                        }
                        for i, (t, v) in enumerate(zip(roots, root_values))
                    ],
                }
            )
    planets.close()
    spice.kclear()
    return {
        "method_id": "independent_de440_horizons_spk_cycles_v1",
        "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "versions": {
            name: version(name)
            for name in ("skyfield", "jplephem", "numpy", "spiceypy")
        },
        "planet_kernel_sha256": hashlib.sha256(planet_path.read_bytes()).hexdigest(),
        "chiron_source": source,
        "scope": "Three fixed TT births and all observed first-cycle contact brackets on an independent one-day grid; not a proof of continuous completeness, exact UTC labels, source-priority conventions or real-world predictions. Chiron uses CSPICE geometric states from a separately generated contemporary JPL orbit solution and Skyfield apparent corrections.",
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planet-kernel", type=Path, required=True)
    parser.add_argument("--chiron-kernel", type=Path, required=True)
    parser.add_argument("--chiron-source", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "tests/fixtures/human-design-cycles-reference.json",
    )
    args = parser.parse_args()
    report = derive(args.planet_kernel, args.chiron_kernel, args.chiron_source)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "records": len(report["records"]),
                "contacts": sum(len(r["contacts"]) for r in report["records"]),
                "versions": report["versions"],
            }
        )
    )


if __name__ == "__main__":
    main()
