"""Freeze complete Skyfield/DE440 TT roots without importing FateBridge.

The independent environment needs the exact REFERENCE_VERSIONS below. The
packet contains its producer source, so later script moves do not invalidate
the identity of the algorithm that generated an existing frozen reference.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from importlib import metadata
from pathlib import Path

import numpy as np
from skyfield.almanac_east_asia import SOLAR_TERMS_ZHS, solar_terms
from skyfield.api import load, load_file

REFERENCE_VERSIONS = {
    "skyfield": "1.53",
    "jplephem": "2.24",
    "numpy": "2.5.4",
    "sgp4": "2.27",
    "certifi": "2026.10.18",
}
KERNEL_SHA256 = "a4ce9bf9b3282becc9f4b2ac3cebe03a2ae7599981aabd7265fd8482fff7c4b5"
KERNEL_MD5 = "c9d581bfd84209dbeee8b1583939b148"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Frozen references are never overwritten; choose a new output")
    versions = {name: metadata.version(name) for name in REFERENCE_VERSIONS}
    if versions != REFERENCE_VERSIONS:
        raise ValueError("Use the declared independent reference versions")
    if any(
        name == "fatebridge" or name.startswith("fatebridge.") for name in sys.modules
    ):
        raise ValueError("Reference collection must not import the candidate")
    with args.kernel.open("rb") as stream:
        kernel_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    with args.kernel.open("rb") as stream:
        kernel_md5 = hashlib.file_digest(stream, "md5").hexdigest()
    if kernel_sha != KERNEL_SHA256 or kernel_md5 != KERNEL_MD5:
        raise ValueError("The original published full DE440 kernel is required")

    first, last = 1699, 2301
    ts = load.timescale(builtin=True)
    ephemeris = load_file(str(args.kernel))
    classify = solar_terms(ephemeris)
    years = np.repeat(np.arange(first, last + 1), 24)
    indices = np.tile(np.arange(24), last - first + 1)
    months = indices // 2 + 1
    targets = (indices + 19) % 24
    low = ts.tt(years, months, np.where(indices % 2 == 0, 1, 12)).tt
    high = ts.tt(years, months, np.where(indices % 2 == 0, 12, 28)).tt
    if not (
        np.all(classify(ts.tt_jd(low)) == (targets - 1) % 24)
        and np.all(classify(ts.tt_jd(high)) == targets)
    ):
        raise ValueError("Every fixed calendar bracket must contain its named term")
    for _ in range(40):
        middle = (low + high) / 2
        after = classify(ts.tt_jd(middle)) == targets
        high = np.where(after, middle, high)
        low = np.where(after, low, middle)
    middle = (low + high) / 2
    rows = [
        {
            "year": int(year),
            "index": int(index),
            "name": SOLAR_TERMS_ZHS[int(target)],
            "jd_tt": float(value),
            "bracket_tt": [float(a), float(b)],
        }
        for year, index, target, value, a, b in zip(
            years, indices, targets, middle, low, high
        )
    ]
    if len(rows) != 14472 or max((high - low) * 86400) > 0.001:
        raise ValueError("The complete cohort and original bracket bound are required")
    producer = Path(__file__).read_text(encoding="utf-8")
    producer_sha256 = hashlib.sha256(producer.encode("utf-8")).hexdigest()
    modules = [
        "skyfield.almanac_east_asia",
        "skyfield.positionlib",
        "skyfield.precessionlib",
        "skyfield.nutationlib",
        "jplephem",
        "numpy",
    ]
    module_sha256 = {}
    for name in modules:
        filename = sys.modules[name].__file__
        if filename is None:
            raise ValueError(f"The reference module has no source identity: {name}")
        module_sha256[name] = hashlib.sha256(Path(filename).read_bytes()).hexdigest()
    packet = {
        "schema": "solar_tt_de440_skyfield153_v1",
        "source": {
            "kernel_url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp",
            "checksum_url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/aa_checksums.txt",
            "kernel_md5": kernel_md5,
            "kernel_sha256": kernel_sha,
            "software_versions": versions,
            "module_sha256": module_sha256,
            "producer_source": producer,
            "producer_sha256": producer_sha256,
            "method": "Unmodified official Skyfield solar_terms; geocentric apparent ecliptic longitude of date, IAU2000B; TT only",
            "documentation_url": "https://rhodesmill.org/skyfield/almanac.html#solar-terms",
            "bracket_policy": "Fixed TT month-days1..12 and12..28; assert both named states;40 vectorized scalar-JD bisections",
            "maximum_bracket_seconds": 0.001,
        },
        "first_year": first,
        "last_year": last,
        "public_packaged_input_years": [1700, 2300],
        "adjacent_context_guard_years": [first, last],
        "production_imports": [
            name
            for name in sys.modules
            if name == "fatebridge" or name.startswith("fatebridge.")
        ],
        "scope": "Complete declared packaged solar range and context guards; overlapping historical roots are reused events. Numerical implementation comparison, not physical observations, a blind holdout, civil-clock/classical/predictive or SOTA certification. Native years outside this range are separate.",
        "rows": rows,
    }
    if packet["production_imports"]:
        raise ValueError("Reference collection imported the candidate")
    data = json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    packed = gzip.compress(data, mtime=0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(packed)
    print(
        json.dumps(
            {
                "rows": len(rows),
                "maximum_bracket_seconds": float(max((high - low) * 86400)),
                "compressed_bytes": len(packed),
                "sha256": hashlib.sha256(packed).hexdigest(),
                "producer_sha256": producer_sha256,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
