"""Independent ERFA rotation/axis reference from a frozen input protocol.

Run in an isolated environment with pyerfa==2.0.1.5 and numpy==2.5.4.
No FateBridge or Swiss import is allowed in this reference process. Supplied
TT/UT1 pairs are inputs; this does not validate civil-time conversion or EOP.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import erfa


def axes(armc, latitude, obliquity):
    theta, phi, eps = map(math.radians, (armc, latitude, obliquity))
    zenith = [
        math.cos(phi) * math.cos(theta),
        math.cos(phi) * math.sin(theta),
        math.sin(phi),
    ]
    east = [-math.sin(theta), math.cos(theta), 0]
    pole = [0, -math.sin(eps), math.cos(eps)]

    def cross(a, b):
        return [
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        ]

    horizon = cross(pole, zenith)
    if sum(x * y for x, y in zip(horizon, east)) < 0:
        horizon = [-x for x in horizon]

    def longitude(point):
        return (
            math.degrees(
                math.atan2(
                    point[1] * math.cos(eps) + point[2] * math.sin(eps), point[0]
                )
            )
            % 360
        )

    return {"ascendant": longitude(horizon), "midheaven": longitude(cross(east, pole))}


def generate(protocol_path):
    protocol = json.loads(protocol_path.read_text())
    for name in ["pyerfa", "numpy"]:
        if importlib.metadata.version(name) != protocol[name + "_version"]:
            raise RuntimeError("Reference dependency differs from the frozen protocol")
    cases = []
    for epoch in protocol["epochs"]:
        ut1, tt = epoch["jd_ut1"], epoch["jd_tt"]
        gast = math.degrees(erfa.gst06a(2451545, ut1 - 2451545, 2451545, tt - 2451545))
        obliquity = math.degrees(
            erfa.obl06(2451545, tt - 2451545) + erfa.nut06a(2451545, tt - 2451545)[1]
        )
        cases.append(
            {
                **epoch,
                "gast_degrees": gast,
                "true_obliquity_degrees": obliquity,
                "locations": [
                    {
                        "latitude": latitude,
                        "longitude": longitude,
                        "axes": axes((gast + longitude) % 360, latitude, obliquity),
                    }
                    for latitude, longitude in protocol["locations"]
                ],
            }
        )
    if any(
        name == prefix or name.startswith(prefix + ".")
        for name in sys.modules
        for prefix in protocol["generator_forbidden_imports"]
    ):
        raise RuntimeError("Reference process imported a forbidden implementation")
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "protocol": protocol,
        "erfa_version": erfa.version.erfa_version,
        "sofa_version": erfa.version.sofa_version,
        "forbidden_implementation_imports": [],
        "cases": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = generate(args.protocol)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print("Independent epochs:", len(report["cases"]))
