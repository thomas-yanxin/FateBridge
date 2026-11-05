"""Reduce frozen JPL ICRF directions with ERFA; imports no candidate code."""

import argparse
import csv
import hashlib
import io
import json
import math
from importlib.metadata import version
from pathlib import Path

import erfa
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--material",
    type=Path,
    default=Path(__file__).resolve().parents[2]
    / "tests/fixtures/jyotish-segment-reference.json",
)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
assert args.material.resolve() != args.output.resolve()
material = json.loads(args.material.read_text())
plan = material["request_plan"]
epoch = plan["center_tt"]
offsets = plan["offsets_days"]


def matrix(jd):
    eps = float(
        erfa.obl06(2451545.0, jd - 2451545.0)
        + erfa.nut06a(2451545.0, jd - 2451545.0)[1]
    )
    co, si = math.cos(eps), math.sin(eps)
    return np.array([[1, 0, 0], [0, co, si], [0, -si, co]]) @ erfa.pnm06a(
        2451545.0, jd - 2451545.0
    )


r = matrix(epoch)
dh = 0.001
rd = (matrix(epoch + dh) - matrix(epoch - dh)) / (2 * dh)
result = {
    "candidate_imports": False,
    "Swiss_imports": False,
    "reference_ephemeris": "NASA JPL Horizons, geocentric airless apparent ICRF direction",
    "reference_frame": "ERFA pnm06a true equator/equinox plus obl06+nut06a true obliquity",
    "packages": {"pyerfa": version("pyerfa"), "numpy": version("numpy")},
    "independent_synthetic_epochs": 1,
    "blind": False,
    "latitude_or_Lahiri_zero_point_certified": False,
    "candidate_rate_line_arcsec_per_day": 0.002,
    "reference_rate_agreement_line_arcsec_per_day": 0.0002,
    "rows": [],
}
for body in ["Sun", "Mercury", "Venus", "Mars"]:
    record = next(row for row in material["rows"] if row["body"] == body)
    text = material["raw_material"][record["raw_file"]]
    assert hashlib.sha256(text.encode()).hexdigest() == record["raw_sha256"]
    response = json.loads(text)
    assert "error" not in response, response.get("error")
    rawrows = list(
        csv.reader(
            io.StringIO(response["result"].split("$$SOE\n", 1)[1].split("$$EOE", 1)[0])
        )
    )
    assert len(rawrows) == len(offsets) == 11
    points = {}
    for offset, columns in zip(offsets, rawrows):
        ra, dec = map(math.radians, map(float, columns[5:7]))
        points[offset] = np.array(
            [math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)]
        )
    unit = points[0.0]
    p = r @ unit
    den = p[0] ** 2 + p[1] ** 2
    estimates = []
    for h in [0.125, 0.0625]:
        tangent = np.array(
            [
                math.fsum(
                    w * points[k * h][axis]
                    for k, w in zip([-3, -2, -1, 1, 2, 3], [-1, 9, -45, 45, -9, 1])
                )
                / (60 * h)
                for axis in range(3)
            ]
        )
        velocity = r @ tangent + rd @ unit
        rate = math.degrees((p[0] * velocity[1] - p[1] * velocity[0]) / den)
        estimates.append(rate)
    agreement = abs(estimates[0] - estimates[1]) * 3600
    result["rows"].append(
        {
            "body": body,
            "epoch_jd_tt": epoch,
            "raw_file": record["raw_file"],
            "raw_sha256": record["raw_sha256"],
            "reference_longitude_degrees": math.degrees(math.atan2(p[1], p[0])) % 360,
            "reference_rates_degrees_per_day": estimates,
            "reference_agreement_arcsec_per_day": agreement,
            "reference_converged": agreement <= 0.0002,
        }
    )
args.output.write_text(json.dumps(result, indent=2) + "\n")
for row in result["rows"]:
    print(
        row["body"],
        row["reference_rates_degrees_per_day"][-1],
        row["reference_agreement_arcsec_per_day"],
        flush=True,
    )
