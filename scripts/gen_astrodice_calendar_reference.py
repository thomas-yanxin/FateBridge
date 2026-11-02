"""Generate every declared Gregorian triple with ERFA, without the candidate."""

import argparse
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path


def collect(protocol_path, output):
    import erfa
    import numpy as np

    protocol = json.loads(protocol_path.read_text())
    for name, version in protocol["dependencies"].items():
        if importlib.metadata.version(name) != version:
            raise ValueError("Frozen dependency changed")
    if output.exists():
        raise FileExistsError(output)
    y = np.arange(1, 10000, dtype=np.int32)[:, None, None]
    m = np.arange(1, 13, dtype=np.int32)[None, :, None]
    d = np.arange(1, 32, dtype=np.int32)[None, None, :]
    origin, mjd, status = erfa.ufunc.cal2jd(y, m, d)
    records = np.empty(mjd.shape, dtype=[("mjd", "<f8"), ("status", "i1")])
    records["mjd"] = mjd
    records["status"] = status
    with output.open("xb") as handle:
        handle.write(records.tobytes(order="C"))
    counts = {
        str(int(k)): int(v) for k, v in zip(*np.unique(status, return_counts=True))
    }
    assert not any(
        k == "fatebridge" or k.startswith("fatebridge.") or k == "swisseph"
        for k in sys.modules
    )
    result = {
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "records": int(records.size),
        "bytes": output.stat().st_size,
        "binary_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "status_counts": counts,
        "all_mjd_origins_2400000_5": bool(np.all(origin == 2400000.5)),
        "all_mjd_finite": bool(np.all(np.isfinite(mjd))),
        "candidate_imported": False,
        "candidate_compared": False,
        "dependencies": {
            n: importlib.metadata.version(n) for n in protocol["dependencies"]
        },
        "scope": "All Gregorian triples in the declared finite grid. Bad-day statuses retained. Midnight calendar labels only; no UT1/TT/TDB conversion or physical ephemeris acceptance.",
    }
    output.with_suffix(".metadata.json").write_text(json.dumps(result, indent=2) + "\n")
    if (
        counts != {"-3": 67569, "0": 3652059}
        or not result["all_mjd_origins_2400000_5"]
        or not result["all_mjd_finite"]
    ):
        raise ValueError("Reference domain/quality failure; raw output retained")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    collect(args.protocol, args.output)
