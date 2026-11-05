"""Derive a J2000 geometry reference from sealed Horizons raw vectors and ERFA.

No FateBridge or Swiss imports; no new epochs or new independent dynamics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from importlib.metadata import version
from pathlib import Path

import erfa  # type: ignore[import-untyped]  # pyerfa does not ship typing metadata.
import numpy as np

SOURCE_SHA256 = "3fbaab7a1b45436e212fd37300b8291acc80320cc177192459d04c6194ffe52b"
TARGETS = {"Mercury": 1, "Venus": 2, "Mars": 4, "Jupiter": 5, "Saturn": 6}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    if a.input.resolve() == a.output.resolve():
        p.error("output must not overwrite the sealed input")
    raw = a.input.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA256
    data = json.loads(raw)
    rotation = erfa.rx(erfa.obl80(2451545.0, 0.0), erfa.bp00(2451545.0, 0.0)[0])
    rows = []
    for body, target in TARGETS.items():
        ref = next(r for r in data["references"] if r["body"] == body)
        assert ref["target_id"] == target
        result = ref["response"]["result"]
        assert hashlib.sha256(result.encode()).hexdigest() == ref["result_sha256"]
        assert "{source: DE441}" in result
        assert ref["parameters"]["TIME_TYPE"] == "'TT'"
        assert ref["parameters"]["VEC_CORR"] == "'NONE'"
        table = list(
            csv.reader(io.StringIO(result.split("$$SOE\n")[1].split("$$EOE")[0]))
        )
        line = next(r for r in table if float(r[0]) == 2451545.0)
        vector = np.array([float(v) for v in line[2:5]])
        old = next(r for r in ref["rows"] if r["jd_tt"] == 2451545.0)
        assert vector.tolist() == old["position_au"]
        transformed = rotation @ vector
        rows.append(
            {
                "body": body,
                "target_id": target,
                "epoch_jd_tt": 2451545.0,
                "raw_geocentric_ICRF_vector_au": vector.tolist(),
                "ecliptic_unit_vector": (
                    transformed / np.linalg.norm(transformed)
                ).tolist(),
                "longitude": math.degrees(math.atan2(transformed[1], transformed[0]))
                % 360,
                "latitude": math.degrees(
                    math.atan2(transformed[2], math.hypot(*transformed[:2]))
                ),
                "raw_result_sha256": ref["result_sha256"],
            }
        )
    assert not any(n == "swisseph" or n.startswith("fatebridge") for n in sys.modules)
    output = {
        "source_sha256": SOURCE_SHA256,
        "source": data["source"],
        "packages": {"pyerfa": version("pyerfa"), "numpy": version("numpy")},
        "frame": "mean_dynamical_ecliptic_equinox_J2000",
        "rotation": "ERFA bp00 ICRS frame bias then obl80 J2000 mean obliquity",
        "position_line_arcsec": 0.02,
        "rows": rows,
        "scope": "Five existing raw geometric vectors at one already exposed J2000 TT. Independent reduction, shared DE441 dynamics; not new observations, civil-clock, Lahiri or prediction acceptance.",
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(output, indent=2) + "\n")
    print("Derived five J2000 rows without FateBridge or Swiss imports")


if __name__ == "__main__":
    main()
