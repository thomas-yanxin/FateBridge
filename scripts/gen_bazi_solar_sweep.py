"""Collect the entire supported year range daily from JPL, without engine imports.

The production candidate and five-second tolerance are fixed before collection.
This is a broad exploratory expansion after the separate 72-instant holdout,
not a second blind test. Preserve full replies in compressed, hashed files.
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate-source", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError("Use a new version; frozen sources are never overwritten")
    candidate = hashlib.sha256(args.candidate_source.read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True)
    manifest = {
        "protocol_id": "jpl_solar_daily_1900_2100_v1",
        "tolerance_seconds": 5,
        "candidate_sha256_before_collection": candidate,
        "classification": "exploratory range expansion with frozen candidate; not a new blind holdout",
        "selection": "every civil date from 1900-01-01 through 2100-12-31 at 12 UT; Greenwich equator, airless",
        "expected_total": 73414,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "references": [],
    }
    for year in range(1900, 2101, 25):
        stop = min(year + 25, 2101)
        params = {
            "format": "json",
            "COMMAND": "'10'",
            "OBJ_DATA": "'NO'",
            "MAKE_EPHEM": "'YES'",
            "EPHEM_TYPE": "'OBSERVER'",
            "CENTER": "'coord@399'",
            "COORD_TYPE": "'GEODETIC'",
            "SITE_COORD": "'0,0,0'",
            "START_TIME": f"'{year}-01-01 12:00'",
            "STOP_TIME": f"'{stop}-01-01 12:00'",
            "STEP_SIZE": "'1d'",
            "TIME_TYPE": "'UT'",
            "QUANTITIES": "'34,49'",
            "CSV_FORMAT": "'YES'",
            "EXTRA_PREC": "'YES'",
            "CAL_TYPE": "'GREGORIAN'",
            "ANG_FORMAT": "'DEG'",
            "TIME_DIGITS": "'FRACSEC'",
            "APPARENT": "'AIRLESS'",
        }
        url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urlencode(params)
        raw = subprocess.check_output(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "60",
                "--retry",
                "2",
                url,
            ]
        )
        reply = json.loads(raw)
        if "error" in reply:
            raise ValueError(reply["error"])
        table = reply["result"].split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
        count = sum(
            datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f").year < stop
            for row in csv.reader(io.StringIO(table))
        )
        expected = (datetime(stop, 1, 1) - datetime(year, 1, 1)).days
        if count != expected:
            raise ValueError("Incomplete daily reference")
        file = args.output_dir / f"{year}-{stop - 1}.json.gz"
        file.write_bytes(gzip.compress(raw, mtime=0))
        manifest["references"].append(
            {
                "start_year": year,
                "stop_year_exclusive": stop,
                "file": file.name,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                "rows": count,
                "request_url": url,
                "parameters": params,
            }
        )
        print(f"Frozen {count} dates: {year}–{stop - 1}", flush=True)
    if hashlib.sha256(args.candidate_source.read_bytes()).hexdigest() != candidate:
        raise ValueError("Candidate source changed during collection")
    assert sum(r["rows"] for r in manifest["references"]) == manifest["expected_total"]
    p = args.output_dir / "manifest.json"
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    p.with_suffix(".sha256").write_text(
        hashlib.sha256(p.read_bytes()).hexdigest() + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
