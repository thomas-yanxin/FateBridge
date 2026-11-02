"""Collect all frozen TT solar-term crossings with Skyfield, independently.

Run with skyfield==1.53, jplephem==2.24 and numpy==2.2.6. This standalone
collector never imports FateBridge or uses its outputs as reference values.
"""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

PROTOCOL_SHA256 = "0d81e9f0f564c3c4d44a08a15d8fb0495ba33f053183c80580dd630e3c13a0dd"


def collect(kernel: Path, protocol_path: Path) -> dict:
    if hashlib.sha256(protocol_path.read_bytes()).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("The predeclared complete protocol must remain unchanged")
    protocol = json.loads(protocol_path.read_text())
    for package, version in (
        ("skyfield", "1.53"),
        ("jplephem", "2.24"),
        ("numpy", "2.2.6"),
    ):
        if importlib.metadata.version(package) != version:
            raise ValueError(f"Require {package}=={version}")
    kernel_bytes = kernel.read_bytes()
    if (
        hashlib.sha256(kernel_bytes).hexdigest() != protocol["kernel_sha256"]
        or hashlib.md5(kernel_bytes).hexdigest() != protocol["kernel_md5"]
    ):
        raise ValueError("Require the complete original JPL DE440 kernel")
    del kernel_bytes

    import numpy as np
    from skyfield import almanac_east_asia
    from skyfield.api import load, load_file

    ts = load.timescale(builtin=True)
    eph = load_file(str(kernel))
    function = almanac_east_asia.solar_terms(eph)
    identities = [(year, i) for year in range(1784, 2205) for i in range(24)]
    rows = []
    for offset in range(0, len(identities), 672):
        selected = identities[offset : offset + 672]
        years = np.array([y for y, _ in selected])
        indices = np.array([i for _, i in selected])
        months = indices // 2 + 1
        low_days = np.where(indices % 2 == 0, 1, 12)
        high_days = np.where(indices % 2 == 0, 12, 28)
        low = ts.tt(years, months, low_days).tt
        high = ts.tt(years, months, high_days).tt
        after_index = (19 + indices) % 24
        before_index = (after_index - 1) % 24
        if not (
            np.all(function(ts.tt_jd(low)) == before_index)
            and np.all(function(ts.tt_jd(high)) == after_index)
        ):
            raise ValueError("A fixed bracket does not contain its named transition")
        for _ in range(40):
            mid = (low + high) / 2
            values = function(ts.tt_jd(mid))
            if not np.all((values == before_index) | (values == after_index)):
                raise ValueError("Unexpected transition inside a fixed bracket")
            before = values == before_index
            low, high = np.where(before, mid, low), np.where(before, high, mid)
        for (year, i), lo, hi in zip(selected, low, high, strict=True):
            rows.append(
                {
                    "year": year,
                    "term_index": i,
                    "term": protocol["terms"][i],
                    "longitude_degrees": protocol["longitudes_degrees"][i],
                    "jd_tt": float((lo + hi) / 2),
                    "bracket_width_seconds": float((hi - lo) * 86400),
                }
            )
        print(f"Collected {len(rows)}/{len(identities)}", flush=True)
    eph.close()
    return {
        "protocol": protocol,
        "protocol_sha256": PROTOCOL_SHA256,
        "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("skyfield", "jplephem", "numpy", "sgp4", "certifi")
        },
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.check:
        raise FileExistsError("Do not replace an existing frozen reference")
    result = collect(args.kernel, args.protocol)
    if args.check:
        if json.loads(args.output.read_text()) != result:
            raise ValueError(
                "Independent recollection differs from the frozen reference"
            )
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"rows": len(result["rows"]), "checked": args.check}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
