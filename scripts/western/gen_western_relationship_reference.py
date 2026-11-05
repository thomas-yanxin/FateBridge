"""Freeze independent spherical midpoints with GeographicLib 2.1.

Run: uv run --locked --extra dev --with geographiclib==2.1 python scripts/western/gen_western_relationship_reference.py
Production code and ordinary tests do not depend on GeographicLib. The 1e-9
degree tolerance is fixed before collecting these samples. No FateBridge
calculation is imported to manufacture a reference answer.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import geographiclib
from geographiclib.geodesic import Geodesic

ROOT = Path(__file__).resolve().parents[2]
TOLERANCE_DEGREES = 1e-9


def main():
    if geographiclib.__version__ != "2.1":
        raise RuntimeError("Use the pinned independent oracle GeographicLib 2.1")
    inputs = [
        [longitude, latitude, (longitude + 137 + 180) % 360 - 180, -latitude / 2 + 11]
        for longitude in (-179, -120, -45, 0, 45, 120, 179)
        for latitude in (-65, -30, 0, 30, 65)
    ] + [
        [179, 10, -179, 10],
        [-179, -10, 179, 20],
        [0, 40, 180, 40],
        [0, -40, -180, -40],
        [0, 10, 180, -9.9],
        [0, 10, -180, -10.1],
        [0, 10, 179.9999, -10],
        [175, 89.9, -4.9, -89.8],
        [30, 90, -50, 80],
        [-180, 0, 180, 0],
        [60, 30, 60, 30],
        [0, 0, 90, 0],
    ]
    geodesic = Geodesic(6371000, 0)  # sphere, deliberately not WGS84 flattening
    rows = []
    for lon1, lat1, lon2, lat2 in inputs:
        inverse = geodesic.Inverse(lat1, lon1, lat2, lon2)
        midpoint = geodesic.Direct(lat1, lon1, inverse["azi1"], inverse["s12"] / 2)
        rows.append(
            {
                "input_longitudes_latitudes": [lon1, lat1, lon2, lat2],
                "expected_longitude": midpoint["lon2"],
                "expected_latitude": midpoint["lat2"],
                "inverse": inverse,
                "direct_half_distance": midpoint,
            }
        )
    report = {
        "source_url": "https://geographiclib.sourceforge.io/html/python/code.html",
        "oracle": "GeographicLib Python 2.1 inverse geodesic followed by half-distance direct geodesic",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "sphere_radius_m": 6371000,
        "flattening": 0,
        "tolerance_degrees": TOLERANCE_DEGREES,
        "scope": "47 unique spherical geographic midpoint cases; not WGS84, native astrological coordinates, or an original-text interpretation oracle",
        "cases": rows,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    target = ROOT / "tests/fixtures/western-geographiclib-midpoints.json"
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(f"Frozen {len(rows)} independent spherical midpoint cases")


if __name__ == "__main__":
    main()
