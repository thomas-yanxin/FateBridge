"""Freeze independent TT crossings using Skyfield's official solar-term API.

Run in an isolated environment with skyfield==1.53; never import FateBridge.
The full JPL DE440 file and its published checksum are verified before use.
This is implementation comparison, not UTC accuracy or reality prediction.
"""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Freeze a new reference; do not replace an existing one")
    if importlib.metadata.version("skyfield") != "1.53":
        raise ValueError("Use the independently pinned skyfield==1.53 collector")
    blob = args.kernel.read_bytes()
    if hashlib.md5(blob).hexdigest() != "c9d581bfd84209dbeee8b1583939b148":
        raise ValueError("Kernel differs from the JPL published DE440 checksum")
    protocol = json.loads(args.protocol.read_text())
    spans = {
        "fengshui_lichun_de440_tt_v1": (1800, 2200),
        "fengshui_lichun_de440_tt_v2": (1784, 2204),
    }
    if protocol["id"] not in spans:
        raise ValueError("Unsupported frozen collection protocol")

    import numpy as np
    from skyfield import almanac_east_asia
    from skyfield.api import load, load_file

    ts = load.timescale(builtin=True)
    eph = load_file(str(args.kernel))
    function = almanac_east_asia.solar_terms(eph)
    first, last = spans[protocol["id"]]
    years = np.arange(first, last + 1)
    low, high = ts.tt(years, 2, 1).tt, ts.tt(years, 2, 8).tt
    if not (
        np.all(function(ts.tt_jd(low)) == 20) and np.all(function(ts.tt_jd(high)) == 21)
    ):
        raise ValueError(
            "Every fixed bracket must contain exactly the Li Chun transition"
        )
    for _ in range(40):
        mid = (low + high) / 2
        before = function(ts.tt_jd(mid)) == 20
        low, high = np.where(before, mid, low), np.where(before, high, mid)
    result = {
        "protocol": protocol,
        "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "kernel_sha256": hashlib.sha256(blob).hexdigest(),
        "kernel_published_md5": hashlib.md5(blob).hexdigest(),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("skyfield", "jplephem", "numpy", "sgp4", "certifi")
        },
        "method": "skyfield.almanac_east_asia.solar_terms, geocentre, apparent ecliptic longitude of date, IAU2000B nutation, TT",
        "rows": [
            {
                "year": int(year),
                "jd_tt": float((lo + hi) / 2),
                "bracket_width_seconds": float((hi - lo) * 86400),
            }
            for year, lo, hi in zip(years, low, high, strict=True)
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {"rows": len(result["rows"]), "kernel_sha256": result["kernel_sha256"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
