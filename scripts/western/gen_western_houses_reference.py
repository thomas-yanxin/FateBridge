"""Generate ERFA sky axes and independently compiled Astrolog cusp references.

This process must not import FateBridge or Swiss Ephemeris. Time pairs are
supplied inputs, not independently verified UTC/TT/UT1 conversions. Requires
pyerfa==2.0.1.5 and the executable built by build_astrolog_house_oracle.py.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import erfa
import numpy as np


def axes(armc, latitude, obliquity):
    theta, phi, eps = map(math.radians, (armc, latitude, obliquity))
    zenith = np.array(
        [
            math.cos(phi) * math.cos(theta),
            math.cos(phi) * math.sin(theta),
            math.sin(phi),
        ]
    )
    east = np.array([-math.sin(theta), math.cos(theta), 0])
    pole = np.array([0, -math.sin(eps), math.cos(eps)])
    horizon_crossing = np.cross(pole, zenith)
    if np.dot(horizon_crossing, east) < 0:
        horizon_crossing = -horizon_crossing
    meridian_crossing = np.cross(east, pole)

    def longitude(point):
        return (
            math.degrees(
                math.atan2(
                    point[1] * math.cos(eps) + point[2] * math.sin(eps), point[0]
                )
            )
            % 360
        )

    return {
        "ascendant": longitude(horizon_crossing),
        "midheaven": longitude(meridian_crossing),
    }


def generate(protocol_path, executable):
    if importlib.metadata.version("pyerfa") != "2.0.1.5" or np.__version__ != "2.5.4":
        raise RuntimeError("Pinned pyerfa 2.0.1.5 and NumPy 2.5.4 required")
    protocol = json.loads(protocol_path.read_text())
    rows = []
    for epoch in protocol["epochs"]:
        jd_tt, jd_ut1 = epoch["jd_tt"], epoch["jd_ut1"]
        gast = math.degrees(
            erfa.gst06a(2451545.0, jd_ut1 - 2451545.0, 2451545.0, jd_tt - 2451545.0)
        )
        eps = math.degrees(
            erfa.obl06(2451545.0, jd_tt - 2451545.0)
            + erfa.nut06a(2451545.0, jd_tt - 2451545.0)[1]
        )
        for latitude in protocol["latitudes"]:
            for longitude in protocol["longitudes"]:
                armc = (gast + longitude) % 360
                oracles = {}
                for code, system in protocol["systems"].items():
                    command = [
                        str(executable),
                        repr(armc),
                        repr(latitude),
                        repr(eps),
                        str(system),
                    ]
                    result = subprocess.run(
                        command, capture_output=True, text=True, check=True
                    )
                    lines = result.stdout.splitlines()
                    values = json.loads(
                        next(
                            line
                            for line in reversed(lines)
                            if line.startswith('{"ascendant"')
                        )
                    )
                    values["stdout_sha256"] = hashlib.sha256(
                        result.stdout.encode()
                    ).hexdigest()
                    values["warnings"] = [
                        line for line in lines if not line.startswith('{"ascendant"')
                    ]
                    oracles[code] = values
                rows.append(
                    {
                        "input": {
                            **epoch,
                            "latitude": latitude,
                            "longitude": longitude,
                        },
                        "armc": armc,
                        "true_obliquity": eps,
                        "erfa_vector_angles": axes(armc, latitude, eps),
                        "astrolog": oracles,
                    }
                )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "protocol": protocol,
        "pyerfa_version": importlib.metadata.version("pyerfa"),
        "numpy_version": np.__version__,
        "erfa_version": erfa.version.erfa_version,
        "sofa_version": erfa.version.sofa_version,
        "astrolog_build": json.loads(
            executable.with_name("house_oracle-build.json").read_text()
        ),
        "sources": [
            "https://www.iausofa.org/current-software",
            "https://github.com/liberfa/erfa",
            "https://github.com/CruiserOne/Astrolog/tree/v8.00",
        ],
        "scope": "Apparent equinox/true ecliptic of date, supplied TT/UT1, geodetic latitude; no polar motion, refraction or measured EOP",
        "limitations": [
            "Not independent time-scale validation",
            "Astrolog polar fallback and branch choices are retained, never relabelled as the requested system",
            "Placidus uses upstream fixed ten iterations, not a guaranteed converged oracle",
            "No planetary positions or empirical astrological validation",
        ],
        "cases": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--astrolog-executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = generate(args.protocol, args.astrolog_executable)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        "Generated",
        len(report["cases"]),
        "sky geometries; all 13 method outputs retained",
    )
