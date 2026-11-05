"""Refine all original 4872 TT roots using an independent two-part search.

Keep the original month brackets, official Skyfield solar_terms function and
kernel. Existing references and their acceptance results are never replaced.
"""

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), "Do not overwrite an existing reference"
    root = Path(__file__).resolve().parents[2]
    protocol = json.loads(args.protocol.read_text())
    assert (
        sha(args.protocol) == args.protocol.with_suffix(".sha256").read_text().strip()
    )
    assert sha(Path(__file__)) == protocol["collector_sha256"]
    assert all(sha(root / p) == value for p, value in protocol["inputs"].items())
    versions = {name: importlib.metadata.version(name) for name in protocol["versions"]}
    assert versions == protocol["versions"]
    import numpy as np
    from skyfield import almanac_east_asia
    from skyfield.api import load, load_file

    ts = load.timescale(builtin=True)
    eph = load_file(str(root / protocol["kernel"]))
    function = almanac_east_asia.solar_terms(eph)
    slots = [
        (y, m, half)
        for y in range(1899, 2102)
        for m in range(1, 13)
        for half in range(2)
    ]
    years = np.array([s[0] for s in slots])
    months = np.array([s[1] for s in slots])
    halves = np.array([s[2] for s in slots])
    indices = (months * 2 + halves + 17) % 24
    # The anchors are exact calendar midnights, independent of both the old
    # rounded reference roots and every application result/failure location.
    base = ts.tt(years, months, np.where(halves == 0, 1, 12)).tt
    high_jd = ts.tt(years, months, np.where(halves == 0, 12, 28)).tt
    low = np.zeros(len(slots))
    high = high_jd - base
    assert np.all(function(ts.tt_jd(base, low)) == (indices - 1) % 24)
    assert np.all(function(ts.tt_jd(base, high)) == indices)
    for iteration in range(protocol["iterations"]):
        mid = (low + high) / 2
        before = function(ts.tt_jd(base, mid)) == (indices - 1) % 24
        low = np.where(before, mid, low)
        high = np.where(before, high, mid)
        if (iteration + 1) % 8 == 0:
            print(
                json.dumps(
                    {
                        "iterations": iteration + 1,
                        "max_width_seconds": float(np.max(high - low) * 86400),
                    }
                ),
                flush=True,
            )
    assert np.all(function(ts.tt_jd(base, low)) == (indices - 1) % 24)
    assert np.all(function(ts.tt_jd(base, high)) == indices)
    old = json.loads((root / protocol["original_reference"]).read_text())["rows"]
    rows = []
    for i, ((year, _, _), index, anchor, a, b, retained) in enumerate(
        zip(slots, indices, base, low, high, old, strict=True)
    ):
        name = almanac_east_asia.SOLAR_TERMS_ZHS[int(index)]
        assert (year, name) == (retained["year"], retained["name"])
        midpoint = (a + b) / 2
        rows.append(
            {
                "index": i,
                "year": year,
                "name": name,
                "solar_longitude_degrees": int(index) * 15,
                "tt_parts": [float(anchor), float(midpoint)],
                "tt_bracket_parts": [
                    [float(anchor), float(a)],
                    [float(anchor), float(b)],
                ],
                "numerical_bracket_seconds": float((b - a) * 86400),
                "original_scalar_jd_tt": retained["jd_tt"],
                "original_minus_split_midpoint_seconds": float(
                    ((retained["jd_tt"] - anchor) - midpoint) * 86400
                ),
            }
        )
    assert len(rows) == len(old) == 4872
    assert all(sha(root / p) == value for p, value in protocol["inputs"].items())
    assert not any(
        k == "fatebridge" or k.startswith("fatebridge.") for k in sys.modules
    )
    result = {
        "method_id": "independent_split_tt_solar_terms_v1",
        "protocol_sha256": sha(args.protocol),
        "versions": versions,
        "rows": rows,
        "row_count": len(rows),
        "max_numerical_bracket_seconds": max(
            r["numerical_bracket_seconds"] for r in rows
        ),
        "max_original_scalar_displacement_seconds": max(
            abs(r["original_minus_split_midpoint_seconds"]) for r in rows
        ),
        "original_references_replaced": False,
        "original_failure_gates_superseded": False,
        "numerical_bracket_is_physical_error_bound": False,
        "new_independent_observation_credit": 0,
        "scope": "Same exposed terms and same astronomical model; two-part numerical refinement only. No kernel/frame/TDB/aberration changes, fitting, new observations or physical clock precision certification.",
    }
    args.output.write_bytes(
        gzip.compress(
            (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(
        json.dumps(
            {
                "rows": len(rows),
                "max_bracket_seconds": result["max_numerical_bracket_seconds"],
                "max_scalar_displacement_seconds": result[
                    "max_original_scalar_displacement_seconds"
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
