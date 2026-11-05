"""Reproduce Moon and ordinary Jupiter/Saturn barycentre endpoint references.

Run with independent pyerfa==2.0.1.5 and numpy==2.2.6. No candidate or Swiss
imports. Body-centre source errors are retained in the development evidence;
they are not these ordinary native planetary-system barycentre targets.
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
    targets = {"Moon": 301, "Jupiter": 5, "Saturn": 6}
    wanted = {(i, b) for i in (0, 1) for b in targets}
    actual = [(r["index"], r["body"]) for r in material["requests"]]
    if len(actual) != 6 or set(actual) != wanted:
        raise ValueError("Extended endpoint reference coverage changed")
    rows = []
    for request in material["requests"]:
        if request["parameters"]["COMMAND"] != f"'{targets[request['body']]}'":
            raise ValueError("Physical target identity changed")
        raw = request["raw_response_utf8"]
        if hashlib.sha256(raw.encode()).hexdigest() != request["raw_sha256"]:
            raise ValueError("Raw JPL reference changed")
        response = json.loads(raw)
        table = response["result"].split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
        values = list(csv.reader(io.StringIO(table)))
        if len(values) != 11:
            raise ValueError("Declared reference probes changed")
        ra, dec = map(math.radians, map(float, values[5][5:7]))
        unit = np.array(
            [math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)]
        )
        epoch = request["epoch_jd_tt"]
        reduced = erfa.pnm06a(2451545.0, epoch - 2451545.0) @ unit
        rows.append(
            dict(
                index=request["index"],
                body=request["body"],
                epoch_jd_tt=epoch,
                true_equatorial_unit_direction=reduced.tolist(),
                raw_sha256=request["raw_sha256"],
            )
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
        / "tests/fixtures/jyotish-endpoint-extended-reference.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.material.resolve() == args.output.resolve():
        parser.error("output must not overwrite frozen source material")
    result = reduce_reference(json.loads(args.material.read_text()))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"expected_directions": len(result["expected_directions"])}))
