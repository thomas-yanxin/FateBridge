"""Independent high-precision geometry on the entire frozen seasonal cohort.

This is an arithmetic reference, not another astronomy or visibility oracle.
No FateBridge, Swiss, native producer, current chart or online data import.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "tests/fixtures/human-design-solar-projection-plan.json"
OUTPUT = ROOT / "tests/fixtures/human-design-solar-projection-reference.json.gz"


def derive() -> dict:
    from mpmath import mp

    plan = json.loads(PLAN.read_text())
    source_path = ROOT / plan["source_reference"]
    source_raw = source_path.read_bytes()
    if hashlib.sha256(source_raw).hexdigest() != plan["source_reference_sha256"]:
        raise ValueError("Original complete seasonal input reference changed")
    if version("mpmath") != plan["oracle"]["version"]:
        raise ValueError("Independent arithmetic runtime changed")
    mp.dps = plan["oracle"]["decimal_precision"]
    source = json.loads(source_raw)

    def exact(value: float):
        numerator, denominator = value.as_integer_ratio()
        return mp.mpf(numerator) / denominator

    def vector(longitude, latitude):
        lon, lat = exact(longitude) * mp.pi / 180, exact(latitude) * mp.pi / 180
        return mp.cos(lat) * mp.cos(lon), mp.cos(lat) * mp.sin(lon), mp.sin(lat)

    rows = []
    for pair in source["pairs"]:
        for side in ("personality", "design"):
            positions = pair[side]["positions"]
            sun = positions["Sun"]
            solar = [sun[k] for k in ("longitude", "latitude", "distance_au")]
            solar_vector = vector(*solar[:2])
            q = plan["constants"]["nominal_solar_radius_m"] / (
                exact(solar[2]) * plan["constants"]["astronomical_unit_m"]
            )
            radius = mp.asin(q)
            for body, position in positions.items():
                if body == "Sun":
                    continue
                target = [position[k] for k in ("longitude", "latitude", "distance_au")]
                direction = vector(*target[:2])
                a, z = solar_vector, direction
                cross = (
                    a[1] * z[2] - a[2] * z[1],
                    a[2] * z[0] - a[0] * z[2],
                    a[0] * z[1] - a[1] * z[0],
                )
                separation = mp.atan2(
                    mp.sqrt(mp.fsum(x * x for x in cross)),
                    mp.fsum(x * y for x, y in zip(a, z, strict=True)),
                )
                rows.append(
                    {
                        "label": pair["label"],
                        "side": side,
                        "body": body,
                        "jd_tt": pair[side]["jd_tt"],
                        "sun_longitude_latitude_distance_au": solar,
                        "target_longitude_latitude_distance_au": target,
                        "separation_radians": mp.nstr(separation, 80),
                        "nominal_solar_radius_radians": mp.nstr(radius, 80),
                        "projection_margin_radians": mp.nstr(separation - radius, 80),
                        "inside_nominal_solar_disk_projection": bool(
                            separation < radius
                        ),
                        "more_distant_than_sun_in_supplied_coordinates": target[2]
                        > solar[2],
                    }
                )
    if len(rows) != plan["case_count"]:
        raise ValueError("Not all declared geometry inputs were retained")
    return {
        "method_id": plan["method_id"],
        "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "source_reference_sha256": plan["source_reference_sha256"],
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "mpmath_version": version("mpmath"),
        "precision_decimal_digits": mp.dps,
        "case_count": len(rows),
        "scope": "High-precision geometry on identical binary input coordinates; not independent native positions, real occultations, visibility or predictive evidence.",
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(derive(), ensure_ascii=False, indent=2) + "\n").encode()
    compressed = gzip.compress(raw, mtime=0)
    if args.check:
        if args.output.read_bytes() != compressed:
            raise SystemExit("Independent geometric reference bytes differ")
    else:
        args.output.write_bytes(compressed)
    print(json.dumps({"cases": 21600, "checked": args.check}))


if __name__ == "__main__":
    main()
