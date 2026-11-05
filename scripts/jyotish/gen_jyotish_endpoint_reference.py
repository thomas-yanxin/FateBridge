"""Reproduce endpoint directions from sealed JPL text with independent ERFA.

Run in uv --no-project with pyerfa==2.0.1.5 and numpy==2.2.6. This optional
reference generator imports neither FateBridge nor Swiss Ephemeris. It never
uses the candidate's coordinates, errors or pass/fail results.
"""

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


def reduce_reference(material):
    wanted = {
        (birth["index"], body)
        for birth in material["birth_inputs"]
        for body in ("Sun", "Mercury", "Venus", "Mars")
    }
    actual = [(row["index"], row["body"]) for row in material["requests"]]
    if len(actual) != 8 or len(set(actual)) != 8 or set(actual) != wanted:
        raise ValueError("Endpoint reference coverage changed")
    rows = []
    for request in material["requests"]:
        raw = request["raw_response_utf8"]
        if hashlib.sha256(raw.encode()).hexdigest() != request["raw_sha256"]:
            raise ValueError("Raw JPL reference bytes changed")
        response = json.loads(raw)
        table = response["result"].split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
        values = list(csv.reader(io.StringIO(table)))
        if len(values) != 11:
            raise ValueError("Endpoint reference probes changed")
        ra, dec = map(math.radians, map(float, values[5][5:7]))
        unit = np.array(
            [math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)]
        )
        epoch = request["epoch_jd_tt"]
        true_equatorial = erfa.pnm06a(2451545.0, epoch - 2451545.0) @ unit
        rows.append(
            {
                "index": request["index"],
                "body": request["body"],
                "epoch_jd_tt": epoch,
                "frame": "ERFA IAU2006/2000A true equator/equinox of date",
                "true_equatorial_unit_direction": true_equatorial.tolist(),
                "raw_sha256": request["raw_sha256"],
            }
        )
    return {
        **material,
        "packages": {"pyerfa": version("pyerfa"), "numpy": version("numpy")},
        "expected_directions": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--material",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "tests/fixtures/jyotish-endpoint-reference.json",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.resolve() == args.material.resolve():
        parser.error("output must not overwrite the frozen source material")
    material = json.loads(args.material.read_text())
    result = reduce_reference(material)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"expected_directions": len(result["expected_directions"])}))
