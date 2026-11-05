"""Independent ERFA calendar oracle for the frozen UTC year-boundary cases."""

import argparse
import hashlib
import importlib.metadata
import json
import sys
from datetime import datetime
from fractions import Fraction
from pathlib import Path


def collect(protocol_path, output):
    import erfa

    protocol = json.loads(protocol_path.read_text())
    for name, version in protocol["dependencies"].items():
        if importlib.metadata.version(name) != version:
            raise ValueError("Frozen dependency changed")
    rows = []
    for case in protocol["cases"]:
        year, month, day, hour, minute, second, microsecond = case["utc"]
        origin, mjd = erfa.cal2jd(year, month, day)
        seconds = Fraction((hour * 60 + minute) * 60 + second) + Fraction(
            microsecond, 1000000
        )
        exact = Fraction(float(origin)) + Fraction(float(mjd)) + seconds / 86400
        local = datetime.fromisoformat(case["date"] + "T" + case["time"])
        local_origin, local_mjd = erfa.cal2jd(local.year, local.month, local.day)
        offset = case.get("expected_offset_seconds")
        if offset is None:
            offset = {"Etc/GMT-14": 14 * 3600, "Etc/GMT+12": -12 * 3600}[case["zone"]]
        local_seconds = Fraction(
            (local.hour * 60 + local.minute) * 60 + local.second
        ) + Fraction(local.microsecond, 1000000)
        independently_shifted = (
            Fraction(float(local_origin))
            + Fraction(float(local_mjd))
            + (local_seconds - offset) / 86400
        )
        if exact != independently_shifted:
            raise ValueError("Declared UTC components disagree with local-minus-offset")
        tt = (
            exact
            + (
                protocol["leap_offset_seconds"]
                + Fraction(protocol["tt_minus_tai_seconds"])
            )
            / 86400
            if year >= 1972
            else None
        )
        rows.append(
            {
                "id": case["id"],
                "utc": case["utc"],
                "erfa_midnight_jd": [float(origin), float(mjd)],
                "local_erfa_midnight_jd": [float(local_origin), float(local_mjd)],
                "offset_seconds": offset,
                "local_minus_offset_matches_utc_exactly": True,
                "exact_jd_utc_fraction": [exact.numerator, exact.denominator],
                "expected_jd_utc": float(exact),
                "expected_jd_tt": float(tt) if tt is not None else None,
            }
        )
    assert not any(
        name == "fatebridge" or name.startswith("fatebridge.") or name == "swisseph"
        for name in sys.modules
    )
    result = {
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "candidate_imported": False,
        "candidate_compared": False,
        "rows": rows,
        "independent_scope": protocol["independent_scope"],
    }
    with output.open("x") as handle:
        handle.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"rows": len(rows), "candidate_imported": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    collect(args.protocol, args.output)
