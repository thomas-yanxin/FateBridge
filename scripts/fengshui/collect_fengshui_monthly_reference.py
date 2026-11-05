"""Collect TT crossings using Skyfield/JPL only, without importing FateBridge.

Run in a separate pinned reference environment. The protocol and one-second
gate must exist before collection; this script never chooses or edits a gate.
"""

import argparse
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

import numpy as np
from skyfield.almanac_east_asia import solar_terms
from skyfield.api import load, load_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text())
    kernel_digest = hashlib.sha256(args.kernel.read_bytes()).hexdigest()
    assert kernel_digest == protocol["kernel_sha256"]
    specs = [
        (year, row)
        for year in range(protocol["year_min"], protocol["year_max"] + 1)
        for row in protocol["civil_month_terms"]
    ]
    ts = load.timescale(builtin=True)
    eph = load_file(str(args.kernel))
    function = solar_terms(eph)
    years = np.array([y for y, row in specs])
    months = np.array([row["civil_month"] for y, row in specs])
    targets = np.array([row["longitude_degrees"] // 15 for y, row in specs])
    low = ts.tt(years, months, protocol["bracket_day_low"]).tt
    high = ts.tt(years, months, protocol["bracket_day_high"]).tt
    assert np.array_equal(function(ts.tt_jd(low)), targets - 1)
    assert np.array_equal(function(ts.tt_jd(high)), targets)
    for index in range(protocol["vector_bisections"]):
        middle = (low + high) / 2
        at_or_after = function(ts.tt_jd(middle)) == targets
        high = np.where(at_or_after, middle, high)
        low = np.where(at_or_after, low, middle)
        if (index + 1) % 10 == 0:
            print(f"{index + 1} vector bisections, {len(specs)} crossings", flush=True)
    assert not any(
        name == "fatebridge" or name.startswith("fatebridge.") for name in sys.modules
    )
    rows = [
        {
            "year": year,
            "term": row["term"],
            "longitude_degrees": row["longitude_degrees"],
            "jd_tt": float(value),
            "bracket_width_seconds": float(width * 86400),
        }
        for (year, row), value, width in zip(specs, (low + high) / 2, high - low)
    ]
    result = {
        "protocol": protocol,
        "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "kernel_sha256": kernel_digest,
        "kernel_md5": hashlib.md5(args.kernel.read_bytes()).hexdigest(),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("skyfield", "jplephem", "numpy", "sgp4", "certifi")
        },
        "method": "skyfield.almanac_east_asia.solar_terms, geocentric apparent ecliptic longitude of date, IAU2000B nutation, TT",
        "fatebridge_imported": False,
        "row_count": len(rows),
        "rows": rows,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps({"reference_count": len(rows), "output": str(args.output)}),
        flush=True,
    )


if __name__ == "__main__":
    main()
