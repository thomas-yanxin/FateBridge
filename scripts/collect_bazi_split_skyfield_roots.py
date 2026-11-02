"""Collect complete two-part TT controls with official Skyfield, no app imports."""

import argparse
import gzip
import hashlib
import importlib.metadata
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "docs/validation/bazi-root-clock-factorization-v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    protocol_path = STUDY / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    assert (
        sha(protocol_path) == protocol_path.with_suffix(".sha256").read_text().strip()
    )
    binding = json.loads((STUDY / "collector-binding.json").read_text())
    assert sha(Path(__file__)) == binding["collector_sha256"]
    assert sha(protocol_path) == binding["protocol_sha256"]
    assert all(sha(ROOT / n) == h for n, h in protocol["files"].items())
    versions = {
        n: importlib.metadata.version(n) for n in ("skyfield", "jplephem", "numpy")
    }
    assert versions == {"skyfield": "1.53", "jplephem": "2.24", "numpy": "2.5.4"}
    import numpy as np
    from skyfield import almanac_east_asia, timelib
    from skyfield.api import load, load_file

    eph = load_file(str(ROOT / "ephe/solar-de440.bsp"))
    ts = load.timescale(builtin=True)
    function = almanac_east_asia.solar_terms(eph)
    slots = [
        (y, m, h) for y in range(1899, 2102) for m in range(1, 13) for h in range(2)
    ]
    years, months, halves = (np.array([s[i] for s in slots]) for i in range(3))
    indices = (months * 2 + halves + 17) % 24
    first = ts.tt(years, months, np.where(halves == 0, 1, 12))
    last = ts.tt(years, months, np.where(halves == 0, 12, 28))
    base = np.floor(first.whole)
    low = first.whole - base + first.tt_fraction
    high = last.whole - base + last.tt_fraction
    assert np.all(function(ts.tt_jd(base, low)) == (indices - 1) % 24)
    assert np.all(function(ts.tt_jd(base, high)) == indices)
    for _ in range(protocol["bisections"]):
        middle = (low + high) / 2
        before = function(ts.tt_jd(base, middle)) == (indices - 1) % 24
        low, high = np.where(before, middle, low), np.where(before, high, middle)
    left, right = function(ts.tt_jd(base, low)), function(ts.tt_jd(base, high))
    assert np.all(left == (indices - 1) % 24) and np.all(right == indices)
    assert np.all((high - low) * 86400 < 0.000001)
    rows = [
        {
            "year": y,
            "name": almanac_east_asia.SOLAR_TERMS_ZHS[int(i)],
            "solar_longitude_degrees": int(i) * 15,
            "tt_parts": [float(b), float((lo + hi) / 2)],
            "tt_bracket_parts": [[float(b), float(lo)], [float(b), float(hi)]],
            "bracket_width_seconds": float((hi - lo) * 86400),
            "endpoint_indices": [int(a), int(z)],
        }
        for (y, _, _), i, b, lo, hi, a, z in zip(
            slots, indices, base, low, high, left, right, strict=True
        )
    ]
    assert len(rows) == 4872
    assert not any(
        k == "fatebridge" or k.startswith("fatebridge.") for k in sys.modules
    )
    assert all(sha(ROOT / n) == h for n, h in protocol["files"].items())
    data = dict(
        rows=rows,
        row_count=len(rows),
        versions=versions,
        protocol_sha256=sha(protocol_path),
        collector_sha256=sha(Path(__file__)),
        official_function_source_sha256={
            "solar_terms": hashlib.sha256(
                inspect.getsource(almanac_east_asia.solar_terms).encode()
            ).hexdigest(),
            "tt_jd": hashlib.sha256(
                inspect.getsource(timelib.Timescale.tt_jd).encode()
            ).hexdigest(),
        },
        no_application_imports=True,
        original_references_unchanged=True,
        numeric_bracket_is_physical_error_bound=False,
        new_independent_observation_credit=0,
        original_gates_superseded=False,
        production_changes=0,
        full_goal_complete=False,
    )
    args.output.write_bytes(
        gzip.compress(
            (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode(), mtime=0
        )
    )
    args.output.with_suffix(".sha256").write_text(sha(args.output) + "\n")
    print(
        json.dumps(
            {
                "rows": len(rows),
                "sha256": sha(args.output),
                "maximum_bracket_seconds": max(
                    r["bracket_width_seconds"] for r in rows
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
