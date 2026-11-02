"""Freeze independent rounded values before a portable projection implementation.

Retain every row of the earlier21600 high-precision reference. Supplement with
predeclared extreme/limb inputs using mpmath, never a FateBridge engine import.
"""

import argparse
import gzip
import hashlib
import json
import math
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "tests/fixtures/human-design-portable-projection-plan.json"


def derive():
    from mpmath import mp

    plan_raw = PLAN.read_bytes()
    plan = json.loads(plan_raw)
    old_path = ROOT / plan["preserved_geometry_reference"]
    old_raw = old_path.read_bytes()
    if (
        hashlib.sha256(old_raw).hexdigest()
        != plan["preserved_geometry_reference_sha256"]
    ):
        raise ValueError("Original21600row reference changed")
    if version("mpmath") != "1.3.0":
        raise ValueError("Independent arithmetic runtime changed")
    mp.dps = 1000
    source = json.loads(gzip.decompress(old_raw))
    keys = (
        "separation_radians",
        "nominal_solar_radius_radians",
        "projection_margin_radians",
    )
    rows = []
    for i, old in enumerate(source["rows"]):
        rounded = {k: float(old[k]).hex() for k in keys}
        # Stored80digit values cannot straddle a binary64 midpoint here.
        for k in keys:
            value = mp.mpf(old[k])
            assert (
                float(value - mp.mpf("1e-75")).hex()
                == rounded[k]
                == float(value + mp.mpf("1e-75")).hex()
            )
        rows.append(
            {
                "id": f"original-{i:05d}",
                "sun": old["sun_longitude_latitude_distance_au"],
                "target": old["target_longitude_latitude_distance_au"],
                "rounded_hex": rounded,
                "relation": (
                    "inside_nominal_disk"
                    if old["inside_nominal_solar_disk_projection"]
                    else "outside_nominal_disk"
                ),
            }
        )

    def exact(value):
        n, d = float(value).as_integer_ratio()
        return mp.mpf(n) / d

    def vector(value):
        lon, lat = [exact(v) * mp.pi / 180 for v in value[:2]]
        return mp.cos(lat) * mp.cos(lon), mp.cos(lat) * mp.sin(lon), mp.sin(lat)

    edges = []
    for case in plan["additional_inputs"]:
        sun, target = case["sun"], case["target"]
        a, z = vector(sun), vector(target)
        cross = (
            a[1] * z[2] - a[2] * z[1],
            a[2] * z[0] - a[0] * z[2],
            a[0] * z[1] - a[1] * z[0],
        )
        separation = mp.atan2(
            mp.sqrt(mp.fsum(x * x for x in cross)), mp.fsum(x * y for x, y in zip(a, z))
        )
        # Exact coordinate coincidences and poles have exactly zero distance.
        if (sun[:2] == target[:2]) or (sun[1] == target[1] and abs(sun[1]) == 90):
            separation = mp.mpf(0)
        radius = mp.asin(mp.mpf(695700000) / (exact(sun[2]) * 149597870700))
        margin = separation - radius
        relation = (
            "numerical_boundary_undetermined"
            if abs(margin) <= exact(1e-12)
            else "inside_nominal_disk" if margin < 0 else "outside_nominal_disk"
        )
        values = dict(zip(keys, (separation, radius, margin)))
        edges.append(
            {
                **case,
                "rounded_hex": {k: float(v).hex() for k, v in values.items()},
                "relation": relation,
            }
        )
    return {
        "method_id": plan["method_id"],
        "plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "original_reference_sha256": plan["preserved_geometry_reference_sha256"],
        "original_count": len(rows),
        "additional_count": len(edges),
        "mpmath_version": version("mpmath"),
        "edge_precision_decimal_digits": mp.dps,
        "scope": plan["scope"],
        "rows": rows + edges,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = derive()
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    with args.output.open("xb") as stream:
        stream.write(gzip.compress(raw, mtime=0))
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "original_count",
                    "additional_count",
                    "plan_sha256",
                    "generator_sha256",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
