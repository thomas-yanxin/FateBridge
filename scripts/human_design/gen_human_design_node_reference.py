"""Derive independent osculating nodes from JPL DE440 and ERFA, never FateBridge.

Explicit maintenance only; ordinary tests use the frozen raw states offline.
Run with uv --isolated --no-project --with pyerfa==2.0.1.5 --with jplephem==2.23.
The fixed epochs and 1 arcsecond comparison tolerance precede collection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

KERNEL_URL = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp"
KERNEL_MD5 = "c9d581bfd84209dbeee8b1583939b148"
TOLERANCE_ARCSECONDS = 1.0
ROOT = Path(__file__).resolve().parents[2]


def epochs() -> list[tuple[str, float]]:
    """Two fixed seasonal phases every ten years, plus range ends and J2000."""
    dates = ["1799-10-01T12:00:00", "2399-12-31T23:59:00"]
    dates.extend(
        f"{year}-{month_day}T12:00:00"
        for year in range(1800, 2400, 10)
        for month_day in ("01-01", "07-02")
    )
    origin = datetime(2000, 1, 1, 12)
    return sorted(
        (
            label + " TT",
            2451545.0
            + (datetime.fromisoformat(label) - origin).total_seconds() / 86400,
        )
        for label in dates
    )


def derive(kernel_path: Path) -> dict:
    import erfa
    import numpy as np
    from jplephem.spk import SPK

    raw = kernel_path.read_bytes()
    if hashlib.md5(raw).hexdigest() != KERNEL_MD5:
        raise ValueError("DE440 kernel does not match NASA's published checksum")
    rows = []
    with SPK.open(kernel_path) as kernel:

        def state(jd_tdb):
            moon = kernel[3, 301].compute_and_differentiate(
                2451545.0, jd_tdb - 2451545.0
            )
            earth = kernel[3, 399].compute_and_differentiate(
                2451545.0, jd_tdb - 2451545.0
            )
            return moon[0] - earth[0], moon[1] - earth[1]

        for label, jd_tt in epochs():
            tt2 = jd_tt - 2451545.0
            # Geocentre: the topocentric arguments are zero. No civil UTC model.
            tdb_minus_tt = float(erfa.dtdb(2451545.0, tt2, 0, 0, 0, 0))
            tdb1, tdb2 = erfa.tttdb(2451545.0, tt2, tdb_minus_tt)
            jd_tdb = float(tdb1 + tdb2)
            position, velocity = state(jd_tdb)
            light_time_seconds = float(np.linalg.norm(position)) / 299792.458
            retarded_jd_tdb = jd_tdb - light_time_seconds / 86400
            retarded_position, retarded_velocity = state(retarded_jd_tdb)
            matrix = erfa.ecm06(2451545.0, tt2)
            dpsi = float(erfa.nut06a(2451545.0, tt2)[0])

            def node(r, v):
                # Ascending direction k cross (r cross v), k = ecliptic north.
                normal = np.cross(matrix @ r, matrix @ v)
                return math.degrees(math.atan2(normal[0], -normal[1]) + dpsi) % 360

            rows.append(
                {
                    "label": label,
                    "jd_tt": jd_tt,
                    "jd_tdb": jd_tdb,
                    "tdb_minus_tt_seconds": tdb_minus_tt,
                    "geocentric_position_icrf_km": position.tolist(),
                    "geocentric_velocity_icrf_km_per_day": velocity.tolist(),
                    "light_time_seconds": light_time_seconds,
                    "retarded_jd_tdb": retarded_jd_tdb,
                    "retarded_geocentric_position_icrf_km": retarded_position.tolist(),
                    "retarded_geocentric_velocity_icrf_km_per_day": retarded_velocity.tolist(),
                    "icrf_to_mean_ecliptic_of_date_matrix": matrix.tolist(),
                    "nutation_longitude_radians": dpsi,
                    "geometric_node_longitude": node(position, velocity),
                    "node_longitude": node(retarded_position, retarded_velocity),
                }
            )
    return {
        "method_id": "independent_de440_erfa_osculating_node_v1",
        "source_url": KERNEL_URL,
        "source_checksum_url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/aa_checksums.txt",
        "kernel_md5": KERNEL_MD5,
        "kernel_sha256": hashlib.sha256(raw).hexdigest(),
        "kernel_size_bytes": len(raw),
        "derivation": "Geocentric Moon r/v from DE440; one lunar light-time iteration; ERFA IAU2006 mean ecliptic of date; ascending node k cross (r cross v); IAU2006/2000A longitude nutation. No Swiss Ephemeris or FateBridge import.",
        "frame_source_url": "https://github.com/liberfa/erfa/blob/master/src/ecm06.c",
        "generator_versions": {
            name: version(name) for name in ("jplephem", "pyerfa", "numpy")
        },
        "tolerance_arcseconds": TOLERANCE_ARCSECONDS,
        "epoch_policy": "1799 design-year witness, two fixed TT dates every ten years from 1800 through 2390, final supported birth year 2399; no epochs selected by backend agreement or disagreement.",
        "scope": "Selected independent osculating-node observations spanning the supported birth range. DE440 and ERFA differ from Swiss DE441/Vondrak conventions. This is not a continuous-year or fine-subdivision error bound, mean-node oracle, official Human Design node convention, or full chart validation.",
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "tests/fixtures/human-design-node-de440.json",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = derive(args.kernel)
    if args.check:
        saved = json.loads(args.output.read_text())
        saved.pop("retrieved_at", None)
        if saved != report:
            raise SystemExit(
                "Independent node reference differs from the specified kernel and generator"
            )
        print(f"Independent node reference matches {len(report['rows'])} fixed epochs")
    else:
        report["retrieved_at"] = datetime.now(timezone.utc).isoformat()
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(
            f"Saved {len(report['rows'])} independent node observations to {args.output}"
        )


if __name__ == "__main__":
    main()
