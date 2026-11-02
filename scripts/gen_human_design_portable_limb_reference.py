"""Supplementary post-prototype probes at the unchanged classification cuts.

Use the independent equatorial angular-distance formula, not production vector
or interval code. All36 formula-selected rows remain; no observed-result filter.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path


def derive():
    from mpmath import mp

    mp.dps = 300

    def exact(v):
        n, d = v.as_integer_ratio()
        return mp.mpf(n) / d

    resolution = exact(1e-12)
    rows = []
    for distance in (0.01, 0.1, 1.0, 10.0):
        radius = mp.asin(mp.mpf(695700000) / (exact(distance) * 149597870700))
        for sign in (-1, 0, 1):
            center = float((radius + sign * resolution) * 180 / mp.pi)
            for offset, longitude in (
                (-1, math.nextafter(center, -math.inf)),
                (0, center),
                (1, math.nextafter(center, math.inf)),
            ):
                separation = exact(longitude) * mp.pi / 180
                margin = separation - radius
                rows.append(
                    {
                        "id": f"distance-{distance}-cut-{sign}-neighbor-{offset}",
                        "sun": [0.0, 0.0, distance],
                        "target": [longitude, 0.0, distance * 2],
                        "rounded_hex": {
                            k: float(v).hex()
                            for k, v in zip(
                                (
                                    "separation_radians",
                                    "nominal_solar_radius_radians",
                                    "projection_margin_radians",
                                ),
                                (separation, radius, margin),
                            )
                        },
                        "relation": (
                            "numerical_boundary_undetermined"
                            if abs(margin) <= resolution
                            else (
                                "inside_nominal_disk"
                                if margin < 0
                                else "outside_nominal_disk"
                            )
                        ),
                    }
                )
    return {
        "method_id": "independent_equatorial_limb_neighbors_v1",
        "selection": "After-prototype supplementary probes: all4distances x3cuts(-resolution,0,+resolution) x3neighboring binary64 longitudes, without output-based selection. This is not the pre-implementation21627cohort.",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "mpmath_decimal_digits": mp.dps,
        "case_count": len(rows),
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = (json.dumps(derive(), indent=2) + "\n").encode()
    with args.output.open("xb") as stream:
        stream.write(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
