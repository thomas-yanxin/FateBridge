"""Freeze geocentric apparent RA/Dec from NASA/JPL Horizons, quantity 2.

Six civil instants are fixed before comparison. Never call FateBridge to create
expected positions. The 2 arcsecond engineering tolerance is declared here.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
DATES = [
    "1985-12-31 05:15:00",
    "1990-04-06 01:33:00",
    "2000-02-29 18:15:00",
    "2024-03-20 06:30:00",
    "2025-03-04 04:00:00",
    "2026-10-22 00:00:00",
]
BODIES = dict(
    Sun=10, Moon=301, Mercury=199, Venus=299, Mars=499, Jupiter=599, Saturn=699
)


def fetch(item):
    name, number = item
    parameters = {
        "format": "json",
        "COMMAND": f"'{number}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'500@399'",
        "TLIST": " ".join(f"'{d}'" for d in DATES),
        "TLIST_TYPE": "'CAL'",
        "TIME_TYPE": "'UT'",
        "QUANTITIES": "'2,31,49'",
        "CSV_FORMAT": "'YES'",
        "EXTRA_PREC": "'YES'",
        "CAL_TYPE": "'GREGORIAN'",
        "ANG_FORMAT": "'DEG'",
        "APPARENT": "'AIRLESS'",
    }
    response = json.loads(
        subprocess.check_output(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--max-time",
                "45",
                "--retry",
                "3",
                "--retry-delay",
                "1",
                URL + "?" + urlencode(parameters),
            ]
        )
    )
    if "error" in response:
        raise RuntimeError(response["error"])
    raw = response["result"]
    table = raw.split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
    rows = []
    for row in csv.reader(io.StringIO(table)):
        when = datetime.strptime(row[0].strip(), "%Y-%b-%d %H:%M:%S.%f").replace(
            tzinfo=timezone.utc
        )
        rows.append(
            {
                "utc": when.isoformat(),
                "right_ascension": float(row[3]),
                "declination": float(row[4]),
                "longitude": float(row[5]),
                "latitude": float(row[6]),
                "dut1_seconds": float(row[7]),
            }
        )
    if len(rows) != len(DATES):
        raise ValueError("Incomplete independent reference")
    return {
        "body": name,
        "parameters": parameters,
        "response": response,
        "response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "rows": rows,
    }


def main():
    with ThreadPoolExecutor(max_workers=3) as pool:
        references = list(pool.map(fetch, BODIES.items()))
    result = {
        "source": URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Geocentric apparent true-equator/equinox-of-date RA/Dec, airless, modern degrees; validates physical positions, not historical mansion-anchor choices or prediction efficacy.",
        "tolerance_arcseconds": 2.0,
        "references": references,
    }
    path = (
        Path(__file__).resolve().parents[1]
        / "tests/data/sukuyo-equatorial-horizons.json"
    )
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f'Frozen {sum(len(r["rows"]) for r in references)} external RA/Dec positions')


if __name__ == "__main__":
    main()
